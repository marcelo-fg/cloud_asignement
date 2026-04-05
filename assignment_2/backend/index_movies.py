import os
from dotenv import load_dotenv
load_dotenv() # Load before other imports

from elasticsearch import helpers
from db import run_query, MOVIES_TABLE
from es_client import get_es_client, ES_INDEX
from utils import normalize_title
from tqdm import tqdm

def create_index(client):
    """Creates the movies index with search_as_you_type mapping."""
    if client.indices.exists(index=ES_INDEX):
        client.indices.delete(index=ES_INDEX)
    
    mapping = {
        "mappings": {
            "properties": {
                "movieId": {"type": "integer"},
                "title": {"type": "search_as_you_type"},
                "genres": {"type": "keyword"},
                "tmdbId": {"type": "integer"},
                "release_year": {"type": "integer"},
                "country": {"type": "keyword"},
                "language": {"type": "keyword"}
            }
        }
    }
    client.indices.create(index=ES_INDEX, body=mapping)
    print(f"[ES] Created index '{ES_INDEX}' with search_as_you_type mapping.")

def index_movies():
    """Reads all movies from BigQuery and bulk-indexes them into Elasticsearch."""
    load_dotenv()
    client = get_es_client()
    if not client:
        return
    
    create_index(client)

    sql = f"SELECT movieId, title, genres, tmdbId, release_year, country, language FROM `{MOVIES_TABLE}`"
    movies_df = run_query(sql)
    movies = movies_df.to_dict('records')  # list of dicts

    actions = []
    count = 0
    batch_size = 500

    print("[ES] Starting bulk indexing...")
    for movie_dict in tqdm(movies, desc="Indexing movies"):
        # Normalize the title for better search
        movie_dict["title"] = normalize_title(movie_dict["title"])
        
        action = {
            "_index": ES_INDEX,
            "_id": movie_dict["movieId"],
            "_source": movie_dict
        }
        actions.append(action)
        
        if len(actions) >= batch_size:
            helpers.bulk(client, actions)
            actions = []
            count += batch_size
    
    # Final batch
    if actions:
        helpers.bulk(client, actions)
        count += len(actions)
        
    print(f"[ES] Bulk indexing complete. {count} movies indexed.")

if __name__ == "__main__":
    index_movies()
