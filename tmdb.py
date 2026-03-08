"""
tmdb.py – TMDB API layer
Fetches movie details (poster, overview, cast, credits) from The Movie Database API.
All results are cached via @st.cache_data to avoid redundant network calls.
"""

from __future__ import annotations

import os
from typing import Any

import requests
import streamlit as st

TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"
TMDB_BACKDROP_BASE = "https://image.tmdb.org/t/p/original"

def _get_api_key() -> str | None:
    """Retrieve TMDB API key from Streamlit secrets or environment variable."""
    try:
        key = st.secrets.get("TMDB_API_KEY", "")
        if key:
            return str(key)
    except Exception:
        pass
    return os.getenv("TMDB_API_KEY", "") or None


def _poster_url(path: str | None) -> str | None:
    """Build a full TMDB poster URL from a relative path, or return None."""
    return f"{TMDB_IMAGE_BASE}{path}" if path else None

def _backdrop_url(path: str | None) -> str | None:
    """Build a full TMDB backdrop URL from a relative path, or return None."""
    return f"{TMDB_BACKDROP_BASE}{path}" if path else None

def _get(endpoint: str, params: dict) -> dict:
    """Perform a GET request to the TMDB API and return the JSON body."""
    r = requests.get(f"{TMDB_BASE_URL}/{endpoint}", params=params, timeout=8)
    r.raise_for_status()
    return r.json()


# ── Movie detail (full, with cast) ────────────────────────────────────────────

def fetch_movie_details(tmdb_id: int | str) -> dict[str, Any]:
    """Fetch full movie details + cast from TMDB. Returns {} on error."""
    api_key = _get_api_key()
    if not api_key or not tmdb_id:
        return {}
    try:
        params = {"api_key": api_key, "language": "fr-FR", "append_to_response": "credits,keywords"}
        data = _get(f"movie/{int(tmdb_id)}", params)
        
        # Fallback to English if French overview is empty
        if not data.get("overview"):
            en_data = _get(f"movie/{int(tmdb_id)}", {"api_key": api_key, "language": "en-US"})
            data["overview"] = en_data.get("overview", "")

        credits = data.get("credits", {})
        return {
            "title": data.get("title", ""),
            "overview": data.get("overview", ""),
            "tagline": data.get("tagline", ""),
            "release_date": data.get("release_date", ""),
            "vote_average": data.get("vote_average", 0),
            "vote_count": data.get("vote_count", 0),
            "popularity": data.get("popularity", 0.0),
            "revenue": data.get("revenue", 0),
            "poster_url": _poster_url(data.get("poster_path")),
            "backdrop_url": _backdrop_url(data.get("backdrop_path")),
            "genres": [g["name"] for g in data.get("genres", [])],
            "cast": [
                {"name": a.get("name", ""), "character": a.get("character", ""), "profile_url": _poster_url(a.get("profile_path"))}
                for a in credits.get("cast", [])[:8]
            ],
            "directors": [cr.get("name", "") for cr in credits.get("crew", []) if cr.get("job") == "Director"],
            "keywords": [k.get("name", "") for k in data.get("keywords", {}).get("keywords", [])],
            "homepage": data.get("homepage", ""),
        }
    except Exception as exc:
        print(f"[TMDB] Error fetching movie {tmdb_id}: {exc}")
        return {}


# ── Movie lightweight (popularity signals only, no cast) ───────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_movie_popularity(tmdb_id: int | str) -> dict[str, Any]:
    """
    Lightweight fetch — poster + popularity signals only (no credits call).
    Used by Top Charts to enrich many films without N×2 API calls.

    Returns keys: title, poster_url, vote_average, vote_count, popularity,
                  revenue, release_date.
    Returns {} on error.
    """
    api_key = _get_api_key()
    if not api_key or not tmdb_id:
        return {}
    try:
        data = _get(f"movie/{int(tmdb_id)}", {"api_key": api_key, "language": "en-US"})
        return {
            "title": data.get("title", ""),
            "poster_url": _poster_url(data.get("poster_path")),
            "vote_average": data.get("vote_average", 0),
            "vote_count": data.get("vote_count", 0),
            "popularity": data.get("popularity", 0.0),
            "revenue": data.get("revenue", 0),
            "release_date": data.get("release_date", ""),
        }
    except requests.RequestException as exc:
        print(f"[TMDB] Error fetching popularity for {tmdb_id}: {exc}")
        return {}


# ── Person search ──────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def search_person(name: str) -> list[dict[str, Any]]:
    """
    Search TMDB for a person (actor or director) by name.

    Returns up to 5 candidates, each with:
      id, name, known_for_department, profile_url, known_for (list of titles).
    """
    api_key = _get_api_key()
    if not api_key or not name.strip():
        return []
    try:
        results = _get("search/person", {"api_key": api_key, "query": name.strip(), "language": "en-US"}).get("results", [])
        return [
            {
                "id": p["id"],
                "name": p.get("name", ""),
                "known_for_department": p.get("known_for_department", ""),
                "profile_url": _poster_url(p.get("profile_path")),
                "known_for": [
                    m.get("title") or m.get("name", "")
                    for m in p.get("known_for", [])[:3]
                    if m.get("title") or m.get("name")
                ],
            }
            for p in results[:5]
        ]
    except requests.RequestException as exc:
        print(f"[TMDB] Error searching person '{name}': {exc}")
        return []


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_person_movie_tmdb_ids(person_id: int, role: str = "actor") -> list[int]:
    """
    Return TMDB movie IDs for a person.

    role: 'actor' → cast credits | 'director' → crew where job=Director | 'both' → union
    """
    api_key = _get_api_key()
    if not api_key:
        return []
    try:
        data = _get(f"person/{person_id}/movie_credits", {"api_key": api_key, "language": "en-US"})
        ids: set[int] = set()
        if role in ("actor", "both"):
            ids.update(int(m["id"]) for m in data.get("cast", []) if m.get("id"))
        if role in ("director", "both"):
            ids.update(int(m["id"]) for m in data.get("crew", []) if m.get("job") == "Director" and m.get("id"))
        return list(ids)
    except requests.RequestException as exc:
        print(f"[TMDB] Error fetching credits for person {person_id}: {exc}")
        return []


