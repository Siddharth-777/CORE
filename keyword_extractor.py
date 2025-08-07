import spacy
from spacy.cli import download

# Automatically download model if not present
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    download("en_core_web_sm")
    nlp = spacy.load("en_core_web_sm")

def extract_keywords(query: str):
    doc = nlp(query)
    keywords = set()

    for chunk in doc.noun_chunks:
        if len(chunk.text) > 2:
            keywords.add(chunk.text.lower())

    for ent in doc.ents:
        if len(ent.text) > 2:
            keywords.add(ent.text.lower())

    for token in doc:
        if not token.is_stop and token.is_alpha and len(token.text) > 2:
            keywords.add(token.text.lower())

    return sorted(keywords)
