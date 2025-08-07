import json
from keyword_extractor import extract_keywords
from supabase_client import upload_to_supabase, get_public_url
import tempfile

def match_blocks(paragraphs, query, bucket_name="doc-processing", upload_filename="json/query_data.json"):
    """
    Given a list of paragraph dicts and a query string:
    - Extracts keywords
    - Scores and ranks paragraphs
    - Uploads JSON results to Supabase
    - Returns matched blocks and public URL
    """
    keywords = extract_keywords(query)
    print("Extracted Keywords:", keywords)

    scored_blocks = []
    for block in paragraphs:
        text = block["text"].lower()
        match_score = sum(text.count(keyword) for keyword in keywords)
        if match_score > 0:
            scored_blocks.append((match_score, block))

    scored_blocks.sort(reverse=True, key=lambda x: x[0])
    matched_blocks = [block for score, block in scored_blocks]

    # Save to temp file & upload
    with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".json") as tmp:
        json.dump(matched_blocks, tmp, indent=2, ensure_ascii=False)
        tmp.flush()
        upload_to_supabase(bucket_name, tmp.name, upload_filename)

    public_url = get_public_url(bucket_name, upload_filename)

    print(f"\n✅ Found {len(matched_blocks)} matching blocks.")
    print(f"✅ Uploaded to Supabase: {upload_filename}")
    print(f"🔗 Public URL: {public_url}")

    return matched_blocks, public_url
