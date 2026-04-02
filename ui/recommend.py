"""
ui/recommend.py – Personalized recommendation page (two-step flow)

Step 1 – Onboarding: user picks movies they like via ES autocomplete.
Step 2 – Results: grid of recommended movies from POST /recommend.
"""

from __future__ import annotations

import os

import requests
import streamlit as st

from ui import components, styles


# ── Backend helpers ───────────────────────────────────────────────────────────

def _backend_url() -> str:
    try:
        return st.secrets.get("BACKEND_URL", os.environ.get("BACKEND_URL", "http://localhost:5001"))
    except Exception:
        return os.environ.get("BACKEND_URL", "http://localhost:5001")


@st.cache_data(ttl=10, show_spinner=False)
def _fetch_autocomplete(query: str) -> list:
    try:
        r = requests.get(
            f"{_backend_url()}/autocomplete",
            params={"q": query},
            timeout=2,
        )
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return []


def _fetch_recommendations(movie_ids: list, n: int = 10) -> list:
    try:
        r = requests.post(
            f"{_backend_url()}/recommend",
            json={"movie_ids": movie_ids, "n": n},
            timeout=15,
        )
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return []


# ── Page render ───────────────────────────────────────────────────────────────

def render(db, qb, tmdb_api):
    styles.render_navbar("recommend")
    st.markdown("<div style='height: 4rem'></div>", unsafe_allow_html=True)

    # Session state initialisation
    if "rec_selected_movies" not in st.session_state:
        st.session_state.rec_selected_movies = []  # list of {movieId, title, tmdbId, release_year}
    if "rec_show_results" not in st.session_state:
        st.session_state.rec_show_results = False

    if st.session_state.rec_show_results:
        _render_results(tmdb_api)
    else:
        _render_onboarding()


# ── Step 1: Onboarding ────────────────────────────────────────────────────────

def _render_onboarding():
    st.markdown(
        "<h1 style='padding: 0 4%;'>Quels films aimez-vous&nbsp;?</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='color:#aaa; padding: 0 4%; margin-bottom:2rem;'>"
        "Ajoutez des films que vous avez aimés pour obtenir des recommandations personnalisées.</p>",
        unsafe_allow_html=True,
    )

    with st.container():
        st.markdown("<div style='padding: 0 4%;'>", unsafe_allow_html=True)

        # ── Search with ES autocomplete ───────────────────────────────────────
        search_col, _ = st.columns([4, 2])
        with search_col:
            ac_query = st.text_input(
                "Rechercher un film",
                placeholder="Ex: The Matrix, Inception…",
                key="rec_ac_query",
            )

        suggestions = []
        if len(ac_query) >= 2:
            suggestions = _fetch_autocomplete(ac_query)

        selected_suggestion = None
        if suggestions:
            labels = ["-- Sélectionner un film --"] + [
                f"{s['title']} ({s.get('release_year', '')})" for s in suggestions
            ]
            sel_idx = st.selectbox(
                "Suggestions",
                options=range(len(labels)),
                format_func=lambda i: labels[i],
                key="rec_ac_sel",
            )
            if sel_idx > 0:
                selected_suggestion = suggestions[sel_idx - 1]

        add_col, _ = st.columns([2, 4])
        with add_col:
            add_disabled = selected_suggestion is None
            if st.button("Ajouter à ma liste", disabled=add_disabled, key="rec_add_btn"):
                # Avoid duplicates
                existing_ids = {m["movieId"] for m in st.session_state.rec_selected_movies}
                if selected_suggestion["movieId"] not in existing_ids:
                    st.session_state.rec_selected_movies.append(selected_suggestion)
                    st.rerun()

        # ── Selected movies chips ─────────────────────────────────────────────
        selected = st.session_state.rec_selected_movies
        if selected:
            st.markdown(
                "<p style='margin-top:1.5rem; font-weight:700; font-size:1rem;'>Films sélectionnés :</p>",
                unsafe_allow_html=True,
            )
            chips_html = " ".join(
                f"<span style='"
                f"display:inline-block; background:rgba(1,180,228,0.15); border:1px solid #01b4e4;"
                f"border-radius:20px; padding:4px 14px; margin:4px; font-size:0.9rem; color:#01b4e4;"
                f"'>{m['title']} ({m.get('release_year', '')})</span>"
                for m in selected
            )
            st.markdown(chips_html, unsafe_allow_html=True)

            # Per-movie remove buttons
            remove_cols = st.columns(min(len(selected), 6))
            for i, movie in enumerate(selected):
                with remove_cols[i % len(remove_cols)]:
                    if st.button(f"✖ {movie['title'][:20]}", key=f"rec_rm_{movie['movieId']}"):
                        st.session_state.rec_selected_movies = [
                            m for m in st.session_state.rec_selected_movies
                            if m["movieId"] != movie["movieId"]
                        ]
                        st.rerun()

        # ── CTA ───────────────────────────────────────────────────────────────
        st.markdown("<br>", unsafe_allow_html=True)
        cta_col, _ = st.columns([2, 4])
        with cta_col:
            if st.button("Voir mes recommandations ➜", key="rec_go_btn"):
                st.session_state.rec_show_results = True
                st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)


