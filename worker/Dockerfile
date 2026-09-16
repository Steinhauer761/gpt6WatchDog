FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TOR_SOCKS_PROXY=socks5://127.0.0.1:9050

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates \
      tor \
      ffmpeg \
      nmap \
      whois \
      tesseract-ocr \
      libimage-exiftool-perl \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 10001 watchdog
WORKDIR /app

COPY worker/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY worker/ /app/

RUN mkdir -p /tmp/watchdog-tor && chown -R watchdog:watchdog /app /tmp/watchdog-tor
USER watchdog

EXPOSE 10000
CMD ["sh", "-c", "tor --RunAsDaemon 1 --SocksPort 9050 --DataDirectory /tmp/watchdog-tor && exec uvicorn app:app --host 0.0.0.0 --port ${PORT:-10000}"]
