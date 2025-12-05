# Contextual Oriented Retrieval and Extraction (CORE)

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/) 
[![License](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)

## Overview
CORE is a Python-based system for processing and analyzing PDF documents, with a focus on insurance policies. It uses natural language processing (NLP), semantic matching, and large language models (LLMs) to extract structured data, identify headers, flag coverage details, and answer user queries. The system parses PDFs, matches relevant sections to queries, generates answers, and stores results in Supabase. It also produces a text-only PDF with formatted headers and page numbers for reference.

## Key Features
- **PDF Parsing**: Extracts text blocks using PyMuPDF, analyzing fonts and colors to detect headers.
- **Keyword Extraction**: Uses spaCy to identify query keywords for semantic matching.
- **Header Detection**: Organizes content with hierarchical headers based on font size, color, and text patterns.
- **Coverage Analysis**: Flags coverage-related terms (e.g., inclusions, exclusions) with priority scoring.
- **Semantic Matching**: Matches queries to document sections and uploads results to Supabase.
- **LLM Integration**: Generates answers using Groq or local Ollama models.
- **PDF Reconstruction**: Creates a text-only PDF with headers and page numbers using ReportLab.
- **Cloud Storage**: Stores JSON and PDF outputs in Supabase with public URLs.

## Project Structure
- `api_server.py`: FastAPI server for document processing and query answering.
- `keyword_extractor.py`: Extracts query keywords using spaCy.
- `parser.py`: Parses PDFs and identifies headers/coverage keywords.
- `reconstruct.py`: Generates text-only PDFs with ReportLab.
- `semantic_matcher.py`: Matches queries to document blocks.
- `llm.py`: Queries local Ollama for answers.
- `supabase_client.py`: Manages Supabase uploads and URLs.
- `requirements.txt`: Lists project dependencies.

## Setup
### Prerequisites
- Python 3.8 or higher
- Supabase account with a `doc-processing` bucket
- `.env` file with:
  ```bash
  SUPABASE_URL=<your-supabase-url>
  SUPABASE_SERVICE_ROLE_KEY=<your-supabase-key>
  GROQ_API_KEY=<your-groq-api-key>
  FAL_API_KEY=<your-fal-api-key>
  # Optional overrides if your FAL endpoint or model name differ
  FAL_API_URL=https://fal.run/fal-ai/veo
  FAL_MODEL=veo-3
  ```
- (Optional) Local Ollama server for `llm.py`

### Installation
1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd core
   ```
2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   ```
 3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Download the required spaCy English model:
   ```bash
   python -m spacy download en_core_web_sm
   ```
5. (Optional) Run Ollama:
   ```bash
   ollama run llama3
   ```

### Video generation via FAL.ai
- The `/hackrx/generate_video` endpoint creates an 8-second clip from the chatbot conclusion using FAL.ai's hosted Veo 3-style video model.
- You need an API key with access to the model on FAL.ai. Set it in `FAL_API_KEY`.
- If your deployment uses a different FAL endpoint or model name, override `FAL_API_URL` and `FAL_MODEL` in `.env`.
- When running locally without internet access, video generation will fail with a 502/504 error that explains whether DNS/host lookup or timeout caused the problem.

## Usage
### API Server
1. Start the server:
   ```bash
   uvicorn api_server:app --reload
   ```
2. Open `/hackrx/run` in a browser (GET) to see an example payload, or send a POST request to `/hackrx/run`:
   ```json
   {
       "documents": "<PDF-URL>",
       "questions": ["What are the coverage exclusions?", "How are claims processed?"]
   }
   ```
   - **Header**: `Authorization: Bearer <token>`
   - **Response**: JSON with answers
  - **401 from Groq?** Ensure `GROQ_API_KEY` is set in `.env` and that the key has
    access to the configured model (default: `llama3-70b-8192`).

### LLM Script
1. Ensure `query_data.json` is available.
2. Run:
   ```bash
   python llm.py
   ```
   - Outputs answers using Ollama.

### Workflow
1. Upload a PDF to a public URL.
2. Query the API with the PDF URL and questions.
3. The system parses the PDF, matches queries, generates answers, and uploads results to Supabase.
4. Access answers and Supabase URLs.

## Future Implementations
To enhance CORE’s functionality and scalability, the following improvements are planned:

1. **Multi-Language and Multi-Format Support**: Extend PDF parsing to handle non-English documents and various PDF structures (e.g., scanned documents using OCR). This will involve integrating libraries like Tesseract for image-based PDFs and adding multilingual NLP models to spaCy for keyword extraction in languages such as Spanish, French, or Mandarin.

2. **Machine Learning for Header Detection**: Replace heuristic-based header detection with a machine learning model (e.g., a transformer-based classifier) trained on annotated PDF datasets. This will improve accuracy in identifying headers across diverse document layouts, accounting for variations in font styles, sizes, and formatting.

3. **Query Caching Mechanism**: Implement a caching layer (e.g., using Redis) to store frequently accessed PDF blocks and query results. This will reduce processing time for repeated queries and improve response times for large documents, especially in high-traffic API scenarios.

4. **Authentication for Supabase Uploads**: Add secure authentication for Supabase uploads using OAuth or JWT tokens to restrict access to authorized users. This will ensure data privacy and prevent unauthorized modifications to the `doc-processing` bucket.

