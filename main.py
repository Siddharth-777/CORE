import time
import os
import json
import sys
from parser import extract_formatted_blocks, save_blocks_to_json
from keyword_extractor import extract_keywords
import requests

PDF_PATH = "sample 2.pdf"
PARAGRAPHS_FILE = "reconstructed_paragraphs.json"
QUERY_DATA_FILE = "query_data.json"
OLLAMA_MODEL = "llama3"
OLLAMA_URL = "http://localhost:11434/api/generate"

def step_1_extract_pdf():
    print("STEP 1: Extract PDF Content")
    print("-" * 30)
    
    if not os.path.exists(PDF_PATH):
        print(f"PDF file not found: {PDF_PATH}")
        return False
    
    try:
        import sys
        from io import StringIO
        
        old_stdout = sys.stdout
        captured_output = StringIO()
        sys.stdout = captured_output
        
        blocks = extract_formatted_blocks(PDF_PATH)
        save_blocks_to_json(blocks, PARAGRAPHS_FILE)
        
        sys.stdout = old_stdout
        
        output = captured_output.getvalue()
        lines = output.split('\n')
        
        show_line = False
        for line in lines:
            if 'SUMMARY:' in line:
                show_line = True
            elif 'PDF content extracted successfully' in line:
                show_line = False
            
            if show_line or line.startswith('HEADERS FOUND:') or line.startswith('HIGH PRIORITY COVERAGE BLOCKS:') or line.startswith('Extracted'):
                print(line)
        
        print(f"PDF content extracted successfully")
        return True
    except Exception as e:
        sys.stdout = old_stdout
        print(f"Error: {e}")
        return False

def step_2_semantic_matching(query):
    print("\nSTEP 2: Find Relevant Content")
    print("-" * 30)
    
    if not os.path.exists(PARAGRAPHS_FILE):
        print(f"Paragraphs file not found")
        return False
    
    try:
        with open(PARAGRAPHS_FILE, "r", encoding="utf-8") as f:
            paragraphs = json.load(f)
        
        keywords = extract_keywords(query)
        print(f"Keywords: {keywords}")
        
        matched_blocks = []
        for block in paragraphs:
            text = block["text"].lower()
            if any(keyword in text for keyword in keywords):
                matched_blocks.append(block)
        
        with open(QUERY_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(matched_blocks, f, indent=2, ensure_ascii=False)
        
        print(f"Relevant content found")
        return True
        
    except Exception as e:
        print(f"Error: {e}")
        return False

def query_ollama(model: str, prompt: str):
    try:
        response = requests.post(OLLAMA_URL, json={
            "model": model,
            "prompt": prompt,
            "stream": False
        })
        
        if response.status_code == 200:
            return response.json()["response"]
        else:
            print(f"Ollama error: {response.status_code}")
            return ""
    except requests.exceptions.ConnectionError:
        print("Cannot connect to Ollama")
        return ""
    except Exception as e:
        print(f"Error: {e}")
        return ""

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

def step_3_llm_query(query):
    print("\nSTEP 3: Generate Answer")
    print("-" * 30)
    
    if not os.path.exists(QUERY_DATA_FILE):
        print(f"Query data file not found")
        return False
    
    try:
        with open(QUERY_DATA_FILE, "r", encoding="utf-8") as f:
            chunks = json.load(f)
        
        if not chunks:
            print("No matching content found")
            return False
        
        chunks = chunks[:30]
        context = format_context_with_headers(chunks)
        
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
{query}

### Answer:"""
        
        print(f"Querying {OLLAMA_MODEL}...")
        answer = query_ollama(OLLAMA_MODEL, prompt)
        
        if answer:
            print("\n" + "=" * 40)
            print("ANSWER:")
            print("=" * 40)
            print(answer)
            return True
        else:
            return False
            
    except Exception as e:
        print(f"Error: {e}")
        return False

def main():
    print("PDF RAG System - 3 Steps")
    print("=" * 40)

    start_time = time.time()
    
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
    else:
        query = "Is attempt of suicide covered in the policy?"
    
    print(f"Query: {query}\n")
    
    if not step_1_extract_pdf():
        return
    
    if not step_2_semantic_matching(query):
        return
    
    if not step_3_llm_query(query):
        return
    
    end_time = time.time()  # End timer
    total_time = end_time - start_time

    print(f"\nPipeline completed successfully!")
    print(f"Total execution time: {total_time:.2f} seconds")


if __name__ == "__main__":
    main()