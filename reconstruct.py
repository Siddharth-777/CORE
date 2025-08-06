import json
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.pdfbase.pdfmetrics import stringWidth

INPUT_JSON = "reconstructed_paragraphs.json"
OUTPUT_PDF = "reconstructed_paragraphs.pdf"
PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN = inch * 0.75
LINE_HEIGHT = 14
FONT_NAME = "Helvetica"
FONT_BOLD = "Helvetica-Bold"
FONT_SIZE = 11
TITLE_SIZE = 13
MAX_WIDTH = PAGE_WIDTH - 2 * MARGIN

with open(INPUT_JSON, "r", encoding="utf-8") as f:
    blocks = json.load(f)

c = canvas.Canvas(OUTPUT_PDF, pagesize=A4)
x_start = MARGIN
y = PAGE_HEIGHT - MARGIN
c.setFont(FONT_NAME, FONT_SIZE)

current_page = 1

def wrap_text(text, font, size, max_width):
    words = text.split()
    lines, line = [], ""
    for word in words:
        test_line = f"{line} {word}".strip()
        if stringWidth(test_line, font, size) <= max_width:
            line = test_line
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines

def draw_page_number(page_num):
    page_text = f"{page_num}"
    text_width = stringWidth(page_text, FONT_NAME, FONT_SIZE)
    x_center = (PAGE_WIDTH - text_width) / 2
    c.setFont(FONT_NAME, FONT_SIZE)
    c.drawString(x_center, MARGIN / 2, page_text)

for idx, block in enumerate(blocks):
    block_page = block.get("page", current_page)
    if block_page != current_page:
        draw_page_number(current_page)
        c.showPage()
        c.setFont(FONT_NAME, FONT_SIZE)
        y = PAGE_HEIGHT - MARGIN
        current_page = block_page

    text = block["text"].strip()
    if not text:
        continue

    is_title = len(text) < 80 and (text.istitle() or text.isupper())
    font = FONT_BOLD if is_title else FONT_NAME
    size = TITLE_SIZE if is_title else FONT_SIZE
    lines = wrap_text(text, font, size, MAX_WIDTH)

    for line in lines:
        if y < MARGIN + LINE_HEIGHT:
            draw_page_number(current_page)
            c.showPage()
            c.setFont(FONT_NAME, FONT_SIZE)
            y = PAGE_HEIGHT - MARGIN
            current_page = block_page
            if is_title:
                c.setFont(FONT_BOLD, TITLE_SIZE)

        c.setFont(font, size)
        c.drawString(x_start, y, line)
        y -= LINE_HEIGHT + (2 if is_title else 0)

    y -= LINE_HEIGHT  

draw_page_number(current_page)
c.save()
print(f"Text-only PDF saved as: {OUTPUT_PDF}")