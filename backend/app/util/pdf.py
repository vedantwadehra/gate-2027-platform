"""Minimal dependency-free PDF writer (text only) for result exports.

Produces a valid single/multi-page PDF using the built-in Helvetica font.
No external libraries required.
"""

PAGE_W = 612
PAGE_H = 792
TOP = 750
BOTTOM = 50
LEADING = 16
FONT_SIZE = 11


def _esc(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _build_content(lines: list[str]) -> str:
    parts = [
        "BT",
        f"/F1 {FONT_SIZE} Tf",
        "1 0 0 1 40 %d Tm" % TOP,
        "%g TL" % LEADING,
    ]
    for ln in lines:
        parts.append("(%s) Tj" % _esc(ln[:120]))
        parts.append("T*")
    parts.append("ET")
    return "\n".join(parts)


def make_pdf(lines: list[str], title: str = "") -> bytes:
    full = ([title, ""] if title else []) + lines
    per_page = max(1, int((TOP - BOTTOM) / LEADING))
    pages = [full[i : i + per_page] for i in range(0, len(full), per_page)] or [[""]]

    n_pages = len(pages)
    page_ids = [4 + i for i in range(n_pages)]
    content_ids = [4 + n_pages + i for i in range(n_pages)]

    objects: list[str] = []
    objects.append("<< /Type /Catalog /Pages 3 0 R >>")  # 1
    kids = " ".join(f"{pid} 0 R" for pid in page_ids)
    objects.append("<< /Type /Pages /Kids [%s] /Count %d >>" % (kids, n_pages))  # 2
    objects.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")  # 3
    for i in range(n_pages):
        objects.append(
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %d %d] "
            "/Resources << /Font << /F1 3 0 R >> >> /Contents %d 0 R >>"
            % (PAGE_W, PAGE_H, content_ids[i])
        )
    for i in range(n_pages):
        stream = _build_content(pages[i])
        objects.append("<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream))

    pdf = "%PDF-1.4\n"
    offsets: list[int] = []
    for idx, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf += "%d 0 obj\n%s\nendobj\n" % (idx, obj)
    xref_pos = len(pdf)
    pdf += "xref\n0 %d\n" % (len(objects) + 1)
    pdf += "0000000000 65535 f \n"
    for off in offsets:
        pdf += "%010d 00000 n \n" % off
    pdf += "trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF" % (
        len(objects) + 1,
        xref_pos,
    )
    return pdf.encode("latin-1", "replace")
