import json
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
import textwrap

# === Settings ===
INPUT_JSON = "semantic_blocks_with_embeddings_local.json"
OUTPUT_PDF = "reconstructed_paragraphs.pdf"
PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN = inch * 0.75
LINE_HEIGHT = 14
WRAP_WIDTH = 100  # characters per line approx

# === Load blocks ===
with open(INPUT_JSON, "r", encoding="utf-8") as f:
    blocks = json.load(f)

# === Setup canvas ===
c = canvas.Canvas(OUTPUT_PDF, pagesize=A4)
width, height = A4
x = MARGIN
y = PAGE_HEIGHT - MARGIN

c.setFont("Helvetica", 11)

for block in blocks:
    text = block["text"].strip()
    if not text:
        continue

    # Word wrap
    lines = textwrap.wrap(text, WRAP_WIDTH)

    for line in lines:
        if y < MARGIN + LINE_HEIGHT:
            c.showPage()
            c.setFont("Helvetica", 11)
            y = PAGE_HEIGHT - MARGIN
        c.drawString(x, y, line)
        y -= LINE_HEIGHT

    # Draw separator
    y -= LINE_HEIGHT
    if y < MARGIN + LINE_HEIGHT:
        c.showPage()
        c.setFont("Helvetica", 11)
        y = PAGE_HEIGHT - MARGIN

    c.drawString(x, y, "---")
    y -= LINE_HEIGHT * 2  # space after separator

# === Finalize PDF ===
c.save()
print(f"✅ PDF saved as: {OUTPUT_PDF}")
