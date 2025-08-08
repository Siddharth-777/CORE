import json
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from supabase_client import upload_to_supabase, get_public_url
import tempfile
import pickle

def match_blocks(paragraphs, query, bucket_name="doc-processing", upload_filename="json/query_data.json", cache_embeddings=False):
    """
    Given a list of paragraph dicts and a query string:
    - Generates or loads cached embeddings
    - Scores and ranks paragraphs based on semantic similarity
    - Uploads JSON results to Supabase
    - Returns matched blocks and public URL
    """
    model = SentenceTransformer('all-MiniLM-L6-v2')
    paragraph_texts = [block["text"] for block in paragraphs]

    # Check for cached embeddings
    embedding_cache_file = f"embeddings/{upload_filename.replace('json/', '')}.pkl"
    if cache_embeddings and os.path.exists(embedding_cache_file):
        with open(embedding_cache_file, 'rb') as f:
            paragraph_embeddings = pickle.load(f)
    else:
        # Encode in batches for efficiency
        paragraph_embeddings = model.encode(paragraph_texts, batch_size=32, convert_to_tensor=False)
        if cache_embeddings:
            os.makedirs(os.path.dirname(embedding_cache_file), exist_ok=True)
            with open(embedding_cache_file, 'wb') as f:
                pickle.dump(paragraph_embeddings, f)

    query_embedding = model.encode([query], convert_to_tensor=False)[0]
    similarities = cosine_similarity([query_embedding], paragraph_embeddings)[0]
    scored_blocks = [(score, block) for score, block in zip(similarities, paragraphs) if score > 0.1]
    scored_blocks.sort(reverse=True, key=lambda x: x[0])
    matched_blocks = [block for score, block in scored_blocks]

    with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".json") as tmp:
        json.dump(matched_blocks, tmp, indent=2, ensure_ascii=False)
        tmp.flush()
        upload_to_supabase(bucket_name, tmp.name, upload_filename)

    public_url = get_public_url(bucket_name, upload_filename)
    print(f"\nFound {len(matched_blocks)} matching blocks.")
    return matched_blocks, public_url