# ── Franchise / Collection ────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def search_collection(name: str) -> list[dict[str, Any]]:
    """Search TMDB for a movie collection/saga. Returns up to 5 candidates."""
    api_key = _get_api_key()
    if not api_key or not name.strip():
        return []
    try:
        results = _get("search/collection", {"api_key": api_key, "query": name.strip(), "language": "en-US"}).get("results", [])
        return [{"id": c["id"], "name": c.get("name", ""), "poster_url": _poster_url(c.get("poster_path"))} for c in results[:5]]
    except requests.RequestException as exc:
        print(f"[TMDB] Error searching collection '{name}': {exc}")
        return []


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_collection_tmdb_ids(collection_id: int) -> tuple[list[int], str, str | None]:
    """
    Return (tmdb_ids, collection_name, poster_url) for a collection.
    """
    api_key = _get_api_key()
    if not api_key:
        return [], "", None
    try:
        data = _get(f"collection/{collection_id}", {"api_key": api_key, "language": "en-US"})
        ids = [int(p["id"]) for p in data.get("parts", []) if p.get("id")]
        return ids, data.get("name", ""), _poster_url(data.get("poster_path"))
    except requests.RequestException as exc:
        print(f"[TMDB] Error fetching collection {collection_id}: {exc}")
        return [], "", None


# ── Keywords / Themes ─────────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def search_keyword(name: str) -> list[dict[str, Any]]:
    """Search TMDB keywords. Returns up to 8 results with keys: id, name."""
    api_key = _get_api_key()
    if not api_key or not name.strip():
        return []
    try:
        results = _get("search/keyword", {"api_key": api_key, "query": name.strip()}).get("results", [])
        return [{"id": k["id"], "name": k["name"]} for k in results[:8]]
    except requests.RequestException as exc:
        print(f"[TMDB] Error searching keyword '{name}': {exc}")
        return []


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_movies_by_keyword(keyword_id: int, pages: int = 3) -> list[int]:
    """
    Return TMDB movie IDs tagged with keyword_id (up to pages×20 results).
    Sorted by vote_count descending for best dataset overlap.
    """
    api_key = _get_api_key()
    if not api_key:
        return []
    ids: list[int] = []
    try:
        for page in range(1, pages + 1):
            data = _get("discover/movie", {
                "api_key": api_key,
                "with_keywords": str(keyword_id),
                "sort_by": "vote_count.desc",
                "page": page,
                "language": "en-US",
            })
            ids.extend(int(m["id"]) for m in data.get("results", []) if m.get("id"))
            if page >= data.get("total_pages", 1):
                break
        return ids
    except requests.RequestException as exc:
        print(f"[TMDB] Error fetching movies for keyword {keyword_id}: {exc}")
        return []

@st.cache_data(ttl=3600, show_spinner=False)
def search_advanced_concepts(query: str, limit_pages: int = 1) -> list[int]:
    """
    Powerful semantic search:
    1. Direct movie search (handles typos natively like 'matricse' -> 'matrix')
    2. Maps word to TMDB keywords (e.g. 'mafia') and fetches movies tagged with it.
    Returns a unified, deduplicated list of TMDB IDs ranked by popularity.
    """
    api_key = _get_api_key()
    if not api_key or not query.strip():
        return []
        
    unified_ids: set[int] = set()
    
    try:
        # 1. Direct Title Search (Typo tolerant)
        for page in range(1, limit_pages + 1):
            title_data = _get("search/movie", {
                "api_key": api_key, 
                "query": query.strip(), 
                "language": "en-US",
                "page": page
            })
            unified_ids.update(int(m["id"]) for m in title_data.get("results", []) if m.get("id"))
            
        # 2. Semantic Keyword Search
        keyword_data = _get("search/keyword", {"api_key": api_key, "query": query.strip()})
        top_keyword_ids = [k["id"] for k in keyword_data.get("results", [])[:3]]
        
        # Fetch best movies for the top 3 matching keywords
        for kw_id in top_keyword_ids:
            for page in range(1, limit_pages + 1):
                kw_movies = _get("discover/movie", {
                    "api_key": api_key,
                    "with_keywords": str(kw_id),
                    "sort_by": "popularity.desc",
                    "page": page,
                    "language": "en-US",
                })
                unified_ids.update(int(m["id"]) for m in kw_movies.get("results", []) if m.get("id"))

        return list(unified_ids)
    except requests.RequestException as exc:
        print(f"[TMDB] Error in advanced semantic search for '{query}': {exc}")
        return []


# ── Similar Movies ────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_similar_movie_tmdb_ids(tmdb_id: int | str, pages: int = 2) -> list[int]:
    """Return TMDB IDs of films similar to tmdb_id (up to pages×20 results)."""
    api_key = _get_api_key()
    if not api_key or not tmdb_id:
        return []
    ids: list[int] = []
    try:
        for page in range(1, pages + 1):
            data = _get(f"movie/{int(tmdb_id)}/similar", {"api_key": api_key, "language": "en-US", "page": page})
            ids.extend(int(m["id"]) for m in data.get("results", []) if m.get("id"))
            if page >= data.get("total_pages", 1):
                break
        return ids
    except requests.RequestException as exc:
        print(f"[TMDB] Error fetching similar movies for {tmdb_id}: {exc}")
        return []
