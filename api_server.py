# api_server.py
from fastapi import FastAPI, Request, Header, HTTPException
from pydantic import BaseModel
import uvicorn
import requests
import os
from parser import extract_formatted_blocks, save_blocks_to_json
from keyword_extractor import extract_keywords
from main import format_context_with_headers
import json

app = FastAPI()

PDF_FILE = "input.pdf"
PARAGRAPH_FILE = "reconstructed_paragraphs.json"
QUERY_FILE = "query_data.json"

COHERE_API_KEY = os.getenv("COHERE_API_KEY")  # Set this as an env variable
COHERE_URL = "https://api.cohere.ai/v1/chat"
COHERE_MODEL = "command-r-plus"  # Pro model

class HackRxRequest(BaseModel):
    documents: str
    questions: list[str]

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
        return response.json()["text"]
    else:
        print("Cohere Error:", response.status_code, response.text)
        return "Error: Could not get response from Cohere"

@app.post("/hackrx/run")
async def run_hackrx(req: HackRxRequest, authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")

    if not COHERE_API_KEY:
        raise HTTPException(status_code=500, detail="Cohere API key not set")

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

            # Step 5: Query Cohere instead of Ollama
            result = query_cohere(prompt)
            answers.append(result.strip())

        return {"answers": answers}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
