from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
import uvicorn
import requests
import os
import tempfile
from dotenv import load_dotenv
from collections import defaultdict
import re
import asyncio
import aiohttp
import time

from parser import extract_formatted_blocks, save_blocks_to_json
from semantic_matcher import match_blocks
from supabase_client import upload_to_supabase, get_public_url, get_supabase_client

load_dotenv(dotenv_path=".env", encoding="utf-8")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

app = FastAPI()

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.1-8b-instant"


def get_existing_parsed_data(pdf_url: str):
    try:
        supabase = get_supabase_client()
        res = supabase.table("processed_docs").select("*").eq("url", pdf_url).execute()
        if res.data:
            return res.data[0]
    except Exception as e:
        print(f"Cache lookup error: {e}")
    return None


def save_processed_doc(pdf_url: str, pdf_storage_path: str, json_url: str):
    try:
        supabase = get_supabase_client()
        supabase.table("processed_docs").insert({
            "url": pdf_url,
            "pdf_storage_path": pdf_storage_path,
            "json_url": json_url
        }).execute()
    except Exception as e:
        print(f"Cache save error: {e}")


@app.get("/")
async def health_check():
    return {"status": "healthy", "message": "CORE API is running"}


@app.get("/health")
async def health():
    return {"status": "ok", "service": "CORE API"}


@app.get("/hackrx/run")
async def run_hackrx_get():
    return {
        "detail": "Use POST /hackrx/run with a JSON body",
        "example": {
            "documents": "https://example.com/sample.pdf",
            "questions": [
                "What are the coverage exclusions?",
                "How are claims processed?"
            ]
        }
    }


class HackRxRequest(BaseModel):
    documents: str
    questions: list[str]


def format_context_with_headers(chunks):
    formatted_context = ""
    current_header = None
    for block in chunks:
        block_header = block.get("header", "").strip()
        block_text = block.get("flagged_text", block["text"]).strip()
        if block_header and block_header != current_header:
            current_header = block_header
            formatted_context += f"\n{block_header}\n"
        formatted_context += f"{block_text}\n\n"
    return formatted_context.strip()


def format_reference(blocks, max_blocks=3, question=""):
    seen_headers = defaultdict(int)
    unique_blocks = []
    relevant_flags = {
        "grace period": ["CONDITION", "HIGH PRIORITY"],
        "maternity": ["MATERNITY", "COVERS", "EXCLUDES", "CONDITION"],
        "moratorium": ["PRE-EXISTING", "HIGH PRIORITY", "CONDITION"]
    }
    question_lower = question.lower()
    selected_flags = []
    for key, flags in relevant_flags.items():
        if key in question_lower:
            selected_flags = flags
            break
    prioritized_blocks = []
    for block in blocks:
        flags = [f["type"] for f in block.get("coverage_flags", [])]
        if selected_flags and any(flag in flags for flag in selected_flags):
            prioritized_blocks.append(block)
        elif not selected_flags:
            prioritized_blocks.append(block)
    for block in prioritized_blocks:
        header = block.get("header", "No Header").strip()
        if seen_headers[header] == 0:
            unique_blocks.append(block)
            seen_headers[header] += 1
        if len(unique_blocks) >= max_blocks:
            break
    references = []
    for block in unique_blocks:
        header = block.get("header", "No Header").strip()
        page = block.get("page", "Unknown")
        section_match = re.match(r'^\[?(\d+(\.\d+(\.\d+)?)?)\.?', header)
        section_number = section_match.group(1) if section_match else "Unknown"
        references.append(f"Page {page} : Section {section_number} : {header}")
    return ", ".join(references) if references else "No relevant sections found"


async def query_groq(prompt: str):
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2,
        "max_tokens": 350,
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(GROQ_URL, headers=headers, json=payload) as resp:
            if resp.status == 200:
                try:
                    data = await resp.json()
                    return data["choices"][0]["message"]["content"]
                except Exception as e:
                    print("JSON parsing error:", e)
                    text = await resp.text()
                    print("Raw response:", text)
                    return "Error: Failed to parse Groq response"
            if resp.status in (401, 403):
                text = await resp.text()
                print("Groq auth error:", resp.status, text)
                raise HTTPException(
                    status_code=502,
                    detail=(
                        "Groq rejected the request (unauthorized). "
                        "Verify GROQ_API_KEY in your .env and confirm the key has access "
                        f"to the '{GROQ_MODEL}' model."
                    ),
                )

            print("Groq Error:", resp.status)
            text = await resp.text()
            print("Raw response:", text)
            return f"Error: Groq returned status {resp.status}"


