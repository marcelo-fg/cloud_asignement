"""
app.py – Streamlit Application Entrypoint (Netflix-style UI)

Architecture:
  Layer 1: Database (db.py) & API (tmdb.py)
  Layer 2: SQL logic (query_builder.py)
  Layer 3: UI renderer (ui/home.py + ui/styles.py)
"""

from __future__ import annotations

import streamlit as st

import db
import query_builder as qb
import tmdb
from ui import home, styles, search, people, movie

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
    home.render(db, qb, tmdb)
elif page == "search":
    search.render(db, qb, tmdb)
elif page == "people":
    people.render(db, qb, tmdb)
elif page == "movie":
    movie.render(db, qb, tmdb)
else:
    home.render(db, qb, tmdb)
