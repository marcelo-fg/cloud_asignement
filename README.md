# Movie Explorer — Cloud & Advanced Analytics Assignment 1

A Streamlit web application that queries a **Google BigQuery** movie database with dynamic SQL filters, and enriches results with movie posters, overviews, and cast information from **The Movie Database (TMDB) API**.

## Live Demo

> **[https://movie-app-262418330780.europe-west6.run.app](https://movie-app-262418330780.europe-west6.run.app)**

Deployed on **Google Cloud Run** (europe-west6 / Zürich) — publicly accessible, no login required.

---



## Architecture

```
app.py              ← Streamlit UI + logic layer
├── db.py           ← BigQuery client + query runner (prints SQL + exec time to terminal)
├── query_builder.py ← Pure SQL builder functions (no BigQuery calls)
└── tmdb.py         ← TMDB API fetch + caching
```

---

## Features

| Feature | SQL Implementation |
|---|---|
| Title autocomplete | `WHERE LOWER(title) LIKE LOWER('%query%') LIMIT 10` |
| Language filter | `WHERE language = 'en'` |
| Genre filter (pipe-separated) | `WHERE genres LIKE 'Action|%' OR genres LIKE '%|Action|%' ...` |
| Avg. rating filter | `JOIN ratings GROUP BY … HAVING AVG(rating) >= threshold` |
| Release year filter | `WHERE release_year >= 2000` |
| Advanced combos | All filters combined with `AND` clauses dynamically |
| SQL transparency | Printed to terminal (with exec time) + shown in UI expander |
| Movie details | TMDB API: poster, tagline, overview, cast (top 4) |
| Charts | Genre distribution (bar) + movies per year (line) |

---

## BigQuery Tables

```
assignement_1.movies  — movieId, title, genres, tmdbId, language, release_year, country
assignement_1.ratings — userId, movieId, rating, timestamp
```

**Project:** `gen-lang-client-0671890527`

---

## Local Development

### Prerequisites
- Python 3.11+
- Google Cloud project with BigQuery enabled
- [TMDB API key](https://www.themoviedb.org/settings/api) (free)

### Install
```bash
git clone <your-repo-url>
cd cloud_asignement
pip install -r requirements.txt
```

### Configure Secrets

Create `.streamlit/secrets.toml`:

```toml
TMDB_API_KEY = "your-tmdb-api-key"

[gcp_service_account]
type = "service_account"
project_id = "your-gcp-project-id"
private_key_id = "..."
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "...@....iam.gserviceaccount.com"
client_id = "..."
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "..."
```

Or use **Application Default Credentials**:
```bash
gcloud auth application-default login
gcloud config set project your-project-id
```

### Run
```bash
streamlit run app.py
```
Open [http://localhost:8501](http://localhost:8501)

---

## 🐳 Docker

### Build & Run Locally
```bash
docker build -t movie-app .
docker run -p 8080:8080 \
  -e TMDB_API_KEY="your-tmdb-key" \
  -e GCP_SA_JSON='{"type":"service_account",...}' \
  movie-app
```
Open [http://localhost:8080](http://localhost:8080)

---

## Cloud Run Deployment

Secrets are stored in **Google Secret Manager** — no env vars with plain-text credentials needed.

### First deploy (setup once)

```bash
# 1. Enable Secret Manager API
gcloud services enable secretmanager.googleapis.com --project=gen-lang-client-0671890527

# 2. Create the secrets
echo -n "YOUR_TMDB_API_KEY" | gcloud secrets create TMDB_API_KEY --data-file=- --replication-policy=automatic
cat your-service-account.json | gcloud secrets create GCP_SERVICE_ACCOUNT --data-file=- --replication-policy=automatic

# 3. Grant Cloud Run's default SA access
PROJECT_NUMBER=$(gcloud projects describe gen-lang-client-0671890527 --format='value(projectNumber)')
for SECRET in TMDB_API_KEY GCP_SERVICE_ACCOUNT; do
  gcloud secrets add-iam-policy-binding $SECRET \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
done

# 4. Deploy (secrets are injected automatically as env vars)
gcloud run deploy movie-app \
  --source . \
  --region europe-west6 \
  --allow-unauthenticated \
  --port 8080 \
  --project gen-lang-client-0671890527 \
  --update-secrets="TMDB_API_KEY=TMDB_API_KEY:latest,GCP_SA_JSON=GCP_SERVICE_ACCOUNT:latest"
```

### Update secrets (rotate keys)

```bash
# Update TMDB key
echo -n "NEW_TMDB_KEY" | gcloud secrets versions add TMDB_API_KEY --data-file=-

# Update SA JSON
cat new-service-account.json | gcloud secrets versions add GCP_SERVICE_ACCOUNT --data-file=-
```

> Secret Manager automatically injects secrets as environment variables into Cloud Run containers. No code change needed — `db.py` and `tmdb.py` read them via `os.getenv()` as before.

---



## Running Tests

```bash
pip install pytest
pytest tests/ -v
```

---

## Project Structure

```
cloud_asignement/
├── app.py               ← Streamlit UI
├── db.py                ← BigQuery client + query executor
├── query_builder.py     ← SQL builder (pure functions)
├── tmdb.py              ← TMDB API integration
├── requirements.txt
├── Dockerfile
├── tests/
│   └── test_query_builder.py
├── .streamlit/
│   ├── config.toml
│   └── secrets.toml     ← NOT committed to git
└── README.md
```
