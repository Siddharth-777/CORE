import json
import requests
from supabase_client import upload_to_supabase


OLLAMA_MODEL = "llama3"
OLLAMA_URL = "http://localhost:11434/api/generate"

QUERY_FILE = "query_data.json"
USER_QUESTION = "How does the Transformer architecture enable better parallelization compared to RNNs and CNNs?"

upload_to_supabase("doc-processing", QUERY_FILE, "json/query_data.json")


with open(QUERY_FILE, "r", encoding="utf-8") as f:
    chunks = json.load(f)

context = "\n\n".join(block["text"] for block in chunks)

prompt = f"""Use the following extracted content from a research paper to answer the question.

### Context:
{context}

### Question:
{USER_QUESTION}

### Answer:"""

def query_ollama(model: str, prompt: str):
    response = requests.post(OLLAMA_URL, json={
        "model": model,
        "prompt": prompt,
        "stream": False
    })

    if response.status_code == 200:
        return response.json()["response"]
    else:
        print("Error from Ollama:", response.status_code)
        print(response.text)
        return ""

if __name__ == "__main__":
    print("Querying Ollama...\n")
    answer = query_ollama(OLLAMA_MODEL, prompt)
    print("Answer:\n")
    print(answer)