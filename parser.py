import fitz  
import json
import os
import nltk
import unicodedata
import re
from collections import Counter
from supabase_client import upload_to_supabase
import tempfile
from supabase_client import upload_to_supabase

try:
    nltk.data.find("tokenizers/punkt")
except LookupError:
    nltk.download("punkt")

def normalize_unicode_text(text):
    normalization_map = {
        "ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl", "ﬅ": "ft", "ﬆ": "st",
        "Æ": "AE", "æ": "ae", "Œ": "OE", "œ": "oe", "Ĳ": "IJ", "ĳ": "ij", "ß": "ss",
        "Ł": "L", "ł": "l", "Đ": "D", "đ": "d", "Ø": "O", "ø": "o",
        "Þ": "Th", "þ": "th", "Ŋ": "N", "ŋ": "n", "Å": "A", "å": "a",
        "Ä": "A", "ä": "a", "Ö": "O", "ö": "o", "Ü": "U", "ü": "u",
        "Ñ": "N", "ñ": "n", "Ç": "C", "ç": "c", "É": "E", "é": "e",
        "È": "E", "è": "e", "Ê": "E", "ê": "e", "Ë": "E", "ë": "e",
        "Á": "A", "á": "a", "À": "A", "à": "a", "Â": "A", "â": "a",
        "Ã": "A", "ã": "a", "Í": "I", "í": "i", "Ì": "I", "ì": "i",
        "Î": "I", "î": "i", "Ï": "I", "ï": "i", "Ó": "O", "ó": "o",
        "Ò": "O", "ò": "o", "Ô": "O", "ô": "o", "Õ": "O", "õ": "o",
        "Ú": "U", "ú": "u", "Ù": "U", "ù": "u", "Û": "U", "û": "u",
        "Ý": "Y", "ý": "y", "Ÿ": "Y", "ÿ": "y", "Ž": "Z", "ž": "z",
        "Š": "S", "š": "s",
    }

    for src, tgt in normalization_map.items():
        text = text.replace(src, tgt)

    text = ''.join(
        c for c in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(c)
    )

    return text

def analyze_document_fonts_and_colors(blocks):
    font_sizes = []
    colors = []
    font_names = []
    
    for block in blocks:
        font_sizes.append(block['size'])
        colors.append(block.get('color', 0))
        font_names.append(block.get('font', ''))
    
    if not font_sizes:
        return {
            'most_common_size': 12,
            'most_common_color': 0,
            'header_size_threshold': 14,
            'size_distribution': {},
            'color_distribution': {},
            'font_distribution': {}
        }
    
    size_counter = Counter(font_sizes)
    most_common_size = size_counter.most_common(1)[0][0]
    
    color_counter = Counter(colors)
    most_common_color = color_counter.most_common(1)[0][0]
    
    font_counter = Counter(font_names)
    
    sorted_sizes = sorted(set(font_sizes), reverse=True)
    
    if len(sorted_sizes) > 1:
        header_candidates = [size for size in sorted_sizes if size > most_common_size]
        header_size_threshold = most_common_size + 1 if header_candidates else most_common_size
    else:
        header_size_threshold = most_common_size
    
    print(f"Font Analysis:")
    print(f"   Most common font size: {most_common_size}")
    print(f"   Most common color: {most_common_color}")
    print(f"   Header size threshold: {header_size_threshold}")
    print(f"   Font sizes found: {sorted(set(font_sizes))}")
    print(f"   Colors found: {set(colors)}")
    
    return {
        'most_common_size': most_common_size,
        'most_common_color': most_common_color,
        'header_size_threshold': header_size_threshold,
        'size_distribution': dict(size_counter),
        'color_distribution': dict(color_counter),
        'font_distribution': dict(font_counter),
        'all_sizes': sorted(set(font_sizes), reverse=True)
    }