# ── Step 2: Results ───────────────────────────────────────────────────────────

def _render_results(tmdb_api):
    st.markdown(
        "<h1 style='padding: 0 4%;'>Vos recommandations</h1>",
        unsafe_allow_html=True,
    )

    selected = st.session_state.rec_selected_movies
    movie_ids = [m["movieId"] for m in selected]

    # Back button
    back_col, _ = st.columns([2, 5])
    with back_col:
        if st.button("← Modifier mes préférences", key="rec_back_btn"):
            st.session_state.rec_show_results = False
            st.rerun()

    # Selected movies summary
    if selected:
        titles = ", ".join(m["title"] for m in selected)
        st.markdown(
            f"<p style='color:#aaa; padding: 0 4%; margin-bottom:1.5rem;'>"
            f"Basé sur : <em>{titles}</em></p>",
            unsafe_allow_html=True,
        )

    with st.spinner("Calcul de vos recommandations…"):
        if movie_ids:
            recs = _fetch_recommendations(movie_ids, n=10)
        else:
            recs = []

    if not recs:
        st.info("Aucune recommandation disponible. Essayez d'ajouter d'autres films.")
        return

    # Build grid of TMDB-style cards (reuse existing component)
    import pandas as pd

    cards_html = ""
    for rec in recs:
        tmdb_id = rec.get("tmdbId") or rec.get("tmdb_id")
        poster = rec.get("poster_url") or ""
        if not poster and tmdb_id:
            pop = tmdb_api.fetch_movie_popularity(tmdb_id)
            poster = pop.get("poster_url", "") if pop else ""
        if not poster:
            safe_title = str(rec.get("title", "")).replace(" ", "+")
            poster = f"https://placehold.co/500x750/e3e3e3/9e9e9e?text={safe_title}"

        avg_r = float(rec.get("avg_pred") or rec.get("avg_rating") or 0)
        year = str(rec.get("release_year", ""))
        cards_html += components.build_tmdb_card(
            title=rec.get("title", ""),
            release_year=year,
            avg_rating_str=avg_r,
            poster_url=poster,
            tmdb_id=tmdb_id or "",
            from_page="recommend",
        )

    st.markdown(
        f"""
<div style="padding: 0 4%; font-family: 'Source Sans Pro', Arial, sans-serif;">
<style>.rec-grid {{ display:grid; grid-template-columns: repeat(5, minmax(0,1fr)); gap:20px; }}</style>
<div class="rec-grid">{cards_html}</div>
</div>
""",
        unsafe_allow_html=True,
    )
