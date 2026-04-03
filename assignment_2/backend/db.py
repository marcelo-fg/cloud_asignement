import os
import json
from google.cloud import bigquery
from google.oauth2 import service_account

# Configuration
GCP_PROJECT = os.getenv("GCP_PROJECT", "gen-lang-client-0671890527")
BQ_DATASET = os.getenv("BQ_DATASET", "assignement_1")
MODEL_NAME = f"{GCP_PROJECT}.{BQ_DATASET}.movie_recommender"
MOVIES_TABLE = f"{GCP_PROJECT}.{BQ_DATASET}.movies"
RATINGS_TABLE = f"{GCP_PROJECT}.{BQ_DATASET}.ratings"

def get_bq_client():
    """
    Initializes a BigQuery client using GCP_SA_JSON environment variable or ADC.
    """
    gcp_sa_json = os.getenv("GCP_SA_JSON")
    if gcp_sa_json:
        try:
            info = json.loads(gcp_sa_json)
            credentials = service_account.Credentials.from_service_account_info(info)
            return bigquery.Client(credentials=credentials, project=GCP_PROJECT)
        except Exception as e:
            print(f"Error initializing BigQuery client with service account JSON: {e}")
            raise e
    else:
        # Falls back to Application Default Credentials
        return bigquery.Client(project=GCP_PROJECT)

def run_query(sql: str):
    """
    Executes a SQL query on BigQuery, printing the query to the terminal first.
    Uses the jobs API (not Storage API) to avoid needing bigquery.readsessions.create.
    """
    print("\n" + "="*80)
    print("EXECUTING BIGQUERY SQL:")
    print(sql)
    print("="*80 + "\n")

    import pandas as pd
    client = get_bq_client()
    query_job = client.query(sql)
    rows = list(query_job.result())
    if not rows:
        return pd.DataFrame()
    # Build DataFrame from Row objects (no Storage API needed)
    return pd.DataFrame([dict(r) for r in rows])
