import os
import requests
from typing import Any, Dict

TMDB_API_KEY = os.getenv("TMDB_API_KEY")
TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"

# In-memory cache
_cache: Dict[str, Any] = {}

def _poster_url(path: str | None) -> str | None:
    """Build a full TMDB poster URL from a relative path."""
    return f"{TMDB_IMAGE_BASE}{path}" if path else None

def fetch_movie_popularity(tmdb_id: int | str) -> Dict[str, Any]:
    """
    Fetches movie details (poster + popularity) from TMDB with in-memory caching.
    Returns keys: title, poster_url, vote_average, popularity, release_date.
    """
    if not TMDB_API_KEY:
        print("[TMDB] Missing TMDB_API_KEY environment variable.")
        return {}
        
    cache_key = f"movie_{tmdb_id}"
    if cache_key in _cache:
        return _cache[cache_key]

    try:
        url = f"{TMDB_BASE_URL}/movie/{int(tmdb_id)}"
        params = {"api_key": TMDB_API_KEY, "language": "en-US"}
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        result = {
            "title": data.get("title", ""),
            "poster_url": _poster_url(data.get("poster_path")),
            "vote_average": data.get("vote_average", 0),
            "popularity": data.get("popularity", 0.0),
            "release_date": data.get("release_date", ""),
        }
        _cache[cache_key] = result
        return result
    except Exception as e:
        print(f"[TMDB] Error fetching movie {tmdb_id}: {e}")
        return {}
