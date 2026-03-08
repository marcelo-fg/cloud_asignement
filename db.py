"""
db.py – Database layer
Responsibilities:
  - Build the BigQuery client (ADC or service-account from Streamlit secrets)
  - Expose run_query(sql) which:
      * prints the SQL to the terminal
      * executes it against BigQuery
      * returns a pandas DataFrame
"""

from __future__ import annotations

import json
import os
import time

import pandas as pd
import streamlit as st
from google.cloud import bigquery
from google.oauth2 import service_account

# ── Project / dataset constants ────────────────────────────────────────────────
GCP_PROJECT = os.getenv("GCP_PROJECT", "gen-lang-client-0671890527")
DATASET = "assignement_1"
MOVIES_TABLE = f"{GCP_PROJECT}.{DATASET}.movies"
RATINGS_TABLE = f"{GCP_PROJECT}.{DATASET}.ratings"


@st.cache_resource(show_spinner=False)
def get_client() -> bigquery.Client:
    """Return a BigQuery client.

    Auth strategy (in priority order):
    1. Streamlit secrets key ``gcp_service_account`` (dict with SA JSON fields)
    2. ``GCP_SA_JSON`` env var  →  JSON string of service-account key
    3. ``GOOGLE_APPLICATION_CREDENTIALS`` env var  →  ADC
    4. Plain ADC (gcloud auth application-default login)
    """
    # 1. Streamlit secrets (local dev with secrets.toml)
    try:
        sa_info = st.secrets.get("gcp_service_account")
        if sa_info:
            if isinstance(sa_info, str):
                sa_info = json.loads(sa_info)
            credentials = service_account.Credentials.from_service_account_info(
                dict(sa_info),
                scopes=["https://www.googleapis.com/auth/cloud-platform"],
            )
            return bigquery.Client(project=GCP_PROJECT, credentials=credentials)
    except Exception:
        pass

    # 2. GCP_SA_JSON env var (Cloud Run / Docker production)
    sa_json = os.getenv("GCP_SA_JSON", "")
    if sa_json:
        try:
            sa_info = json.loads(sa_json)
            credentials = service_account.Credentials.from_service_account_info(
                sa_info,
                scopes=["https://www.googleapis.com/auth/cloud-platform"],
            )
            return bigquery.Client(project=GCP_PROJECT, credentials=credentials)
        except Exception:
            pass

    # 3. ADC fallback
    return bigquery.Client(project=GCP_PROJECT)


def run_query(sql: str) -> pd.DataFrame:
    """Execute *sql* on BigQuery, print it to the terminal, return a DataFrame."""

    print("\n" + "=" * 72)
    print("[BigQuery SQL]")
    print(sql)
    print("=" * 72 + "\n")

    client = get_client()
    t0 = time.time()
    try:
        result = client.query(sql).to_dataframe(create_bqstorage_client=False)
        elapsed = time.time() - t0
        print(f"  → {len(result)} row(s) returned in {elapsed:.2f}s\n")
        return result
    except Exception as exc:
        elapsed = time.time() - t0
        print(f"  [ERROR after {elapsed:.2f}s] {exc}\n")
        raise

