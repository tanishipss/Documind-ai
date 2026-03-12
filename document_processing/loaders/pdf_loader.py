from pypdf import PdfReader
import docx


def load_document(file):

    filename = file.name.lower()

    text = ""

    # ---------------- PDF ----------------
    if filename.endswith(".pdf"):

        reader = PdfReader(file)

        for page in reader.pages:

            page_text = page.extract_text()

            if page_text:
                text += page_text + "\n"

    # ---------------- DOCX ----------------
    elif filename.endswith(".docx"):

        document = docx.Document(file)

        for para in document.paragraphs:
            text += para.text + "\n"

    # ---------------- TXT ----------------
    elif filename.endswith(".txt"):

        text = file.read().decode("utf-8")

    # Clean text
    text = text.replace("\n\n", "\n")

    return text