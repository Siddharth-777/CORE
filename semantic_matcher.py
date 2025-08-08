import json
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from supabase_client import upload_to_supabase, get_public_url
import tempfile

def match_blocks(paragraphs, query, bucket_name="doc-processing", upload_filename="json/query_data.json"):
    """
    Given a list of paragraph dicts and a query string:
    - Generates embeddings using a pre-trained transformer model
    - Scores and ranks paragraphs based on semantic similarity
    - Uploads JSON results to Supabase
    - Returns matched blocks and public URL
    """
    # Load pre-trained sentence transformer model
    model = SentenceTransformer('all-MiniLM-L6-v2')

    # Extract paragraph texts and compute embeddings
    paragraph_texts = [block["text"] for block in paragraphs]
    paragraph_embeddings = model.encode(paragraph_texts, convert_to_tensor=False)
    
    # Compute query embedding
    query_embedding = model.encode([query], convert_to_tensor=False)[0]

    # Compute cosine similarity between query and paragraphs
    similarities = cosine_similarity([query_embedding], paragraph_embeddings)[0]

    # Pair similarities with blocks and filter out low-similarity matches
    scored_blocks = [(score, block) for score, block in zip(similarities, paragraphs) if score > 0.3]
    
    # Sort by similarity score in descending order
    scored_blocks.sort(reverse=True, key=lambda x: x[0])
    matched_blocks = [block for score, block in scored_blocks]

    # Save results to temporary JSON file
    with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".json") as tmp:
        json.dump(matched_blocks, tmp, indent=2, ensure_ascii=False)
        tmp.flush()
        upload_to_supabase(bucket_name, tmp.name, upload_filename)

    # Get public URL for uploaded file
    public_url = get_public_url(bucket_name, upload_filename)

    print(f"\nFound {len(matched_blocks)} matching blocks.")

    return matched_blocks, public_url
