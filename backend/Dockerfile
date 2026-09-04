FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# tesseract powers chat image OCR; poppler is dev-only (ocr_pdf.py) so not installed.
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

# Build context is the repo root (Render), so reference backend/ paths.
COPY backend/requirements.txt ./
RUN pip install -r requirements.txt

COPY backend/app ./app

EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
