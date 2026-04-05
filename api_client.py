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

@st.cache_data(ttl=3600, show_spinner=False)
def get_genres() -> list[str]:
    """Fetch distinct genre list from backend."""
    try:
        r = requests.get(f"{_get_base_url()}/movies/genres", timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[API] get_genres error: {e}")
        return []


@st.cache_data(ttl=3600, show_spinner=False)
def get_languages() -> list[str]:
    """Fetch distinct language list from backend."""
    try:
        r = requests.get(f"{_get_base_url()}/movies/languages", timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[API] get_languages error: {e}")
        return []


@st.cache_data(ttl=600, show_spinner=False)
def search_movies(
    title: str = "",
    language: str = "",
    genres: tuple = (),
    rating_min: float = 0.0,
    rating_max: float = 5.0,
    year_min: int = 1900,
    year_max: int = 2026,
    limit: int = 100,
    tmdb_ids: tuple | None = None,
) -> list[dict]:
    """Search movies via backend with optional filters and tmdb_ids list."""
    try:
        params: dict = {
            "language": language,
            "year_min": year_min,
            "year_max": year_max,
            "rating_min": rating_min,
            "rating_max": rating_max,
            "limit": limit,
        }
        if title:
            params["title"] = title
        for g in genres:
            params.setdefault("genre", [])
            if isinstance(params["genre"], list):
                params["genre"].append(g)
        if tmdb_ids is not None:
            params["tmdb_ids"] = ",".join(str(i) for i in tmdb_ids)
        r = requests.get(f"{_get_base_url()}/movies/search", params=params, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[API] search_movies error: {e}")
        return []


def get_movies_by_tmdb_ids(tmdb_ids: list[int], limit: int = 60) -> list[dict]:
    """Fetch top BQ movies matching a list of TMDB IDs (used for filmography pages)."""
    if not tmdb_ids:
        return []
    try:
        r = requests.post(
            f"{_get_base_url()}/movies/by-tmdb-ids",
            json={"tmdb_ids": tmdb_ids, "limit": limit},
            timeout=20,
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[API] get_movies_by_tmdb_ids error: {e}")
        return []


def resolve_tmdb_ids_to_movie_ids(tmdb_ids: list[int]) -> list:
    """Convert TMDB IDs to BigQuery movieIds via backend."""
    if not tmdb_ids:
        return []
    try:
        r = requests.post(
            f"{_get_base_url()}/movies/ids-from-tmdb",
            json={"tmdb_ids": tmdb_ids},
            timeout=10,
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[API] resolve_tmdb_ids_to_movie_ids error: {e}")
        return []


@st.cache_data(ttl=3600, show_spinner=False)
def get_top_movies_per_genre(limit: int = 10) -> list[dict]:
    """Fetch top N movies per genre (window function query via backend)."""
    try:
        r = requests.get(f"{_get_base_url()}/movies/top-per-genre", params={"limit": limit}, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[API] get_top_movies_per_genre error: {e}")
        return []


@st.cache_data(ttl=3600, show_spinner=False)
def get_top_movies_per_decade(limit: int = 20) -> list[dict]:
    """Fetch top N movies per decade (window function query via backend)."""
    try:
        r = requests.get(f"{_get_base_url()}/movies/top-per-decade", params={"limit": limit}, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[API] get_top_movies_per_decade error: {e}")
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

