from fastapi import FastAPI, Header, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
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
from aiohttp import ClientError, ClientConnectorError
import time
import uuid
import shutil

from parser import extract_formatted_blocks, save_blocks_to_json
from semantic_matcher import match_blocks
from supabase_client import upload_to_supabase, get_public_url, get_supabase_client

# ---------------------------------------------------------
# Heading detection helpers (from your original code)
# ---------------------------------------------------------

SECTION_PATTERNS = [
    r"^\d+(\.\d+)*\s+[A-Za-z].*$",        # 1, 1.1, 1.1.2 titled sections
    r"^[A-Z][A-Z\s]{3,}$",                # ALL CAPS headings
    r"^(Coverage|Exclusions|Definitions|Benefits|Waiting Periods|Claims?)$",
]


def is_heading(text: str):
    text = text.strip()
    if not text:
        return False
    return any(re.match(p, text) for p in SECTION_PATTERNS)


# ---------------------------------------------------------
# Env + Groq setup
# ---------------------------------------------------------

load_dotenv(dotenv_path=".env", encoding="utf-8")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.1-8b-instant"
FAL_API_KEY = os.getenv("FAL_API_KEY")
FAL_API_URL = os.getenv("FAL_API_URL", "https://fal.run/fal-ai/fast-svd")
FAL_MODEL = os.getenv("FAL_MODEL", "fal-ai/fast-svd")

# In-memory store: session_id -> parsed blocks
SESSION_BLOCKS: dict[str, list[dict]] = {}

# ---------------------------------------------------------
# FastAPI app + CORS
# ---------------------------------------------------------

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------
# Supabase helpers (cache)
# ---------------------------------------------------------


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
        supabase.table("processed_docs").insert(
            {
                "url": pdf_url,
                "pdf_storage_path": pdf_storage_path,
                "json_url": json_url,
            }
        ).execute()
    except Exception as e:
        print(f"Cache save error: {e}")


# ---------------------------------------------------------
# Health routes
# ---------------------------------------------------------


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
                "How are claims processed?",
            ],
        },
    }


# ---------------------------------------------------------
# Request models
# ---------------------------------------------------------


class HackRxRequest(BaseModel):
    documents: str
    questions: list[str]


class ChatAskRequest(BaseModel):
    session_id: str
    question: str


class GenerateVideoRequest(BaseModel):
    prompt: str


# ---------------------------------------------------------
# Formatting helpers (from your original code)
# ---------------------------------------------------------


def format_context_with_headers(chunks):
    """
    Build text context using either header or section so Section Unknown never appears.
    """
    formatted_context = ""
    current_header = None
    for block in chunks:
        block_header = (block.get("header") or block.get("section") or "").strip()
        block_text = block.get("flagged_text", block.get("text", "")).strip()
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
        "moratorium": ["PRE-EXISTING", "HIGH PRIORITY", "CONDITION"],
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
        header = (block.get("header") or block.get("section") or "No Header").strip()
        if seen_headers[header] == 0:
            unique_blocks.append(block)
            seen_headers[header] += 1
        if len(unique_blocks) >= max_blocks:
            break
    references = []
    for block in unique_blocks:
        header = (block.get("header") or block.get("section") or "No Header").strip()
        page = block.get("page", "Unknown")
        section_match = re.match(r"^\[?(\d+(\.\d+(\.\d+)?)?)\.?", header)
        section_number = section_match.group(1) if section_match else "Unknown"
        references.append(f"Page {page} : Section {section_number} : {header}")
    return ", ".join(references) if references else "No relevant sections found"


def format_answer_json(question: str, answer_text: str, matched_blocks: list):
    """
    Creates structured JSON with correct section/page/text for each reference block.
    Also converts escaped \\n into real newlines.
    """
    references = []

    for b in matched_blocks:
        clean_text = (
            b.get("text") or b.get("flagged_text") or ""
        ).replace("\\n", "\n").strip()

        ref = {
            "page": b.get("page") or b.get("pagenumber") or "Unknown",
            "section": b.get("section") or b.get("header") or "Miscellaneous",
            "text": clean_text,
        }

        references.append(ref)

    return {
        "question": question,
        "answer": answer_text.strip(),
        "references": references,
    }


# ---------------------------------------------------------
# Groq client
# ---------------------------------------------------------


async def query_groq(prompt: str):
    if not GROQ_API_KEY:
        raise HTTPException(status_code=500, detail="Groq API key not set")

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": GROQ_MODEL,
        "messages": [{"role": "user", "content": prompt}],
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


# ---------------------------------------------------------
# Shared question-answer helper
# ---------------------------------------------------------


