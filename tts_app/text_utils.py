import re

def detect_language(text: str) -> str:
    """
    Ratio-based language detection.
    If >20% of alphabetic chars are Devanagari → Hindi, else English.
    Handles mixed Hindi+English (Hinglish) correctly.
    """
    devanagari  = len(re.findall(r'[\u0900-\u097F]', text))
    total_alpha = len(re.findall(r'[A-Za-z\u0900-\u097F]', text))
    if total_alpha == 0:
        return "en"
    return "hi" if (devanagari / total_alpha) > 0.2 else "en"


def normalize_text_for_tts(text: str) -> str:
    """
    Safe text normalisation — only expands genuine ALL-CAPS acronyms.
    Cleans up characters that cause XTTS to hallucinate or stutter.
    """
    def expand_acronym(match):
        return ' '.join(list(match.group(0)))

    # 1. Expand acronyms safely (ALL-CAPS words only)
    text = re.sub(r'\b[A-Z]{2,}\b', expand_acronym, text)

    # 2. Remove brackets and quotes that cause XTTS to make unnecessary clicking/pauses
    text = re.sub(r'["\'\(\)\[\]{}]', '', text)

    # 3. Prevent stuttering by collapsing multiple periods or dandas into one
    text = re.sub(r'\.{2,}', '.', text)
    text = re.sub(r'[।\u0964]{2,}', '।', text)

    # 4. Normalise whitespace
    text = ' '.join(text.split())
    return text


def smart_chunk_text(text: str, max_chars: int = 220) -> list:
    """
    Sentence-aware chunking.
    - Prefers sentence boundaries (.!?।)
    - Falls back to comma/semicolon splits
    - Hard word-wraps only as last resort
    - Always filters empty chunks (empty strings crash XTTS silently)
    """
    text = ' '.join(text.split())
    if not text:
        return []

    sentences = re.split(r'(?<=[.!?।\u0964])\s+', text)
    chunks, current = [], ""

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        if len(sentence) > max_chars:
            sub_parts = re.split(r'(?<=[,;:\-])\s+', sentence)
            for part in sub_parts:
                part = part.strip()
                if not part:
                    continue
                if len(part) > max_chars:
                    while len(part) > max_chars:
                        split_at = part.rfind(' ', 0, max_chars)
                        if split_at == -1:
                            split_at = max_chars
                        piece = part[:split_at].strip()
                        if piece:
                            chunks.append(piece)
                        part = part[split_at:].strip()
                    if part:
                        chunks.append(part)
                else:
                    if len(current) + 1 + len(part) <= max_chars:
                        current = (current + " " + part).strip()
                    else:
                        if current:
                            chunks.append(current)
                        current = part
        else:
            if len(current) + 1 + len(sentence) <= max_chars:
                current = (current + " " + sentence).strip()
            else:
                if current:
                    chunks.append(current)
                current = sentence

    if current:
        chunks.append(current)

    return [c for c in chunks if c.strip()]