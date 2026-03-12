import re

def chunk_text(text, max_words=400, overlap=50):
    # Split on sentence boundaries instead of arbitrary word count
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    
    chunks = []
    current_words = []
    
    for sentence in sentences:
        words = sentence.split()
        
        if len(current_words) + len(words) > max_words and current_words:
            chunks.append(" ".join(current_words))
            # Overlap: keep last N words for context continuity
            current_words = current_words[-overlap:]
        
        current_words.extend(words)
    
    if current_words:
        chunks.append(" ".join(current_words))
    
    return chunks