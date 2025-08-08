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

from parser import extract_formatted_blocks, save_blocks_to_json
from semantic_matcher import match_blocks
from supabase_client import upload_to_supabase

load_dotenv(dotenv_path=".env", encoding="utf-8")

COHERE_API_KEY = os.getenv("COHERE_API_KEY")

app = FastAPI()

COHERE_URL = "https://api.cohere.ai/v1/chat"
COHERE_MODEL = "command-r-plus"

@app.get("/")
async def health_check():
    return {"status": "healthy", "message": "CORE API is running"}

@app.get("/health")
async def health():
    return {"status": "ok", "service": "CORE API"}

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
    """
    Format the top matching blocks as a reference string in the format 'Page X : Section Y : Header'.
    Prioritize blocks with relevant coverage flags based on the question.
    """
    seen_headers = defaultdict(int)  # Track headers to avoid duplicates
    unique_blocks = []
    
    # Define relevant coverage flags for each question type
    relevant_flags = {
        "grace period": ["CONDITION", "HIGH PRIORITY"],
        "maternity": ["MATERNITY", "COVERS", "EXCLUDES", "CONDITION"],
        "moratorium": ["PRE-EXISTING", "HIGH PRIORITY", "CONDITION"]
    }
    
    # Select relevant flags based on question content
    question_lower = question.lower()
    selected_flags = []
    for key, flags in relevant_flags.items():
        if key in question_lower:
            selected_flags = flags
            break
    
    # Prioritize blocks with relevant coverage flags
    prioritized_blocks = []
    for block in blocks:
        flags = [f["type"] for f in block.get("coverage_flags", [])]
        if selected_flags and any(flag in flags for flag in selected_flags):
            prioritized_blocks.append(block)
        elif not selected_flags:  # Fallback if no specific flags match
            prioritized_blocks.append(block)
    
    # Remove duplicates
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
        # Extract section number (e.g., '2.21', '3.1.14', '5.6')
        section_match = re.match(r'^\[?(\d+(\.\d+(\.\d+)?)?)\.?', header)
        section_number = section_match.group(1) if section_match else "Unknown"
        references.append(f"Page {page} : Section {section_number} : {header}")
    
    return ", ".join(references) if references else "No relevant sections found"

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

@app.post("/hackrx/run")
async def run_hackrx(req: HackRxRequest, authorization: str = Header(None)):

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
            context = format_context_with_headers(matched)  # All matched blocks
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


            # Step 5: Query Cohere
            result = query_cohere(prompt)
            # Step 6: Format answer with references
            references = format_reference(matched, question=question)
            full_answer = f"{result.strip()} Reference : {references}"
            answers.append(full_answer)

        return {
            "answers": answers
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Add this main block to handle Railway deployment
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