def is_header_by_visual_properties(block, doc_stats):
    text = block['text'].strip()
    font_size = block['size']
    color = block.get('color', 0)
    font_name = block.get('font', '').lower()
    
    if len(text) < 3:
        return False
    
    score = 0
    
    if font_size > doc_stats['header_size_threshold']:
        score += 5
        print(f"   Size {font_size} > threshold {doc_stats['header_size_threshold']}: +5 points")
    elif font_size > doc_stats['most_common_size']:
        score += 3
        print(f"   Size {font_size} > common {doc_stats['most_common_size']}: +3 points")
    
    if color != doc_stats['most_common_color']:
        score += 3
        print(f"   Color {color} != common {doc_stats['most_common_color']}: +3 points")
    
    if font_name:
        if 'bold' in font_name or 'heavy' in font_name or 'black' in font_name:
            score += 4
            print(f"   Bold font '{font_name}': +4 points")
        elif 'italic' in font_name and len(text) < 100:
            score += 2
            print(f"   Italic font '{font_name}': +2 points")
    
    text_length = len(text)
    if text_length < 50:
        score += 2
        print(f"   Short text ({text_length} chars): +2 points")
    elif text_length < 100:
        score += 1
        print(f"   Medium text ({text_length} chars): +1 point")
    elif text_length > 300:
        score -= 2
        print(f"   Long text ({text_length} chars): -2 points")
    
    header_patterns = [
        r'^\d+\.',
        r'^\d+\.\d+',
        r'^[A-Z]\.',
        r'(?i)^(chapter|section|part|article|clause)\s+\d+',
        r'(?i)(cover|coverage|benefit|exclusion|definition|procedure)',
        r'(?i)(ambulance|emergency|medical|hospital|maternity)',
    ]
    
    for pattern in header_patterns:
        if re.search(pattern, text):
            score += 2
            print(f"   Pattern match '{pattern}': +2 points")
            break
    
    words = text.split()
    if len(words) > 1:
        capitalized_words = sum(1 for word in words if len(word) > 2 and word[0].isupper())
        if capitalized_words / len(words) > 0.6:
            score += 2
            print(f"   Title case ({capitalized_words}/{len(words)}): +2 points")
    
    if text.isupper() and len(text) > 4:
        score += 3
        print(f"   All caps: +3 points")
    
    false_positive_patterns = [
        r'(?i)(company|limited|ltd|inc|corporation)',
        r'(?i)(email|website|phone|address)',
        r'UIN:|CIN:|IRDAI',
        r'^\d{4,}',
    ]
    
    for pattern in false_positive_patterns:
        if re.search(pattern, text):
            score -= 5
            print(f"   False positive pattern: -5 points")
            break
    
    print(f"   Total score for '{text[:50]}...': {score}")
    
    return score >= 5

def analyze_coverage_keywords(text):
    text_lower = text.lower()
    
    inclusion_patterns = [
        (r'\b(will cover|covers|covered|coverage includes?|benefits? include|payable|reimbursable)\b', 'INCLUSION', 10),
        (r'\b(eligible|entitled|applicable|includes?|benefits?)\b', 'INCLUSION', 8),
        (r'\b(shall pay|we pay|payment|compensation)\b', 'INCLUSION', 9),
        (r'\b(provided|subject to)\b', 'CONDITION', 7),
    ]
    
    exclusion_patterns = [
        (r'\b(will not cover|does not cover|not covered|excludes?|exclusions?)\b', 'EXCLUSION', 10),
        (r'\b(not eligible|not entitled|not applicable|not payable|non-payable)\b', 'EXCLUSION', 9),
        (r'\b(shall not pay|we will not pay|no payment|no compensation)\b', 'EXCLUSION', 10),
        (r'\b(except|excepting|other than|but not|however|provided that)\b', 'EXCEPTION', 8),
        (r'\b(limitations?|restrictions?|conditions?)\b', 'LIMITATION', 7),
        (r'\b(waiting period|deductible|co-?pay|out of pocket)\b', 'LIMITATION', 6),
    ]
    
    special_patterns = [
        (r'\b(pre-?existing|pre-?condition)\b', 'PRE_EXISTING', 9),
        (r'\b(suicide|self-?harm|self-?inflicted)\b', 'SUICIDE_RELATED', 10),
        (r'\b(war|terrorism|nuclear|riot)\b', 'WAR_RELATED', 8),
        (r'\b(maternity|pregnancy|childbirth|delivery)\b', 'MATERNITY', 8),
        (r'\b(emergency|ambulance|hospitalization)\b', 'EMERGENCY', 8),
        (r'\b(claim|claims process|documentation)\b', 'CLAIMS', 7),
    ]
    
    flags = []
    max_priority = 0
    primary_classification = 'GENERAL'
    
    all_patterns = inclusion_patterns + exclusion_patterns + special_patterns
    
    for pattern, classification, priority in all_patterns:
        matches = re.findall(pattern, text_lower)
        if matches:
            flags.append({
                'type': classification,
                'priority': priority,
                'matches': matches,
                'pattern': pattern
            })
            if priority > max_priority:
                max_priority = priority
                primary_classification = classification
    
    return {
        'flags': flags,
        'max_priority': max_priority,
        'primary_classification': primary_classification,
        'has_coverage_keywords': len(flags) > 0
    }

