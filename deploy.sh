#!/usr/bin/env bash
# deploy.sh — Build, push, and deploy Assignment 2 to Google Cloud Run
#
# Usage:
#   cd assignment_2
#   chmod +x deploy.sh
#   ./deploy.sh
#
# Prerequisites:
#   - gcloud CLI installed and authenticated (gcloud auth login)
#   - Docker installed and running
#   - Artifact Registry API enabled in your GCP project

set -euo pipefail

# ── Configuration — edit these before running ─────────────────────────────────
PROJECT_ID="${GCP_PROJECT:-gen-lang-client-0671890527}"
REGION="${REGION:-europe-west6}"
REPO="moviefinder"                    # Artifact Registry repository name
AR_HOST="${REGION}-docker.pkg.dev"

BACKEND_IMAGE="${AR_HOST}/${PROJECT_ID}/${REPO}/backend:latest"
FRONTEND_IMAGE="${AR_HOST}/${PROJECT_ID}/${REPO}/frontend:latest"

# Cloud Run service names
BACKEND_SERVICE="moviefinder-backend"
FRONTEND_SERVICE="moviefinder-frontend"

# ── Step 1: Enable required APIs ──────────────────────────────────────────────
echo "==> Enabling required GCP APIs..."
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  bigquery.googleapis.com \
  secretmanager.googleapis.com \
  --project="${PROJECT_ID}"

# ── Step 2: Create Artifact Registry repository (idempotent) ─────────────────
echo "==> Creating Artifact Registry repository (if not exists)..."
gcloud artifacts repositories describe "${REPO}" \
  --location="${REGION}" \
  --project="${PROJECT_ID}" 2>/dev/null \
|| gcloud artifacts repositories create "${REPO}" \
  --repository-format=docker \
  --location="${REGION}" \
  --project="${PROJECT_ID}"

# Configure Docker to push to Artifact Registry
gcloud auth configure-docker "${AR_HOST}" --quiet

# ── Step 3: Build and push backend ───────────────────────────────────────────
echo "==> Building backend Docker image..."
docker build --platform linux/amd64 -t "${BACKEND_IMAGE}" ./backend

echo "==> Pushing backend image to Artifact Registry..."
docker push "${BACKEND_IMAGE}"

# ── Step 4: Build and push frontend ──────────────────────────────────────────
echo "==> Building frontend Docker image..."
docker build --platform linux/amd64 -t "${FRONTEND_IMAGE}" ./frontend

echo "==> Pushing frontend image to Artifact Registry..."
docker push "${FRONTEND_IMAGE}"

# ── Step 5: Deploy backend to Cloud Run ──────────────────────────────────────
echo "==> Deploying backend to Cloud Run..."
gcloud run deploy "${BACKEND_SERVICE}" \
  --image="${BACKEND_IMAGE}" \
  --region="${REGION}" \
  --project="${PROJECT_ID}" \
  --platform=managed \
  --allow-unauthenticated \
  --port=8080 \
  --memory=512Mi \
  --cpu=1 \
  --timeout=120 \
  --update-secrets="TMDB_API_KEY=TMDB_API_KEY:latest,GCP_SA_JSON=GCP_SERVICE_ACCOUNT:latest,ES_API_KEY=ES_API_KEY:latest" \
  --set-env-vars="GCP_PROJECT=${PROJECT_ID},BQ_DATASET=${BQ_DATASET:-assignement_1},ES_URL=${ES_URL:-}"

# Retrieve the backend URL
BACKEND_URL=$(gcloud run services describe "${BACKEND_SERVICE}" \
  --region="${REGION}" \
  --project="${PROJECT_ID}" \
  --format="value(status.url)")

echo "==> Backend deployed at: ${BACKEND_URL}"

# ── Step 6: Deploy frontend to Cloud Run ─────────────────────────────────────
echo "==> Deploying frontend to Cloud Run..."
gcloud run deploy "${FRONTEND_SERVICE}" \
  --image="${FRONTEND_IMAGE}" \
  --region="${REGION}" \
  --project="${PROJECT_ID}" \
  --platform=managed \
  --allow-unauthenticated \
  --port=8501 \
  --memory=256Mi \
  --cpu=1 \
  --set-env-vars="BACKEND_URL=${BACKEND_URL}"

FRONTEND_URL=$(gcloud run services describe "${FRONTEND_SERVICE}" \
  --region="${REGION}" \
  --project="${PROJECT_ID}" \
  --format="value(status.url)")

echo "==> Frontend deployed at: ${FRONTEND_URL}"

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo "========================================================"
echo "  Deployment complete!"
echo "  Frontend : ${FRONTEND_URL}"
echo "  Backend  : ${BACKEND_URL}"
echo "========================================================"
echo ""
echo "Next steps:"
echo "  1. Update assignment_2/README.md with the URLs above."
echo "  2. Run 'python scripts/upload_data.py' to load data into BigQuery."
echo "  3. Run 'python train_model.py' to train the BigQuery ML model."
echo "  4. Run 'python backend/index_movies.py' to index movies into Elasticsearch."
