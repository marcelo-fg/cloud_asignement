"""
app.py – Streamlit Application Entrypoint (Netflix-style UI)

Architecture:
  Layer 1: Flask backend API (api_client.py) + TMDB API (tmdb.py)
  Layer 2: UI renderer (ui/)
"""

from __future__ import annotations

import streamlit as st

import tmdb
from ui import home, styles, search, people, movie, recommend

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="MovieFinder",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Inject Netflix-style CSS
styles.inject()

# ── Routing ──────────────────────────────────────────────────────────────────
page = st.query_params.get("page", "home")

if page == "home":
    home.render(tmdb)
elif page == "search":
    search.render(tmdb)
elif page == "people":
    people.render(tmdb)
elif page == "movie":
    movie.render(tmdb)
elif page == "recommend":
    recommend.render()
else:
    home.render(tmdb)

