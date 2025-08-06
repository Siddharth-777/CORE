import json
from keyword_extractor import extract_keywords

INPUT_PARAGRAPHS = "reconstructed_paragraphs.json"
OUTPUT_MATCHED = "query_data.json"

with open(INPUT_PARAGRAPHS, "r", encoding="utf-8") as f:
    paragraphs = json.load(f)

query = "How does the Transformer architecture enable better parallelization compared to RNNs and CNNs?"

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

with open(OUTPUT_MATCHED, "w", encoding="utf-8") as f:
    json.dump(matched_blocks, f, indent=2, ensure_ascii=False)

print(f"\nFound {len(matched_blocks)} matching blocks.")
print(f"Saved to: {OUTPUT_MATCHED}")