@app.post("/hackrx/run")
async def run_hackrx(req: HackRxRequest, authorization: str = Header(None)):
    start_time = time.time()

    if not GROQ_API_KEY:
        raise HTTPException(status_code=500, detail="Groq API key not set")

    try:
        step0 = time.time()
        existing = get_existing_parsed_data(req.documents)
        print(f"Cache check: {time.time() - step0:.2f} sec")

        if existing:
            print("Using cached parsed data from Supabase")
            step_json = time.time()
            blocks = requests.get(existing["json_url"]).json()
            print(f"JSON fetch from cache: {time.time() - step_json:.2f} sec")
        else:
            step1 = time.time()
            pdf_url = req.documents
            pdf_data = requests.get(pdf_url)
            if pdf_data.status_code != 200:
                raise HTTPException(status_code=400, detail="Failed to download PDF")
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_pdf:
                tmp_pdf.write(pdf_data.content)
                tmp_pdf.flush()
                upload_to_supabase("doc-processing", tmp_pdf.name, "pdf/input.pdf")
                pdf_path = tmp_pdf.name
            print(f"PDF download + upload: {time.time() - step1:.2f} sec")

            step2 = time.time()
            blocks = extract_formatted_blocks(pdf_path)
            save_blocks_to_json(blocks)
            print(f"PDF parsing + JSON save: {time.time() - step2:.2f} sec")

            json_url = get_public_url("doc-processing", "json/reconstructed_paragraphs.json")
            save_processed_doc(req.documents, "pdf/input.pdf", json_url)

        async def process_question(idx, question):
            q_start = time.time()
            upload_filename = f"json/query_data_q{idx + 1}.json"

            matched, _ = match_blocks(
                paragraphs=blocks,
                query=question,
                bucket_name="doc-processing",
                upload_filename=upload_filename,
                top_n=8,
                include_neighbors=True
            )

            context = format_context_with_headers(matched)

            prompt = (
                "You are an assistant that must answer strictly and exclusively from the content contained in the provided document.\n"
                "Your entire reasoning and output must remain fully grounded in the document and nowhere else.\n\n"
                "NON-NEGOTIABLE RULES (the assistant must obey these exactly):\n"
                "1. You may use ONLY information explicitly written in the document.\n"
                "2. If you refer to information from the document, you must quote the exact wording with no alterations.\n"
                "3. You must not add, assume, infer, interpret, reformulate, or rely on any outside knowledge.\n"
                "4. You must not summarize unless the summary is composed entirely of quotes from the document.\n"
                "5. You must not fabricate details, metadata, page numbers, section labels, rationale, or context not present in the document.\n"
                "6. You must not attempt to explain, clarify, or expand beyond what the document directly states.\n"
                "7. If the answer is not explicitly present in the document, you must reply with EXACTLY:\n"
                "   Answer not found in the provided document.\n"
                "8. No alternative phrasing, no elaboration, and no additional commentary is allowed beyond the answer itself.\n\n"
                "OUTPUT REQUIREMENTS:\n"
                "- Your answer must follow all rules above without exception.\n"
                "- Your answer must be as concise as possible while strictly quoting the document when needed.\n"
                "- If multiple sections of the document are relevant, quote them exactly and only.\n\n"
                "TASK:\n"
                "Answer the question strictly using only the provided document.\n\n"
                f"Document:\n{context}\n\n"
                f"Question: {question}\n"
                "Answer:\n"
                "- Provide the answer using exact quotes from the document.\n"
                "- If no answer is available, respond exactly with: Answer not found in the provided document."
            )

            result = await query_groq(prompt)

            if ("Answer not found" in result) or not re.search(r'\d', result):
                print(f"Fallback triggered for Q{idx+1}")
                full_context = format_context_with_headers(blocks)
                prompt_full = (
                    "You are an assistant that must answer strictly and exclusively from the content contained in the provided document.\n"
                    "Your entire reasoning and output must remain fully grounded in the document and nowhere else.\n\n"
                    "NON-NEGOTIABLE RULES (the assistant must obey these exactly):\n"
                    "1. You may use ONLY information explicitly written in the document.\n"
                    "2. If you refer to information from the document, you must quote the exact wording with no alterations.\n"
                    "3. You must not add, assume, infer, interpret, reformulate, or rely on any outside knowledge.\n"
                    "4. You must not summarize unless the summary is composed entirely of quotes from the document.\n"
                    "5. You must not fabricate details, metadata, page numbers, section labels, rationale, or context not present in the document.\n"
                    "6. You must not attempt to explain, clarify, or expand beyond what the document directly states.\n"
                    "7. If the answer is not explicitly present in the document, you must reply with EXACTLY:\n"
                    "   Answer not found in the provided document.\n"
                    "8. No alternative phrasing, no elaboration, and no additional commentary is allowed beyond the answer itself.\n\n"
                    "OUTPUT REQUIREMENTS:\n"
                    "- Your answer must follow all rules above without exception.\n"
                    "- Your answer must be as concise as possible while strictly quoting the document when needed.\n"
                    "- If multiple sections of the document are relevant, quote them exactly and only.\n\n"
                    "TASK:\n"
                    "Answer the question strictly using only the provided document.\n\n"
                    f"Document:\n{full_context}\n\n"
                    f"Question: {question}\n"
                    "Answer:\n"
                    "- Provide the answer using exact quotes from the document.\n"
                    "- If no answer is available, respond exactly with: Answer not found in the provided document."
                )
                result = await query_groq(prompt_full)

            references = format_reference(matched, question=question)
            ans = f"{result.strip()} Reference : {references}"
            print(f"Q{idx+1} done in {time.time() - q_start:.2f} sec")
            return ans

        step4 = time.time()
        answers = await asyncio.gather(
            *[process_question(i, q) for i, q in enumerate(req.questions)]
        )
        print(f"All Qs processed in parallel: {time.time() - step4:.2f} sec")
        print(f"TOTAL request time: {time.time() - start_time:.2f} sec")
        return {"answers": answers}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
