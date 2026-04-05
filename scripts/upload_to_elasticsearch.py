"""
scripts/upload_to_elasticsearch.py
===================================
Uploads the ml-small movie dataset to Elasticsearch.
Creates an index with proper mapping for autocomplete search.

Usage:
    pip install elasticsearch pandas
    python scripts/upload_to_elasticsearch.py \
        --endpoint "https://xxxx.es.io:9243" \
        --api-key "your_api_key" \
        --movies  data/movies.csv \
        --links   data/links.csv

Or set environment variables:
    ES_ENDPOINT=https://... ES_API_KEY=... python scripts/upload_to_elasticsearch.py
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import pandas as pd
from elasticsearch import Elasticsearch, helpers

# ── Constants ──────────────────────────────────────────────────────────────────

INDEX_NAME = "movies"

# Mapping optimized for autocomplete (search_as_you_type = edge n-gram)
INDEX_MAPPING = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
    },
    "mappings": {
        "properties": {
            "movieId":  {"type": "integer"},
            "tmdbId":   {"type": "integer"},
            "title":    {"type": "search_as_you_type"},   # ← autocomplete magic
            "genres":   {"type": "keyword"},               # exact match / filter
            "genres_text": {"type": "text"},               # full-text search on genres
        }
    },
}


# ── Helpers ────────────────────────────────────────────────────────────────────

def build_client(endpoint: str, api_key: str | None, username: str | None, password: str | None) -> Elasticsearch:
    """Build an Elasticsearch client from credentials."""
    if api_key:
        client = Elasticsearch(endpoint, api_key=api_key, verify_certs=True)
    elif username and password:
        client = Elasticsearch(endpoint, basic_auth=(username, password), verify_certs=True)
    else:
        raise ValueError("Provide either --api-key or --username + --password")

    # Quick connectivity check
    info = client.info()
    print(f"✅ Connected to Elasticsearch cluster: {info['cluster_name']} (v{info['version']['number']})")
    return client


def load_movies(movies_path: str, links_path: str | None) -> pd.DataFrame:
    """Load movies CSV and optionally join with links CSV to get tmdbId."""
    print(f"\n📂 Loading movies from: {movies_path}")
    movies = pd.read_csv(movies_path)
    print(f"   → {len(movies)} movies loaded")

    if links_path and os.path.exists(links_path):
        print(f"📂 Loading links from: {links_path}")
        links = pd.read_csv(links_path)[["movieId", "tmdbId"]]
        movies = movies.merge(links, on="movieId", how="left")
        print(f"   → tmdbId joined ({movies['tmdbId'].notna().sum()} movies have a TMDB ID)")
    else:
        print("⚠️  No links.csv provided — tmdbId will be missing")
        movies["tmdbId"] = None

    # Normalize
    movies["tmdbId"] = pd.to_numeric(movies["tmdbId"], errors="coerce")
    movies["movieId"] = pd.to_numeric(movies["movieId"], errors="coerce")
    movies = movies.dropna(subset=["movieId"]).copy()
    movies["movieId"] = movies["movieId"].astype(int)

    return movies


def recreate_index(client: Elasticsearch, index: str) -> None:
    """Delete (if exists) and recreate the index with our mapping."""
    if client.indices.exists(index=index):
        print(f"\n🗑️  Deleting existing index '{index}'...")
        client.indices.delete(index=index)

    print(f"📐 Creating index '{index}' with autocomplete mapping...")
    client.indices.create(index=index, body=INDEX_MAPPING)
    print(f"   ✅ Index '{index}' created")


def generate_actions(movies: pd.DataFrame, index: str):
    """Generate bulk index actions from the dataframe."""
    for _, row in movies.iterrows():
        title = str(row.get("title", "")).strip()
        genres_raw = str(row.get("genres", "")).strip()
        genres_list = [g.strip() for g in genres_raw.split("|") if g.strip() and g.strip() != "(no genres listed)"]

        tmdb_id = row.get("tmdbId")
        tmdb_id_val = int(tmdb_id) if pd.notna(tmdb_id) else None

        yield {
            "_index": index,
            "_id": int(row["movieId"]),
            "_source": {
                "movieId":     int(row["movieId"]),
                "tmdbId":      tmdb_id_val,
                "title":       title,
                "genres":      genres_list,
                "genres_text": genres_raw.replace("|", " "),
            },
        }


def bulk_index(client: Elasticsearch, movies: pd.DataFrame, index: str, batch_size: int = 500) -> None:
    """Bulk index all movies in batches."""
    total = len(movies)
    print(f"\n⬆️  Indexing {total} movies into '{index}' (batch_size={batch_size})...")

    t0 = time.time()
    success, errors = helpers.bulk(
        client,
        generate_actions(movies, index),
        chunk_size=batch_size,
        raise_on_error=False,
        stats_only=False,
    )

    elapsed = time.time() - t0
    print(f"\n✅ Done in {elapsed:.1f}s")
    print(f"   → {success} documents indexed successfully")
    if errors:
        print(f"   ⚠️  {len(errors)} errors:")
        for e in errors[:5]:
            print(f"      {e}")


def test_autocomplete(client: Elasticsearch, query: str = "Pulp", index: str = INDEX_NAME) -> None:
    """Quick test of the autocomplete after indexing."""
    print(f"\n🔍 Testing autocomplete for '{query}'...")
    results = client.search(
        index=index,
        body={
            "query": {
                "multi_match": {
                    "query": query,
                    "type": "bool_prefix",
                    "fields": ["title", "title._2gram", "title._3gram"],
                }
            },
            "size": 5,
        },
    )
    hits = results["hits"]["hits"]
    if hits:
        print(f"   Results ({len(hits)}):")
        for h in hits:
            src = h["_source"]
            print(f"   - [{src['movieId']}] {src['title']} (tmdbId={src.get('tmdbId')})")
    else:
        print("   ⚠️  No results found — check the index")


# ── Main ───────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Upload ml-small movies to Elasticsearch")
    p.add_argument("--endpoint", default=os.getenv("ES_ENDPOINT"), help="Elastic Cloud endpoint URL")
    p.add_argument("--api-key",  default=os.getenv("ES_API_KEY"),  help="Elastic Cloud API key")
    p.add_argument("--username", default=os.getenv("ES_USERNAME"), help="Elasticsearch username (if not using API key)")
    p.add_argument("--password", default=os.getenv("ES_PASSWORD"), help="Elasticsearch password")
    p.add_argument("--movies",   default="data/movies.csv",  help="Path to movies.csv")
    p.add_argument("--links",    default="data/links.csv",   help="Path to links.csv (optional but recommended)")
    p.add_argument("--index",    default=INDEX_NAME,          help="Elasticsearch index name")
    p.add_argument("--batch",    type=int, default=500,       help="Bulk batch size")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    if not args.endpoint:
        print("❌ ERROR: Missing --endpoint (or ES_ENDPOINT env var)")
        sys.exit(1)

    # 1. Connect
    client = build_client(args.endpoint, args.api_key, args.username, args.password)

    # 2. Load data
    movies = load_movies(args.movies, args.links)

    # 3. Recreate index
    recreate_index(client, args.index)

    # 4. Index data
    bulk_index(client, movies, args.index, batch_size=args.batch)

    # 5. Refresh + quick test
    client.indices.refresh(index=args.index)
    test_autocomplete(client, query="Pulp", index=args.index)

    count = client.count(index=args.index)["count"]
    print(f"\n🎬 Total documents in '{args.index}': {count}")
    print("\n✅ Upload complete! Your Elasticsearch index is ready for autocomplete.")


if __name__ == "__main__":
    main()
