"""
upload_data.py — Load MovieLens ml-latest-small CSVs into BigQuery.

Downloads the three CSV files from the course GitHub repository and uploads
them to BigQuery tables:
  - movies  (movies.csv + links.csv merged → adds tmdbId column)
  - ratings (ratings.csv)
  - links   (links.csv — raw, for reference)

Usage:
  python upload_data.py              # full upload
  python upload_data.py --dry-run    # print what would be uploaded, no writes
"""

import argparse
import io
import os
import sys

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# ── Configuration ─────────────────────────────────────────────────────────────

GCP_PROJECT = os.environ["GCP_PROJECT"]
BQ_DATASET  = os.environ.get("BQ_DATASET", "assignement_1")

# Course GitHub repository raw CSV URLs (ml-latest-small)
BASE_URL = (
    "https://raw.githubusercontent.com/DataTalksClub/movie-recommender-system/"
    "main/data/ml-latest-small"
)
URLS = {
    "movies":  f"{BASE_URL}/movies.csv",
    "ratings": f"{BASE_URL}/ratings.csv",
    "links":   f"{BASE_URL}/links.csv",
}

# BigQuery write disposition: WRITE_TRUNCATE replaces the table on every run
WRITE_DISPOSITION = "WRITE_TRUNCATE"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _download_csv(name: str, url: str) -> pd.DataFrame:
    print(f"  [download] {name} ← {url}")
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return pd.read_csv(io.StringIO(r.text))


def _get_bq_client():
    import json
    from google.cloud import bigquery
    from google.oauth2 import service_account

    sa_json = os.getenv("GCP_SA_JSON", "")
    if sa_json:
        info = json.loads(sa_json)
        creds = service_account.Credentials.from_service_account_info(info)
        return bigquery.Client(project=GCP_PROJECT, credentials=creds)
    return bigquery.Client(project=GCP_PROJECT)


def _upload(client, df: pd.DataFrame, table_id: str, dry_run: bool):
    from google.cloud import bigquery

    full_id = f"{GCP_PROJECT}.{BQ_DATASET}.{table_id}"
    print(f"  [upload] {len(df):,} rows → {full_id}")
    if dry_run:
        print(f"           (dry-run: skipping actual write)")
        print(df.dtypes.to_string())
        return

    job_config = bigquery.LoadJobConfig(
        write_disposition=WRITE_DISPOSITION,
        autodetect=True,
    )
    job = client.load_table_from_dataframe(df, full_id, job_config=job_config)
    job.result()  # wait for completion
    print(f"           ✓ done — {client.get_table(full_id).num_rows:,} rows in table")


# ── Main pipeline ─────────────────────────────────────────────────────────────

def run(dry_run: bool = False):
    print(f"\n{'='*60}")
    print(f"  Upload target : {GCP_PROJECT}.{BQ_DATASET}")
    print(f"  Dry-run       : {dry_run}")
    print(f"{'='*60}\n")

    # ── 1. Download all CSVs ──────────────────────────────────────────────────
    print("Step 1 — Downloading CSVs...")
    df_movies  = _download_csv("movies",  URLS["movies"])
    df_ratings = _download_csv("ratings", URLS["ratings"])
    df_links   = _download_csv("links",   URLS["links"])

    # ── 2. Enrich movies with tmdbId from links ───────────────────────────────
    print("\nStep 2 — Merging links into movies (adds tmdbId)...")
    # links.csv columns: movieId, imdbId, tmdbId
    df_links["tmdbId"] = pd.to_numeric(df_links["tmdbId"], errors="coerce").astype("Int64")
    df_movies_enriched = df_movies.merge(
        df_links[["movieId", "tmdbId"]],
        on="movieId",
        how="left",
    )

    # Extract release year from title "(YYYY)" pattern
    df_movies_enriched["release_year"] = (
        df_movies_enriched["title"]
        .str.extract(r"\((\d{4})\)\s*$")[0]
        .pipe(pd.to_numeric, errors="coerce")
        .astype("Int64")
    )

    print(f"  movies enriched: {len(df_movies_enriched):,} rows, "
          f"columns: {list(df_movies_enriched.columns)}")

    # ── 3. Upload to BigQuery ─────────────────────────────────────────────────
    print("\nStep 3 — Uploading to BigQuery...")
    client = None if dry_run else _get_bq_client()

    _upload(client, df_movies_enriched, "movies",  dry_run)
    _upload(client, df_ratings,         "ratings", dry_run)
    _upload(client, df_links,           "links",   dry_run)

    print(f"\n{'='*60}")
    print("  Upload complete!")
    print(f"{'='*60}\n")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Upload MovieLens data to BigQuery")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be uploaded without actually writing to BigQuery",
    )
    args = parser.parse_args()

    try:
        run(dry_run=args.dry_run)
    except Exception as exc:
        print(f"\n[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)
