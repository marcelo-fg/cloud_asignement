import os
import requests

def _get_base_url():
    return os.environ.get("BACKEND_URL", "http://localhost:5001")

def health() -> bool:
    try:
        r = requests.get(f"{_get_base_url()}/health", timeout=3)
        return r.status_code == 200
    except requests.RequestException:
        return False

import streamlit as st

@st.cache_data(ttl=600, show_spinner=False)
def autocomplete(query: str, limit: int = 8) -> list[dict]:
    if not query or len(query) < 2:
        return []
    try:
        r = requests.get(f"{_get_base_url()}/autocomplete", params={"q": query, "limit": limit})
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[API] autocomplete error: {e}")
        return []

def get_top_movies(genre: str = "", limit: int = 16) -> list[dict]:
    """Fetch top-rated popular movies for the onboarding suggestion grid."""
    try:
        params = {"limit": limit}
        if genre:
            params["genre"] = genre
        r = requests.get(f"{_get_base_url()}/movies/top", params=params)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[API] get_top_movies error: {e}")
        return []

def get_recommendations(
    movie_ids: list[int] = None,
    movie_ratings: dict = None,
    genres: list[str] = None,
    year_min: int = None,
    year_max: int = None,
    person_tmdb_ids: list[int] = None,
    excluded_movie_ids: list[int] = None,
    n: int = 12
) -> list[dict]:
    try:
        payload = {"n": n}
        if movie_ids:
            payload["movie_ids"] = movie_ids
        if movie_ratings:
            payload["movie_ratings"] = movie_ratings
        if genres:
            payload["genres"] = genres
        if year_min is not None:
            payload["year_min"] = year_min
        if year_max is not None:
            payload["year_max"] = year_max
        if person_tmdb_ids:
            payload["person_tmdb_ids"] = person_tmdb_ids
        if excluded_movie_ids:
            payload["excluded_movie_ids"] = excluded_movie_ids

        r = requests.post(f"{_get_base_url()}/recommend", json=payload)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[API] recommend error: {e}")
        return []

