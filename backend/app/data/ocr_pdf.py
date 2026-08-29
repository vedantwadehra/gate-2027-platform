"""OCR a scanned GATE CS PDF: render pages with pdftoppm, run tesseract, return text.

Usage: python3 ocr_pdf.py <pdf_path> [--dpi 300]
Requires: pdftoppm (poppler) and tesseract on PATH.
"""
import sys
import os
import tempfile
import subprocess
import re


def ocr_pdf(path: str, dpi: int = 300) -> str:
    tmp = tempfile.mkdtemp(prefix="ocr_")
    base = os.path.join(tmp, "page")
    subprocess.run(["pdftoppm", "-r", str(dpi), "-png", path, base],
                   check=True, capture_output=True)
    pages = sorted(os.path.join(tmp, f) for f in os.listdir(tmp) if f.endswith(".png"))
    out = []
    for pg in pages:
        r = subprocess.run(["tesseract", pg, "stdout", "-l", "eng"],
                           capture_output=True, text=True)
        out.append(r.stdout)
    return "\n".join(out)


if __name__ == "__main__":
    path = sys.argv[1]
    dpi = 300
    if "--dpi" in sys.argv:
        dpi = int(sys.argv[sys.argv.index("--dpi") + 1])
    txt = ocr_pdf(path, dpi)
    print(f"chars={len(txt)}")
    # show answer-key region if present
    m = re.search(r"Q\.?\s*No\.?\s*Type|Key/Range|Key\s+Marks", txt)
    print("key-region found:", bool(m))
    print(txt[:600])
