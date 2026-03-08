# ─── Dockerfile for Cloud Run deployment ─────────────────────────────────────
# Build:  docker build -t moviefinder .
# Run:    docker run -p 8080:8080 moviefinder
# Deploy: gcloud run deploy moviefinder --source . --region europe-west6 \
#                  --allow-unauthenticated --port 8080

FROM python:3.11-slim

# Reduce image size and avoid bytecode clutter
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

# Install dependencies first (layer-cached)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Streamlit listens on $PORT; Cloud Run injects PORT=8080
EXPOSE 8080

CMD ["sh", "-c", "streamlit run app.py --server.port=$PORT --server.address=0.0.0.0 --server.headless=true"]