def create_coverage_flag_text(coverage_analysis, original_text):
    if not coverage_analysis['has_coverage_keywords']:
        return original_text
    
    priority = coverage_analysis['max_priority']
    classification = coverage_analysis['primary_classification']
    
    flag_map = {
        'INCLUSION': 'COVERS',
        'EXCLUSION': 'EXCLUDES', 
        'EXCEPTION': 'EXCEPTION',
        'LIMITATION': 'LIMITATION',
        'CONDITION': 'CONDITION',
        'PRE_EXISTING': 'PRE-EXISTING',
        'SUICIDE_RELATED': 'SUICIDE',
        'WAR_RELATED': 'WAR/TERRORISM',
        'MATERNITY': 'MATERNITY',
        'EMERGENCY': 'EMERGENCY',
        'CLAIMS': 'CLAIMS',
        'GENERAL': 'GENERAL'
    }
    
    flag = flag_map.get(classification, 'GENERAL')
    priority_indicator = "HIGH PRIORITY" if priority >= 9 else "MEDIUM PRIORITY" if priority >= 7 else "LOW PRIORITY"
    
    flagged_text = f"[{flag}] [{priority_indicator}]\n{original_text}"
    
    return flagged_text

def extract_formatted_blocks(pdf_path):
    doc = fitz.open(pdf_path)
    all_blocks = []
    
    temp_blocks = []
    
    for page_num, page in enumerate(doc, start=1):
        blocks = page.get_text("dict")["blocks"]

        for b in blocks:
            if b['type'] != 0:
                continue  

            paragraph_lines = []
            full_text = ""
            fonts = []
            sizes = []
            colors = []

            for line in b["lines"]:
                line_text = ""
                line_y = line["bbox"][1]

                for span in line["spans"]:
                    text = normalize_unicode_text(span["text"])
                    line_text += text
                    fonts.append(span.get("font", ""))
                    sizes.append(span.get("size", 12))
                    colors.append(span.get("color", 0))

                if line_text.strip():
                    paragraph_lines.append({
                        "text": line_text.strip(),
                        "y": line_y
                    })
                    full_text += line_text + "\n"

            if full_text.strip():
                most_common_font = max(set(fonts), key=fonts.count) if fonts else None
                most_common_size = max(set(sizes), key=sizes.count) if sizes else 12
                most_common_color = max(set(colors), key=colors.count) if colors else 0
                
                temp_blocks.append({
                    "page": page_num,
                    "bbox": b["bbox"], 
                    "font": most_common_font,
                    "size": most_common_size,
                    "color": most_common_color,
                    "lines": paragraph_lines,
                    "text": full_text.strip(),
                    "y_position": b["bbox"][1]
                })
    
    doc_stats = analyze_document_fonts_and_colors(temp_blocks)
    
    current_header = "[Document Start]"
    header_hierarchy = ["Document Start"]
    
    print(f"\nAnalyzing {len(temp_blocks)} blocks for headers and coverage keywords...")
    
    for i, block in enumerate(temp_blocks):
        original_text = block['text']
        print(f"\nBlock {i+1}: '{original_text[:50]}...'")
        
        coverage_analysis = analyze_coverage_keywords(original_text)
        
        is_header = is_header_by_visual_properties(block, doc_stats)
        
        if is_header:
            current_header_text = original_text.strip()
            current_header = f"[{current_header_text}]"
            
            print(f"IDENTIFIED AS HEADER: {current_header}")
            
            current_size = block['size']
            if len(header_hierarchy) > 1:
                if i > 0:
                    prev_blocks = [b for b in temp_blocks[:i] if b.get('is_header')]
                    if prev_blocks:
                        prev_header_size = prev_blocks[-1]['size']
                        if current_size > prev_header_size:
                            header_hierarchy = [current_header_text]
                        elif current_size < prev_header_size:
                            header_hierarchy.append(current_header_text)
                        else:
                            header_hierarchy[-1] = current_header_text
                    else:
                        header_hierarchy = [current_header_text]
                else:
                    header_hierarchy = [current_header_text]
            else:
                header_hierarchy = [current_header_text]
            
            hierarchical_header = "[" + " > ".join(header_hierarchy) + "]"
            
            block["is_header"] = True
            block["header"] = hierarchical_header
            block["header_level"] = len(header_hierarchy)
            block["direct_header"] = current_header
            block["text"] = current_header
            
            block["coverage_analysis"] = coverage_analysis
            block["coverage_flags"] = coverage_analysis['flags']
            block["coverage_priority"] = coverage_analysis['max_priority']
            block["coverage_classification"] = coverage_analysis['primary_classification']
            
        else:
            hierarchical_header = "[" + " > ".join(header_hierarchy) + "]"
            block["is_header"] = False
            block["header"] = hierarchical_header
            block["header_level"] = len(header_hierarchy)
            block["direct_header"] = f"[{header_hierarchy[-1]}]" if header_hierarchy else "[Document Start]"
            
            block["coverage_analysis"] = coverage_analysis
            block["coverage_flags"] = coverage_analysis['flags']
            block["coverage_priority"] = coverage_analysis['max_priority']
            block["coverage_classification"] = coverage_analysis['primary_classification']
            
            if coverage_analysis['has_coverage_keywords']:
                flagged_text = create_coverage_flag_text(coverage_analysis, original_text)
                block["flagged_text"] = flagged_text
                print(f"COVERAGE KEYWORDS DETECTED:")
                print(f"   Classification: {coverage_analysis['primary_classification']}")
                print(f"   Priority: {coverage_analysis['max_priority']}")
                print(f"   Flags: {[f['type'] + ':' + str(f['matches']) for f in coverage_analysis['flags']]}")
                print(f"   Flagged as: {flagged_text.split('\\n')[0]}")
            else:
                block["flagged_text"] = original_text
                
            print(f"Regular content under: {block['direct_header']}")
        
        all_blocks.append(block)

    headers_found = [b for b in all_blocks if b.get('is_header')]
    coverage_blocks = [b for b in all_blocks if b.get('coverage_analysis', {}).get('has_coverage_keywords', False)]
    high_priority_blocks = [b for b in all_blocks if b.get('coverage_priority', 0) >= 9]
    
    print(f"\nSUMMARY:")
    print(f"   Total blocks: {len(all_blocks)}")
    print(f"   Headers found: {len(headers_found)}")
    print(f"   Coverage-related blocks: {len(coverage_blocks)}")
    print(f"   High priority coverage blocks: {len(high_priority_blocks)}")
    
    print(f"\nHEADERS FOUND:")
    for header in headers_found:
        print(f"   - {header['text']} (size: {header['size']}, color: {header.get('color', 0)})")
    
    print(f"\nHIGH PRIORITY COVERAGE BLOCKS:")
    for block in high_priority_blocks:
        classification = block.get('coverage_classification', 'UNKNOWN')
        priority = block.get('coverage_priority', 0)
        text_preview = block['text'][:100].replace('\n', ' ')
        print(f"   - [{classification}] (Priority: {priority}) {text_preview}...")
    
    return all_blocks

def save_blocks_to_json(blocks):
    # Save to temp file (not to disk)
    with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".json") as tmp:
        json.dump(blocks, tmp, indent=2, ensure_ascii=False)
        tmp.flush()
        upload_to_supabase("doc-processing", tmp.name, "json/reconstructed_paragraphs.json")