"""
Worker que procesa PDFs en un proceso separado usando pdfminer.six
pdfminer NO procesa imágenes, solo texto - mucho más eficiente en memoria.
"""
import sys
import json
from io import StringIO

# Usar pdfminer.six en lugar de PyMuPDF
from pdfminer.high_level import extract_text_to_fp
from pdfminer.layout import LAParams
from pdfminer.pdfpage import PDFPage

MAX_PAGES = 50
MAX_CHARS_PER_PAGE = 20000


def count_pages(pdf_path: str) -> int:
    """Cuenta páginas del PDF sin cargar todo en memoria"""
    try:
        with open(pdf_path, 'rb') as f:
            return len(list(PDFPage.get_pages(f)))
    except:
        return 0


def extract_text_pdfminer(pdf_path: str) -> dict:
    """Extrae texto usando pdfminer.six - más eficiente en memoria"""
    try:
        total_pages = count_pages(pdf_path)
        pages_to_process = min(total_pages, MAX_PAGES)

        pages_data = []

        # Extraer texto página por página
        for page_num in range(pages_to_process):
            output = StringIO()
            laparams = LAParams()

            with open(pdf_path, 'rb') as f:
                # Extraer solo una página a la vez
                extract_text_to_fp(
                    f,
                    output,
                    page_numbers=[page_num],
                    laparams=laparams,
                    maxpages=1
                )

            text = output.getvalue().strip()
            output.close()

            if text:
                # Limitar texto por página
                text = text[:MAX_CHARS_PER_PAGE]
                pages_data.append({
                    "page_number": page_num + 1,
                    "text": text
                })

        return {
            "success": True,
            "pages": pages_data,
            "total_pages": total_pages,
            "processed_pages": len(pages_data)
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "error": "No PDF path provided"}))
        sys.exit(1)

    pdf_path = sys.argv[1]
    result = extract_text_pdfminer(pdf_path)
    print(json.dumps(result))
