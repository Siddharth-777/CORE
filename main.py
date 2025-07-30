import fitz  # PyMuPDF
import json
import os
import nltk

# === Optional: Check/download NLTK tokenizer (only if you later want sentence splitting)
try:
    nltk.data.find("tokenizers/punkt")
except LookupError:
    nltk.download("punkt")

# === Ligature normalization map
def normalize_ligatures(text):
    ligature_map = {
        "ﬁ": "fi",
        "ﬂ": "fl",
        "ﬀ": "ff",
        "ﬃ": "ffi",
        "ﬄ": "ffl",
        "ﬅ": "ft",
        "ﬆ": "st",
    }
    for lig, replacement in ligature_map.items():
        text = text.replace(lig, replacement)
    return text

# === Main extraction function
def extract_semantic_blocks(pdf_path):
    doc = fitz.open(pdf_path)
    all_blocks = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        raw_text = page.get_text()

        # Normalize ligatures
        cleaned_text = normalize_ligatures(raw_text)

        # Split by paragraph (double newlines)
        paragraphs = [p.strip() for p in cleaned_text.split("\n\n") if p.strip()]

        for segment_idx, para in enumerate(paragraphs, start=1):
            all_blocks.append({
                "page": page_num + 1,
                "segment": segment_idx,
                "text": para
            })

    return all_blocks

# === Save as JSON
def save_blocks_to_json(blocks, output_file):
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(blocks, f, indent=2, ensure_ascii=False)
    print(f"✅ Extracted {len(blocks)} blocks and saved to {output_file}")

# === Main runner
if __name__ == "__main__":
    pdf_path = "research.pdf"  # ← input PDF path
    output_file = "semantic_blocks_with_embeddings_local.json"

    if not os.path.exists(pdf_path):
        print(f"❌ File not found: {pdf_path}")
    else:
        blocks = extract_semantic_blocks(pdf_path)
        save_blocks_to_json(blocks, output_file)
