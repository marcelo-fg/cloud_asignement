"""
tmdb.py – TMDB API layer
Fetches movie details (poster, overview, cast) from The Movie Database API.
Results are cached via @st.cache_data to avoid redundant network calls.
"""

from __future__ import annotations

from typing import Any

import requests
import streamlit as st

TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"


def _get_api_key() -> str | None:
    """Retrieve TMDB API key from Streamlit secrets or environment."""
    try:
        key = st.secrets.get("TMDB_API_KEY", "")
        if key:
            return str(key)
    except Exception:
        pass
    import os
    return os.getenv("TMDB_API_KEY", "") or None


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_movie_details(tmdb_id: int | str) -> dict[str, Any]:
    """
    Fetch full movie details from TMDB.

    Returns a dict with keys:
      - title, overview, tagline, release_date, vote_average
      - poster_url  (full URL or None)
      - genres      (list of str)
      - cast        (list of dicts: name, character, profile_url)
      - homepage
    Returns an empty dict on error.
    """
    api_key = _get_api_key()
    if not api_key or not tmdb_id:
        return {}

    try:
        # Movie details
        detail_url = f"{TMDB_BASE_URL}/movie/{int(tmdb_id)}"
        r = requests.get(
            detail_url,
            params={"api_key": api_key, "language": "en-US"},
            timeout=8,
        )
        r.raise_for_status()
        data = r.json()

        poster_path = data.get("poster_path")
        poster_url = f"{TMDB_IMAGE_BASE}{poster_path}" if poster_path else None

        genres = [g["name"] for g in data.get("genres", [])]

        # Credits (cast)
        credits_url = f"{TMDB_BASE_URL}/movie/{int(tmdb_id)}/credits"
        rc = requests.get(
            credits_url,
            params={"api_key": api_key, "language": "en-US"},
            timeout=8,
        )
        rc.raise_for_status()
        credits_data = rc.json()

        cast = []
        for actor in credits_data.get("cast", [])[:8]:
            profile_path = actor.get("profile_path")
            cast.append(
                {
                    "name": actor.get("name", ""),
                    "character": actor.get("character", ""),
                    "profile_url": (
                        f"{TMDB_IMAGE_BASE}{profile_path}" if profile_path else None
                    ),
                }
            )

        return {
            "title": data.get("title", ""),
            "overview": data.get("overview", ""),
            "tagline": data.get("tagline", ""),
            "release_date": data.get("release_date", ""),
            "vote_average": data.get("vote_average", 0),
            "poster_url": poster_url,
            "genres": genres,
            "cast": cast,
            "homepage": data.get("homepage", ""),
        }

    except requests.RequestException as exc:
        print(f"[TMDB] Error fetching movie {tmdb_id}: {exc}")
        return {}
