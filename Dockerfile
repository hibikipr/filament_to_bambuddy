FROM python:3.14-slim

# The base image's own OS packages lag Debian's security patch cadence —
# util-linux (util-linux/mount/login/libuuid1/libsmartcols1/libmount1/
# liblastlog2-2/libblkid1/bsdutils, all built from the same source package)
# was flagged by CI's Trivy scan at 2.41-5 with several CVEs fixed in
# 2.41.3-1/2.41.5-0+deb13u1. Upgrading here (rather than waiting on the next
# python:3.14-slim rebuild) keeps every build current regardless of how
# stale the upstream base image's own OS layer is.
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

# Set at build time from the release git tag (see .github/workflows/docker-publish.yml);
# defaults to "dev" for a plain local `docker build` with no --build-arg.
ARG VERSION=dev

WORKDIR /app

# Deps first for layer caching. gunicorn serves the Flask app in production.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# App code
COPY app.py ofd.py filament_parse.py spoolmandb_community.py i18n.py ./
COPY templates ./templates
COPY static ./static

# Caches live on a mounted volume so they survive restarts.
ENV APP_VERSION=$VERSION \
    BARCODE_CACHE_FILE=/data/barcode_cache.json \
    OFD_CACHE_FILE=/data/ofd_index.json \
    SPOOLMANDB_COMMUNITY_CACHE_FILE=/data/spoolmandb_community_index.json \
    HOST=0.0.0.0 \
    PORT=8088
VOLUME ["/data"]
EXPOSE 8088

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8088/',timeout=4).status==200 else 1)"]

# One worker (shared in-memory OFD index) + threads for the blocking HTTP calls.
# --access-logfile - sends HTTP access logs to stdout so they appear in docker logs.
CMD ["gunicorn", "-b", "0.0.0.0:8088", "-w", "1", "--threads", "8", "--timeout", "120", "--access-logfile", "-", "app:app"]
