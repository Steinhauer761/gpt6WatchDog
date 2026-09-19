FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TOR_SOCKS_PROXY=socks5://127.0.0.1:9050

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libimage-exiftool-perl \
    nmap \
    tesseract-ocr \
    tor \
    whois \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY backend /app/backend
COPY worker /app/worker

CMD ["sh", "-c", "mkdir -p /tmp/tor-data && chown -R debian-tor:debian-tor /tmp/tor-data && tor --RunAsDaemon 1 --User debian-tor --SocksPort 127.0.0.1:9050 --DataDirectory /tmp/tor-data --Log 'notice stdout' && uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
