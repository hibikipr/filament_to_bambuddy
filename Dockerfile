FROM python:3.12-slim

WORKDIR /app

# Deps first for layer caching. gunicorn serves the Flask app in production.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# App code
COPY app.py ofd.py filament_parse.py ./
COPY templates ./templates
COPY static ./static

# Caches live on a mounted volume so they survive restarts.
ENV BARCODE_CACHE_FILE=/data/barcode_cache.json \
    OFD_CACHE_FILE=/data/ofd_index.json \
    HOST=0.0.0.0 \
    PORT=8088
VOLUME ["/data"]
EXPOSE 8088

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8088/',timeout=4).status==200 else 1)"

# One worker (shared in-memory OFD index) + threads for the blocking HTTP calls.
CMD ["gunicorn", "-b", "0.0.0.0:8088", "-w", "1", "--threads", "8", "--timeout", "120", "app:app"]
