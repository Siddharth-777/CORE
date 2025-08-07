# api_server.py
from fastapi import FastAPI, Request, Header, HTTPException
from pydantic import BaseModel
import uvicorn
import requests
import os
from parser import extract_formatted_blocks, save_blocks_to_json
from keyword_extractor import extract_keywords
from main import format_context_with_headers, query_ollama
import json

app = FastAPI()

PDF_FILE = "input.pdf"
PARAGRAPH_FILE = "reconstructed_paragraphs.json"
QUERY_FILE = "query_data.json"
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3"

class HackRxRequest(BaseModel):
    documents: str
    questions: list[str]

@app.post("/hackrx/run")
async def run_hackrx(req: HackRxRequest, authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        # Step 1: Download the document
        pdf_url = req.documents
        pdf_data = requests.get(pdf_url)
        with open(PDF_FILE, "wb") as f:
            f.write(pdf_data.content)

        # Step 2: Parse PDF
        blocks = extract_formatted_blocks(PDF_FILE)
        save_blocks_to_json(blocks, PARAGRAPH_FILE)

        answers = []

        for question in req.questions:
            # Step 3: Keyword Match
            keywords = extract_keywords(question)
            with open(PARAGRAPH_FILE, "r", encoding="utf-8") as f:
                paragraphs = json.load(f)

            matched = [b for b in paragraphs if any(k in b["text"].lower() for k in keywords)]

            with open(QUERY_FILE, "w", encoding="utf-8") as f:
                json.dump(matched, f, indent=2)

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

            # Step 5: Query Ollama
            result = query_ollama(OLLAMA_MODEL, prompt)
            answers.append(result.strip())

        return {"answers": answers}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
