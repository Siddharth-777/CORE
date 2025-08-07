# api_server.py
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
import uvicorn
import requests
import os
import tempfile
from dotenv import load_dotenv

from parser import extract_formatted_blocks, save_blocks_to_json
from semantic_matcher import match_blocks
from supabase_client import upload_to_supabase

load_dotenv(dotenv_path=".env", encoding="utf-8")

COHERE_API_KEY = os.getenv("COHERE_API_KEY")

app = FastAPI()

COHERE_URL = "https://api.cohere.ai/v1/chat"
COHERE_MODEL = "command-r-plus"

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

def query_cohere(prompt: str):
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

    response = requests.post(COHERE_URL, headers=headers, json=payload)

    if response.status_code == 200:
        try:
            return response.json()["text"]
        except Exception as e:
            print("JSON parsing error:", e)
            print("Raw response:", response.text)
            return "Error: Failed to parse Cohere response"
    else:
        print("Cohere Error:", response.status_code)
        print("Raw response:", response.text)
        return f"Error: Cohere returned status {response.status_code}"

@app.get("/")
def home():
    return {"status": "CORE API is running ✅", "docs": "/docs"}

@app.post("/hackrx/run")
async def run_hackrx(req: HackRxRequest, authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")

    if not COHERE_API_KEY:
        raise HTTPException(status_code=500, detail="Cohere API key not set")

    try:
        # Step 1: Download and upload PDF to Supabase
        pdf_url = req.documents
        pdf_data = requests.get(pdf_url)
        if pdf_data.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to download PDF")

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_pdf:
            tmp_pdf.write(pdf_data.content)
            tmp_pdf.flush()
            upload_to_supabase("doc-processing", tmp_pdf.name, "pdf/input.pdf")
            pdf_path = tmp_pdf.name  # used for parsing

        # Step 2: Parse PDF
        blocks = extract_formatted_blocks(pdf_path)
        save_blocks_to_json(blocks)  # this uploads directly to Supabase

        answers = []

        for idx, question in enumerate(req.questions):
            # Step 3: Match blocks and upload JSON to Supabase
            upload_filename = f"json/query_data_q{idx + 1}.json"
            matched, _ = match_blocks(
                paragraphs=blocks,
                query=question,
                bucket_name="doc-processing",
                upload_filename=upload_filename
            )

            # Step 4: Format prompt
            context = format_context_with_headers(matched[:30])
            prompt = f"""Use the following extracted content from a policy document to answer the question.

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

### Answer:"""

            # Step 5: Query Cohere
            result = query_cohere(prompt)
            answers.append(result.strip())

        return {
            "answers": answers
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
