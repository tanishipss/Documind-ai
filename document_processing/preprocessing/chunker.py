import re

def chunk_text(text, max_words=150, overlap=20):
    if not text or not text.strip():
        return []

    sentences = re.split(r'(?<=[.!?])\s+', text.strip())

    chunks = []
    current_words = []

    for sentence in sentences:
        words = sentence.split()

        if len(current_words) + len(words) > max_words and current_words:
            chunk = " ".join(current_words)
            if len(chunk.strip()) > 20:
                chunks.append(chunk)
            current_words = current_words[-overlap:]

        current_words.extend(words)

    if current_words:
        chunk = " ".join(current_words)
        if len(chunk.strip()) > 20:
            chunks.append(chunk)

    return chunks