async def answer_question_from_blocks(blocks, question: str, idx: int = 0):
    upload_filename = f"json/query_data_q{idx + 1}.json"

    matched, _ = match_blocks(
        paragraphs=blocks,
        query=question,
        bucket_name="doc-processing",
        upload_filename=upload_filename,
        top_n=8,
        include_neighbors=True,
    )

    context = format_context_with_headers(matched)

    prompt = (
        "You must answer strictly and exclusively from the provided document. "
        "Your entire output must remain fully grounded in it.\n\n"
        "RULES (no exceptions):\n"
        "1. Use ONLY information explicitly in the document.\n"
        "2. Quote exact wording whenever referencing the document.\n"
        "3. Do NOT add, assume, infer, interpret, or use outside knowledge.\n"
        "4. Do NOT summarize unless the summary consists only of quoted text.\n"
        "5. Do NOT fabricate details, metadata, page numbers, or section labels.\n"
        "6. Do NOT explain or expand beyond what the document states.\n"
        "7. If the answer is not explicitly present, reply EXACTLY:\n"
        "   Answer not found in the provided document.\n"
        "8. No alternative phrasing or extra commentary beyond the answer.\n\n"
        "TASK:\n"
        "Answer the question strictly using the document.\n\n"
        f"Document:\n{context}\n\n"
        f"Question: {question}\n\n"
        "Answer:"
    )

    result = await query_groq(prompt)

    # Fallback if needed
    if ("Answer not found" in result) or not re.search(r"\d", result):
        full_context = format_context_with_headers(blocks)
        prompt_full = (
            "You are an assistant answering questions based only on the provided document.\n"
            "Quote the relevant policy wording exactly where possible.\n"
            "If the answer is not found, reply exactly: Answer not found in the provided document.\n\n"
            f"Document:\n{full_context}\n\n"
            f"Question: {question}\nAnswer:"
        )
        result = await query_groq(prompt_full)

    cleaned_result = result.replace("\\n", "\n").strip()
    formatted = format_answer_json(question, cleaned_result, matched)
    return formatted


# ---------------------------------------------------------
# New upload + ask endpoints (for your UI)
# ---------------------------------------------------------


@app.post("/hackrx/upload_file")
async def upload_file(file: UploadFile = File(...)):
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    # Save uploaded PDF to a temp file
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_pdf:
            shutil.copyfileobj(file.file, tmp_pdf)
            pdf_path = tmp_pdf.name
    finally:
        file.file.close()

    # Parse PDF into blocks
    try:
        blocks = extract_formatted_blocks(pdf_path)
        save_blocks_to_json(blocks)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse PDF: {e}")

    # Create a session and store blocks in memory
    session_id = str(uuid.uuid4())
    SESSION_BLOCKS[session_id] = blocks

    return {
        "session_id": session_id,
        "message": "PDF uploaded and parsed successfully.",
    }


@app.post("/hackrx/ask")
async def ask_question(req: ChatAskRequest):
    blocks = SESSION_BLOCKS.get(req.session_id)
    if blocks is None:
        raise HTTPException(
            status_code=404,
            detail="Session not found. Please upload and process the PDF again.",
        )

    try:
        answer_obj = await answer_question_from_blocks(blocks, req.question, idx=0)
        return answer_obj
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/hackrx/generate_video")
async def generate_video(req: GenerateVideoRequest):
    if not FAL_API_KEY:
        raise HTTPException(status_code=500, detail="FAL API key not set")

    payload = {
        "prompt": req.prompt,
        "duration_seconds": 8,
        "model": FAL_MODEL,
    }

    headers = {
        "Authorization": f"Key {FAL_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30)
        ) as session:
            async with session.post(FAL_API_URL, json=payload, headers=headers) as resp:
                body_text = await resp.text()
                if resp.status >= 300:
                    raise HTTPException(
                        status_code=resp.status,
                        detail=f"FAL API error: {body_text}",
                    )

                try:
                    data = await resp.json()
                except Exception:
                    raise HTTPException(
                        status_code=500, detail="Invalid response from FAL API"
                    )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail="Timed out waiting for FAL API. Please try again later.",
        )
    except ClientConnectorError:
        raise HTTPException(
            status_code=502,
            detail="Unable to reach FAL API host. Check FAL_API_URL, network access, or DNS settings.",
        )
    except ClientError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Network error talking to FAL API: {exc}",
        )

    video_url = (
        data.get("video_url")
        or data.get("url")
        or data.get("output_url")
        or data.get("result")
    )

    if not video_url:
        raise HTTPException(status_code=500, detail="No video URL returned by FAL API")

    return {"video_url": video_url, "job_id": data.get("id") or data.get("job_id")}


# ---------------------------------------------------------
# Original /hackrx/run (URL-based) endpoint
# ---------------------------------------------------------


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

            json_url = get_public_url(
                "doc-processing", "json/reconstructed_paragraphs.json"
            )
            save_processed_doc(req.documents, "pdf/input.pdf", json_url)

        async def process_question(idx, question):
            q_start = time.time()
            formatted = await answer_question_from_blocks(blocks, question, idx=idx)
            print(f"Q{idx+1} done in {time.time() - q_start:.2f} sec")
            return formatted

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
