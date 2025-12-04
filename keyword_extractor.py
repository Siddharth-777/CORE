from functools import lru_cache
import spacy


@lru_cache(maxsize=1)
def get_nlp():
    """Load the spaCy model lazily and raise a clear error if missing."""
    try:
        return spacy.load("en_core_web_sm")
    except OSError as exc:
        raise RuntimeError(
            "SpaCy model 'en_core_web_sm' is not installed. "
            "Install it with `python -m spacy download en_core_web_sm`."
        ) from exc


def extract_keywords(query: str):
    nlp = get_nlp()
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
