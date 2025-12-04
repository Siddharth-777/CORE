import json
import tempfile
from keyword_extractor import extract_keywords
from supabase_client import upload_to_supabase, get_public_url


def sanitize_text_for_json(text):
    if not isinstance(text, str):
        return text

    replacements = {
        '\x00': '', '\x01': '', '\x02': '', '\x03': '', '\x04': '',
        '\x05': '', '\x06': '', '\x07': '', '\x08': '', '\x0b': '',
        '\x0c': '', '\x0e': '', '\x0f': '', '\x10': '', '\x11': '',
        '\x12': '', '\x13': '', '\x14': '', '\x15': '', '\x16': '',
        '\x17': '', '\x18': '', '\x19': '', '\x1a': '', '\x1b': '',
        '\x1c': '', '\x1d': '', '\x1e': '', '\x1f': '',
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    text = ''.join(char for char in text if ord(char) >= 32 or char in '\t\n\r')

    return text


def sanitize_block_for_json(block):
    if isinstance(block, dict):
        return {key: sanitize_block_for_json(value) for key, value in block.items()}
    elif isinstance(block, list):
        return [sanitize_block_for_json(item) for item in block]
    elif isinstance(block, str):
        return sanitize_text_for_json(block)
    else:
        return block


def match_blocks(
    paragraphs,
    query,
    bucket_name="doc-processing",
    upload_filename="json/query_data.json",
    top_n=None,
    include_neighbors=False
):
    keywords = extract_keywords(query)
    print("Extracted Keywords:", keywords)

    scored_blocks = []
    for idx, block in enumerate(paragraphs):
        text = block["text"].lower()
        match_score = sum(text.count(keyword) for keyword in keywords)
        if match_score > 0:
            scored_blocks.append((match_score, idx, block))
    if not scored_blocks:
        print("⚠ No keyword matches found — using all parsed chunks as fallback.")
        scored_blocks = [(0, idx, block) for idx, block in enumerate(paragraphs)]
    scored_blocks.sort(reverse=True, key=lambda x: x[0])
    if top_n is not None:
        scored_blocks = scored_blocks[:top_n]

    matched_indices = {idx for _, idx, _ in scored_blocks}
    if include_neighbors:
        neighbor_indices = set()
        for idx in matched_indices:
            if idx - 1 >= 0:
                neighbor_indices.add(idx - 1)
            if idx + 1 < len(paragraphs):
                neighbor_indices.add(idx + 1)
        matched_indices |= neighbor_indices

    matched_blocks = [paragraphs[i] for i in sorted(matched_indices)]
    sanitized_blocks = [sanitize_block_for_json(block) for block in matched_blocks]
    with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".json", encoding='utf-8') as tmp:
        json.dump(sanitized_blocks, tmp, indent=2, ensure_ascii=False)
        tmp.flush()
        upload_to_supabase(bucket_name, tmp.name, upload_filename)

    public_url = get_public_url(bucket_name, upload_filename)
    print(f"\n✅ Found {len(matched_blocks)} matching blocks (including fallback if needed).")

    return matched_blocks, public_url
