# SpecWeft backend for the Forge app (Forge Remote). Serve behind HTTPS (most hosts terminate TLS for you).
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY specweft ./specweft
COPY scripts ./scripts
ENV SPECWEFT_DB=/data/specweft.db
# Hugging Face Spaces runs the container as a non-root user (uid 1000): keep /data writable for it
RUN mkdir -p /data && chmod 777 /data
VOLUME ["/data"]
EXPOSE 8765
# SPECWEFT_FORGE_APP_ID must be set at runtime (ari:cloud:ecosystem::app/<uuid> from `forge register`)
CMD ["python", "-m", "specweft.cli", "serve", "--host", "0.0.0.0", "--port", "8765"]
