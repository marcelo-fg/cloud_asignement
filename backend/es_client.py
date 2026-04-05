import os
from elasticsearch import Elasticsearch
from typing import List, Dict, Any

ES_URL = os.getenv("ES_URL")
ES_API_KEY = os.getenv("ES_API_KEY")
ES_INDEX = "movies"

def get_es_client():
    """Returns an Elasticsearch client initialized with ES_URL and ES_API_KEY."""
    if not ES_URL or not ES_API_KEY:
        print("[ES] Missing ES_URL or ES_API_KEY environment variables.")
        return None
    
    return Elasticsearch(
        ES_URL,
        api_key=ES_API_KEY
    )

def autocomplete(query: str, limit: int = 8) -> List[Dict[str, Any]]:
    """
    Performs search-as-you-type autocomplete on movie titles.
    Returns a list of dicts: {movieId, title, genres, tmdbId, release_year}.
    """
    client = get_es_client()
    if not client or not query:
        return []

    body = {
        "query": {
            "multi_match": {
                "query": query,
                "type": "bool_prefix",
                "fields": [
                    "title",
                    "title._2gram",
                    "title._3gram"
                ]
            }
        },
        "size": limit
    }
    
    try:
        response = client.search(index=ES_INDEX, body=body)
        from utils import normalize_title
        hits = response.get("hits", {}).get("hits", [])
        results = []
        for hit in hits:
            source = hit["_source"]
            source["title"] = normalize_title(source.get("title", ""))
            results.append(source)
        return results
    except Exception as e:
        print(f"[ES] Error during autocomplete: {e}")
        return []
