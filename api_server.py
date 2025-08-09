# api_server.py
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
from supabase_client import upload_to_supabase, supabase, get_public_url

load_dotenv(dotenv_path=".env", encoding="utf-8")

COHERE_API_KEY = os.getenv("COHERE_API_KEY")

app = FastAPI()

COHERE_URL = "https://api.cohere.ai/v1/chat"
COHERE_MODEL = "command-r-plus"


# --------------------------
# Cache helpers
# --------------------------
def get_existing_parsed_data(pdf_url: str):
    """Check Supabase for an already processed document."""
    try:
        res = supabase.table("processed_docs").select("*").eq("url", pdf_url).execute()
        if res.data:
            return res.data[0]
    except Exception as e:
        print(f"❌ Cache lookup error: {e}")
    return None


def save_processed_doc(pdf_url: str, pdf_storage_path: str, json_url: str):
    """Store processed document info in Supabase."""
    try:
        supabase.table("processed_docs").insert({
            "url": pdf_url,
            "pdf_storage_path": pdf_storage_path,
            "json_url": json_url
        }).execute()
    except Exception as e:
        print(f"❌ Cache save error: {e}")


# --------------------------
# API health checks
# --------------------------
@app.get("/")
async def health_check():
    return {"status": "healthy", "message": "CORE API is running"}


@app.get("/health")
async def health():
    return {"status": "ok", "service": "CORE API"}


# --------------------------
# Request model
# --------------------------
class HackRxRequest(BaseModel):
    documents: str
    questions: list[str]


# --------------------------
# Formatting helpers
# --------------------------
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


# --------------------------
# Async Cohere query
# --------------------------
async def query_cohere(prompt: str):
    headers = {
        "Authorization": f"Bearer {COHERE_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": COHERE_MODEL,
        "message": prompt,
        "temperature": 0.3,
        "max_tokens": 300,
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(COHERE_URL, headers=headers, json=payload) as resp:
            if resp.status == 200:
                try:
                    data = await resp.json()
                    return data["text"]
                except Exception as e:
                    print("JSON parsing error:", e)
                    text = await resp.text()
                    print("Raw response:", text)
                    return "Error: Failed to parse Cohere response"
            else:
                print("Cohere Error:", resp.status)
                text = await resp.text()
                print("Raw response:", text)
                return f"Error: Cohere returned status {resp.status}"


# --------------------------
# Main endpoint
# --------------------------
@app.post("/hackrx/run")
async def run_hackrx(req: HackRxRequest, authorization: str = Header(None)):
    start_time = time.time()

    if not COHERE_API_KEY:
        raise HTTPException(status_code=500, detail="Cohere API key not set")

    try:
        # Step 0: Check if already processed
        step0 = time.time()
        existing = get_existing_parsed_data(req.documents)
        print(f"⏱ Cache check: {time.time() - step0:.2f} sec")

        if existing:
            print("✅ Using cached parsed data from Supabase")
            step_json = time.time()
            blocks = requests.get(existing["json_url"]).json()
            print(f"⏱ JSON fetch from cache: {time.time() - step_json:.2f} sec")
        else:
            # Step 1: Download & upload PDF
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
            print(f"⏱ PDF download + upload: {time.time() - step1:.2f} sec")

            # Step 2: Parse
            step2 = time.time()
            blocks = extract_formatted_blocks(pdf_path)
            save_blocks_to_json(blocks)
            print(f"⏱ PDF parsing + JSON save: {time.time() - step2:.2f} sec")

            # Step 3: Save mapping in Supabase
            json_url = get_public_url("doc-processing", "json/reconstructed_paragraphs.json")
            save_processed_doc(req.documents, "pdf/input.pdf", json_url)

        # Step 4: Process all questions in parallel
        async def process_question(idx, question):
            q_start = time.time()
            upload_filename = f"json/query_data_q{idx + 1}.json"
            matched, _ = match_blocks(
                paragraphs=blocks,
                query=question,
                bucket_name="doc-processing",
                upload_filename=upload_filename
            )
            context = format_context_with_headers(matched)
            prompt = f"""You are an expert assistant analyzing an insurance policy document. Use the extracted text below to answer the user's question with:

1. A **detailed**, **well-structured** explanation.
2. Clear **justifications** by referring to specific clauses, page numbers, or headers found in the context.
3. Make it easy to trace your reasoning back to the document — ideally mention specific phrases or logic behind your conclusion.
4. If the answer requires interpretation or there's ambiguity, explain that too.

Coverage flags:
COVERS = Inclusions/Benefits  
EXCLUDES = Exclusions/Not Covered  
EXCEPTION/LIMITATION = Conditions/Restrictions  
CONDITION = Requirements/Conditions  
PRE-EXISTING = Pre-existing condition related  
CLAIMS = Claims process related  
HIGH PRIORITY = Very important coverage information  
MEDIUM PRIORITY = Important coverage information  

### Context:
{context}

### Question:
{question}

### Detailed Answer with Justification:"""

            result = await query_cohere(prompt)
            references = format_reference(matched, question=question)
            ans = f"{result.strip()} Reference : {references}"
            print(f"✅ Q{idx+1} done in {time.time() - q_start:.2f} sec")
            return ans

        step4 = time.time()
        answers = await asyncio.gather(
            *[process_question(i, q) for i, q in enumerate(req.questions)]
        )
        print(f"⏱ All Qs processed in parallel: {time.time() - step4:.2f} sec")

        print(f"⏱ TOTAL request time: {time.time() - start_time:.2f} sec")
        return {"answers": answers}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --------------------------
# Run server
# --------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
