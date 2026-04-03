"""
ui/home.py – Renders the complete Netflix-style cinematic home page.
Includes the 'Pour vous' personalized recommendation section above the Top 10.
"""

from __future__ import annotations

import os
import re
import requests
import streamlit as st
import pandas as pd
from ui import styles, components
from db import MOVIES_TABLE


# ─────────────────────────────────────────────────────────────────────────────
# Home page data fetching (cached)
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=600, show_spinner="Loading Cinematic UI...")
def _fetch_home_data_v2(_db, _qb, _tmdb):
    """Fetches all data needed for the cinematic home page."""
    # ── 1. Top 10 All Time ──────────────────────────────────────────────────
    top_sql = _qb.build_top_charts_query(limit=10)
    df_top = _db.run_query(top_sql)
    top_movies = []

    for rank, row in enumerate(df_top.itertuples(), 1):
        details = _tmdb.fetch_movie_details(row.tmdbId) if pd.notna(row.tmdbId) else {}
        poster = details.get("poster_url") or "https://via.placeholder.com/500x750/000000/38bdf8?text=No+Poster"
        backdrop = details.get("backdrop_url") or poster
        overview = details.get("overview", "Aucun résumé disponible.")

        if len(overview) > 180:
            overview = overview[:177] + "..."

        top_movies.append({
            "rank": rank,
            "title": row.title,
            "poster": poster,
            "backdrop": backdrop,
            "overview": overview,
            "tmdbId": row.tmdbId,
            "rating": getattr(row, "avg_rating", "N/A"),
            "votes": getattr(row, "nb_ratings", "0"),
            "year": getattr(row, "release_year", "")
        })

    # ── 2. Top 10 by All Genres ─────────────────────────────────────────────
    genre_data = {}
    g_sql = _qb.build_top_movies_per_genre_query(limit=10)
    df_g = _db.run_query(g_sql)

    for row in df_g.itertuples():
        g = row.genre
        if g not in genre_data:
            genre_data[g] = {"movies": [], "sql": g_sql}
        pop = _tmdb.fetch_movie_popularity(row.tmdbId) if pd.notna(row.tmdbId) else {}
        poster = pop.get("poster_url") or "https://via.placeholder.com/500x750/000000/38bdf8?text=No+Poster"
        genre_data[g]["movies"].append({
            "rank": row.rank_in_genre,
            "title": row.title,
            "poster": poster,
            "rating": getattr(row, "avg_rating", "N/A"),
            "votes": getattr(row, "nb_ratings", "0"),
            "year": getattr(row, "release_year", ""),
            "tmdbId": row.tmdbId
        })

    # ── 3. Hits by Decade ───────────────────────────────────────────────────
    decade_data = {}
    d_sql = _qb.build_top_movies_per_decade_query(limit=20)
    df_d = _db.run_query(d_sql)

    decade_labels = {
        1960: "60s", 1970: "70s", 1980: "80s",
        1990: "90s", 2000: "2000s", 2010: "2010s"
    }

    for row in df_d.itertuples():
        d_val = row.decade
        label = decade_labels.get(d_val, f"{d_val}s")
        if label not in decade_data:
            decade_data[label] = {"movies": [], "sql": d_sql}

        pop = _tmdb.fetch_movie_popularity(row.tmdbId) if pd.notna(row.tmdbId) else {}
        poster = pop.get("poster_url") or "https://via.placeholder.com/500x750/000000/38bdf8?text=No+Poster"
        decade_data[label]["movies"].append({
            "title": row.title,
            "poster": poster,
            "rating": getattr(row, "avg_rating", "N/A"),
            "year": getattr(row, "release_year", ""),
            "tmdbId": row.tmdbId
        })

    return top_movies, top_sql, genre_data, decade_data, d_sql


# ─────────────────────────────────────────────────────────────────────────────
# "Pour vous" – helpers
# ─────────────────────────────────────────────────────────────────────────────

_ALL_GENRES = [
    "Action", "Adventure", "Animation", "Comedy", "Crime", "Documentary",
    "Drama", "Family", "Fantasy", "History", "Horror", "Music", "Mystery",
    "Romance", "Science Fiction", "Thriller", "War", "Western",
]


def _get_backend_url() -> str:
    try:
        return st.secrets.get("BACKEND_URL", os.environ.get("BACKEND_URL", "http://localhost:5001"))
    except Exception:
        return os.environ.get("BACKEND_URL", "http://localhost:5001")


def _normalize_title(title: str) -> str:
    if not title:
        return title
    title = re.sub(r"\s*\(\d{4}\)\s*$", "", title).strip()
    m = re.search(r",\s*(The|A|An)$", title, re.IGNORECASE)
    if m:
        return f"{m.group(1)} {title[:m.start()].strip()}"
    return title


def _search_movies_es(query: str, limit: int = 10) -> list:
    """Search movies via Elasticsearch backend."""
    if len(query) < 2:
        return []
    try:
        r = requests.get(
            f"{_get_backend_url()}/autocomplete",
            params={"q": query, "limit": limit},
            timeout=2,
        )
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return []


def _tmdb_ids_to_movie_ids(db, tmdb_ids: list) -> list:
    """Convert a list of TMDB IDs to BigQuery movieIds."""
    if not tmdb_ids:
        return []
    clean = [int(x) for x in tmdb_ids if x]
    if not clean:
        return []
    ids_str = ", ".join(str(x) for x in clean)
    try:
        df = db.run_query(
            f"SELECT movieId FROM `{MOVIES_TABLE}` WHERE CAST(tmdbId AS INT64) IN ({ids_str})"
        )
        return df["movieId"].tolist()
    except Exception as e:
        print(f"[HOME] tmdb→movieId conversion failed: {e}")
        return []


# ── State management ──────────────────────────────────────────────────────────

def _init_pv_state():
    defaults = {
        "pv_state": "idle",       # idle | questionnaire | pending | results
        "pv_step": 1,
        "pv_genres": [],
        "pv_year": (1900, 2026),
        "pv_persons": [],          # [{"id": int, "name": str}]
        "pv_liked": [],            # [{"tmdb_id": int, "title": str}]
        "pv_watched": [],          # [{"tmdb_id": int, "title": str, "rating": int}]
        "pv_results": [],
        # Temp search state
        "pv_person_results": [],
        "pv_movie_results": [],
        "pv_watch_results": [],
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _reset_pv():
    keys = [k for k in list(st.session_state.keys()) if k.startswith("pv_")]
    for k in keys:
        del st.session_state[k]


def _go_next_cb():
    step = st.session_state.get("pv_step", 1)
    if step < 5:
        st.session_state.pv_step = step + 1
    else:
        st.session_state.pv_state = "pending"


def _go_skip_cb():
    _go_next_cb()


def _go_back_cb():
    step = st.session_state.get("pv_step", 1)
    if step > 1:
        st.session_state.pv_step = step - 1


# ── Step renderers ────────────────────────────────────────────────────────────

def _render_tag_list(items: list, clear_key: str, state_key: str):
    """Render a horizontal list of selected items as styled pills."""
    if not items:
        return
    pills = []
    for item in items:
        label = item if isinstance(item, str) else item.get("name") or item.get("title", "")
        rating = item.get("rating") if isinstance(item, dict) else None
        color = "#01b4e4"
        if rating is not None:
            color = "#21d07a" if rating >= 4 else "#d2d531" if rating >= 3 else "#db2360"
        suffix = f" — {rating}/5" if rating is not None else ""
        pills.append(
            f"<span style='display:inline-block; background:rgba(255,255,255,0.06); "
            f"border:1px solid rgba(255,255,255,0.12); border-radius:20px; "
            f"padding:4px 14px; margin:3px 4px; font-size:0.88rem; "
            f"color:{color}; font-weight:600;'>{label}{suffix}</span>"
        )
    st.markdown(
        f"<div style='display:flex; flex-wrap:wrap; margin:8px 0 4px 0;'>{''.join(pills)}</div>",
        unsafe_allow_html=True,
    )
    if st.button("Effacer la sélection", key=clear_key):
        st.session_state[state_key] = []
        st.rerun()


def _step_genres():
    selected = st.multiselect(
        "Genres",
        options=_ALL_GENRES,
        default=st.session_state.pv_genres,
        key="pv_genres_select",
        label_visibility="collapsed",
    )
    st.session_state.pv_genres = selected


def _step_year():
    year = st.slider(
        "Période de sortie",
        min_value=1900,
        max_value=2026,
        value=st.session_state.pv_year,
        key="pv_year_slider",
    )
    st.session_state.pv_year = year


def _step_persons(tmdb):
    col_q, col_btn = st.columns([5, 1])
    with col_q:
        query = st.text_input(
            "Rechercher un artiste",
            placeholder="Christopher Nolan, Meryl Streep...",
            key="pv_person_query_input",
        )
    with col_btn:
        st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
        search_clicked = st.button("Rechercher", key="pv_person_search_btn", use_container_width=True)

    if search_clicked and query:
        try:
            results = tmdb.search_person(query) or []
            st.session_state.pv_person_results = results[:6]
        except Exception as e:
            st.error(f"Erreur TMDB : {e}")
            st.session_state.pv_person_results = []

    if st.session_state.pv_person_results:
        people = st.session_state.pv_person_results
        labels = [f"{p['name']} ({p.get('known_for_department', 'N/A')})" for p in people]
        col_sel, col_add = st.columns([5, 1])
        with col_sel:
            selected_label = st.selectbox(
                "Résultats",
                options=labels,
                key="pv_person_sel",
                label_visibility="collapsed",
            )
        with col_add:
            st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
            if st.button("Ajouter", key="pv_person_add", use_container_width=True):
                sel_idx = labels.index(selected_label)
                sel_person = people[sel_idx]
                existing_ids = [p["id"] for p in st.session_state.pv_persons]
                if sel_person["id"] not in existing_ids:
                    st.session_state.pv_persons.append({
                        "id": sel_person["id"],
                        "name": sel_person["name"],
                    })

    _render_tag_list(st.session_state.pv_persons, "pv_person_clear", "pv_persons")


def _step_liked_movies():
    col_q, col_btn = st.columns([5, 1])
    with col_q:
        query = st.text_input(
            "Rechercher un film",
            placeholder="Inception, The Dark Knight...",
            key="pv_liked_query",
        )
    with col_btn:
        st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
        search_clicked = st.button("Rechercher", key="pv_liked_search_btn", use_container_width=True)

    if search_clicked and query:
        st.session_state.pv_movie_results = _search_movies_es(query)

    if st.session_state.pv_movie_results:
        options = st.session_state.pv_movie_results
        labels = [
            f"{_normalize_title(m.get('title', ''))} ({m.get('release_year', '')})"
            for m in options
        ]
        col_sel, col_add = st.columns([5, 1])
        with col_sel:
            selected_label = st.selectbox(
                "Résultats",
                options=labels,
                key="pv_liked_sel",
                label_visibility="collapsed",
            )
        with col_add:
            st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
            if st.button("Ajouter", key="pv_liked_add_btn", use_container_width=True):
                sel_idx = labels.index(selected_label)
                sel_movie = options[sel_idx]
                tmdb_id = sel_movie.get("tmdbId")
                existing = [m["tmdb_id"] for m in st.session_state.pv_liked]
                if tmdb_id and tmdb_id not in existing:
                    st.session_state.pv_liked.append({
                        "tmdb_id": int(tmdb_id),
                        "title": _normalize_title(sel_movie.get("title", "")),
                    })

    _render_tag_list(st.session_state.pv_liked, "pv_liked_clear", "pv_liked")


def _step_watched_movies():
    st.markdown(
        "<p style='color:#999; font-size:0.9rem; margin:0 0 12px 0;'>"
        "Ces films seront exclus des recommandations. "
        "Les films notés 4/5 ou plus serviront aussi de base.</p>",
        unsafe_allow_html=True,
    )

    col_q, col_btn = st.columns([5, 1])
    with col_q:
        query = st.text_input(
            "Rechercher un film",
            placeholder="Titanic, Avengers...",
            key="pv_watch_query",
        )
    with col_btn:
        st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
        search_clicked = st.button("Rechercher", key="pv_watch_search_btn", use_container_width=True)

    if search_clicked and query:
        st.session_state.pv_watch_results = _search_movies_es(query)

    if st.session_state.pv_watch_results:
        options = st.session_state.pv_watch_results
        labels = [
            f"{_normalize_title(m.get('title', ''))} ({m.get('release_year', '')})"
            for m in options
        ]
        col_sel, col_rate, col_add = st.columns([4, 1.5, 1])
        with col_sel:
            selected_label = st.selectbox(
                "Résultats",
                options=labels,
                key="pv_watch_sel",
                label_visibility="collapsed",
            )
        with col_rate:
            rating = st.selectbox("Note", options=[1, 2, 3, 4, 5], index=2, key="pv_watch_rating")
        with col_add:
            st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
            if st.button("Ajouter", key="pv_watch_add_btn", use_container_width=True):
                sel_idx = labels.index(selected_label)
                sel_movie = options[sel_idx]
                tmdb_id = sel_movie.get("tmdbId")
                existing = [m["tmdb_id"] for m in st.session_state.pv_watched]
                if tmdb_id and tmdb_id not in existing:
                    st.session_state.pv_watched.append({
                        "tmdb_id": int(tmdb_id),
                        "title": _normalize_title(sel_movie.get("title", "")),
                        "rating": rating,
                    })

    _render_tag_list(st.session_state.pv_watched, "pv_watch_clear", "pv_watched")


# ── Questionnaire frame ───────────────────────────────────────────────────────

_STEP_TITLES = [
    "Genres préférés",
    "Période de sortie",
    "Artistes favoris",
    "Films aimés",
    "Films déjà vus",
]

@st.dialog("Personnalisez vos recommandations", width="large")
def _questionnaire_dialog(tmdb):
    """Modal dialog for the recommendation questionnaire."""
    step = st.session_state.pv_step

    # Progress bar
    progress_pct = int(step / 5 * 100)
    st.markdown(f"""
    <div style="margin-bottom:1.2rem;">
        <div style="display:flex; justify-content:space-between; align-items:baseline; margin-bottom:8px;">
            <span style="font-weight:700; font-size:1.05rem;">{_STEP_TITLES[step-1]}</span>
            <span style="color:#888; font-size:0.85rem;">Étape {step} sur 5</span>
        </div>
        <div style="height:3px; background:rgba(255,255,255,0.08); border-radius:2px; overflow:hidden;">
            <div style="height:100%; width:{progress_pct}%; background:#38bdf8; border-radius:2px; transition:width 0.3s ease;"></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Step content
    if step == 1:
        _step_genres()
    elif step == 2:
        _step_year()
    elif step == 3:
        _step_persons(tmdb)
    elif step == 4:
        _step_liked_movies()
    elif step == 5:
        _step_watched_movies()

    # Navigation
    st.markdown("<div style='height:0.8rem'></div>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        if step > 1:
            st.button("Précédent", on_click=_go_back_cb, key=f"pv_back_{step}", use_container_width=True)
    with c2:
        st.button("Passer", on_click=_go_skip_cb, key=f"pv_skip_{step}", use_container_width=True)
    with c3:
        if step == 5:
            if st.button("Valider", key=f"pv_next_{step}", type="primary", use_container_width=True):
                st.session_state.pv_state = "pending"
                st.rerun()
        else:
            st.button("Suivant", on_click=_go_next_cb, key=f"pv_next_{step}", type="primary", use_container_width=True)


# ── Recommendation generation ─────────────────────────────────────────────────

def _do_generate(db):
    """Call the Flask /recommend endpoint and store results in session state."""
    liked_tmdb = [m["tmdb_id"] for m in st.session_state.pv_liked]
    watched_tmdb = [m["tmdb_id"] for m in st.session_state.pv_watched]
    high_rated_tmdb = [m["tmdb_id"] for m in st.session_state.pv_watched if m["rating"] >= 4]

    # Seeds = liked + high-rated watched
    all_seed_tmdb = list(set(liked_tmdb + high_rated_tmdb))
    # Excluded = all liked + all watched (to not repeat)
    excluded_tmdb = list(set(liked_tmdb + watched_tmdb))

    liked_movie_ids    = _tmdb_ids_to_movie_ids(db, all_seed_tmdb)
    excluded_movie_ids = _tmdb_ids_to_movie_ids(db, excluded_tmdb)
    person_ids         = [p["id"] for p in st.session_state.pv_persons]

    genres   = st.session_state.pv_genres or None
    year_min, year_max = st.session_state.pv_year
    year_min = year_min if year_min > 1900 else None
    year_max = year_max if year_max < 2026 else None

    payload = {
        "movie_ids":          liked_movie_ids,
        "excluded_movie_ids": excluded_movie_ids if excluded_movie_ids else None,
        "person_tmdb_ids":    person_ids if person_ids else None,
        "genres":             genres,
        "year_min":           year_min,
        "year_max":           year_max,
        "n":                  20,
    }

    try:
        r = requests.post(
            f"{_get_backend_url()}/recommend",
            json=payload,
            timeout=30,
        )
        if r.status_code == 200:
            st.session_state.pv_results = r.json()
        else:
            print(f"[HOME] /recommend returned {r.status_code}: {r.text}")
            st.session_state.pv_results = []
    except Exception as e:
        print(f"[HOME] /recommend failed: {e}")
        st.session_state.pv_results = []

    st.session_state.pv_state = "results"


# ── Results carousel ──────────────────────────────────────────────────────────

def _render_pv_results():
    results = st.session_state.pv_results

    # Summary of preferences used
    summary_parts = []
    if st.session_state.pv_genres:
        summary_parts.append(f"Genres : <b>{', '.join(st.session_state.pv_genres)}</b>")
    if st.session_state.pv_persons:
        summary_parts.append(f"Artistes : <b>{', '.join(p['name'] for p in st.session_state.pv_persons)}</b>")
    liked_count   = len(st.session_state.pv_liked)
    watched_count = len(st.session_state.pv_watched)
    if liked_count:
        summary_parts.append(f"<b>{liked_count}</b> film(s) aimé(s)")
    if watched_count:
        summary_parts.append(f"<b>{watched_count}</b> film(s) exclus")

    if summary_parts:
        st.markdown(
            "<div style='color:#666; font-size:0.85rem; margin-bottom:0.8rem; padding:0 4%;'>"
            + " &middot; ".join(summary_parts) + "</div>",
            unsafe_allow_html=True,
        )

    if not results:
        st.warning("Aucune recommandation trouvée. Essayez d'ajuster vos préférences.")
    else:
        # Build cards HTML
        cards_html = ""
        for m in results:
            tmdb_id  = m.get("tmdbId") or m.get("tmdb_id") or ""
            title    = m.get("title", "")
            year     = m.get("release_year", "")
            rating   = m.get("avg_pred") or m.get("avg_rating") or 0
            poster   = m.get("poster_url")
            if not poster:
                safe_t = _normalize_title(title).replace(" ", "+")[:30]
                poster = f"https://placehold.co/500x750/1a1a2e/ffffff?text={safe_t}"
            cards_html += (
                f'<div class="poster-card">'
                f'{components.build_tmdb_card(title, year, rating, poster, tmdb_id, from_page="home")}'
                f"</div>"
            )

        # Render carousel in an iframe so it has full CSS + JS
        carousel_html = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  {styles.get_css()}
  <style>
    body {{ background: transparent; margin: 0; padding: 0; overflow-x: hidden; }}
    .pv-carousel-root {{ padding: 0 0 1.5rem 0; }}
  </style>
</head>
<body>
<div class="pv-carousel-root">
  <div class="carousel-wrapper">
    <button class="scroll-btn left" onclick="slideLeft(this)">&#10094;</button>
    <div class="posters-container">
      {cards_html}
    </div>
    <button class="scroll-btn right" onclick="slideRight(this)">&#10095;</button>
  </div>
</div>
<script>
function slideLeft(btn) {{
  const c = btn.parentElement.querySelector('.posters-container');
  c.scrollBy({{ left: -c.clientWidth * 0.8, behavior: 'smooth' }});
}}
function slideRight(btn) {{
  const c = btn.parentElement.querySelector('.posters-container');
  c.scrollBy({{ left: c.clientWidth * 0.8, behavior: 'smooth' }});
}}
</script>
</body>
</html>
"""
        st.components.v1.html(carousel_html, height=380, scrolling=False)

    # Action buttons — right-aligned, compact
    _, col_regen, col_reset = st.columns([3, 1.5, 1.5])
    with col_regen:
        if st.button("Modifier les préférences", key="pv_regen", use_container_width=True):
            st.session_state.pv_state = "questionnaire"
            st.session_state.pv_step = 1
            st.rerun()
    with col_reset:
        if st.button("Réinitialiser", key="pv_reset", use_container_width=True):
            _reset_pv()
            st.rerun()


# ── Main "Pour vous" section ──────────────────────────────────────────────────

def _render_pour_vous(db, tmdb):
    _init_pv_state()

    state = st.session_state.pv_state

    # Section title — matches existing row-title style (blue bar + bold text)
    st.markdown("""
    <div style="
        display:flex; align-items:center; gap:10px;
        margin: 0.6rem 0 0.6rem 0;
        padding: 0 4%;
    ">
        <div style="width:4px; height:1.2rem; background:#38bdf8; border-radius:2px; flex-shrink:0;"></div>
        <span style="font-size:1.4rem; font-weight:700; color:#FFFFFF;">Recommandations personnalisées</span>
    </div>
    """, unsafe_allow_html=True)

    # ── Idle / Questionnaire — show CTA, dialog opens on top ─────────────────
    if state in ("idle", "questionnaire"):
        st.markdown(
            "<p style='color:#888; font-size:0.95rem; margin:0 0 1rem 0; padding:0 4%;'>"
            "Obtenez des suggestions basées sur vos goûts, vos artistes favoris et les films que vous avez vus."
            "</p>",
            unsafe_allow_html=True,
        )
        _, col_btn, _ = st.columns([3, 2, 3])
        with col_btn:
            if st.button("Personnaliser", key="pv_start_btn", use_container_width=True, type="primary"):
                st.session_state.pv_state = "questionnaire"
                st.session_state.pv_step = 1
                st.rerun()

        # Open dialog overlay when in questionnaire state
        if state == "questionnaire":
            _questionnaire_dialog(tmdb)

    # ── Pending (generating) ──────────────────────────────────────────────────
    elif state == "pending":
        with st.spinner("Génération en cours..."):
            _do_generate(db)
        st.rerun()

    # ── Results ───────────────────────────────────────────────────────────────
    elif state == "results":
        _render_pv_results()


# ─────────────────────────────────────────────────────────────────────────────
# Shared JS helpers (injected into every iframe)
# ─────────────────────────────────────────────────────────────────────────────

_CAROUSEL_JS = """
function slideLeft(btn) {
    const container = btn.parentElement.querySelector('.posters-container');
    container.scrollBy({ left: -container.clientWidth * 0.8, behavior: 'smooth' });
}
function slideRight(btn) {
    const container = btn.parentElement.querySelector('.posters-container');
    container.scrollBy({ left: container.clientWidth * 0.8, behavior: 'smooth' });
}
function showSql(id) {
    document.getElementById('sql-modal-' + id).style.display = 'flex';
}
function hideSql(id) {
    document.getElementById('sql-modal-' + id).style.display = 'none';
}
"""


# ─────────────────────────────────────────────────────────────────────────────
# Main render
# ─────────────────────────────────────────────────────────────────────────────

def render(db, qb, tmdb) -> None:
    top_movies, top_sql, genre_data, decade_data, decade_sql = _fetch_home_data_v2(db, qb, tmdb)

    if not top_movies:
        st.error("No data available.")
        return

    # ── Full-Width Navigation ────────────────────────────────────────────────
    styles.render_navbar("home")

    # ── Hero Section ───────────────────────────────────────────────────────────
    slides_html = ""
    for i, m in enumerate(top_movies):
        delay = i * 20  # 20s per slide
        slides_html += f"""
        <div class="hero-slide" style="background-image: url('{m['backdrop']}'); animation-delay: {delay}s;">
            <div class="hero-fade"></div>
            <div class="hero-content">
                <div class="hero-rank">{m['rank']}</div>
                <div class="hero-details">
                    <div class="hero-title">{m['title']}</div>
                    <div class="hero-summary">{m['overview']}</div>
                    <div class="hero-buttons">
                        <a href="/?page=movie&movie_id={m['tmdbId']}&from=home" target="_self" class="btn btn-primary">Plus d'info</a>
                    </div>
                </div>
            </div>
        </div>
        """

    hero_html = f"""
    <div class="hero-container">
        {slides_html}
    </div>
    """

    # ── Generate Modals ────────────────────────────────────────────────────────
    genre_sql = next(iter(genre_data.values()))["sql"] if genre_data else ""

    modals_html = "".join([
        components.render_sql_modal("top10", "Top 10 All Time SQL", top_sql),
        components.render_sql_modal("genre", "Top 10 Category (Window Function)", genre_sql),
        components.render_sql_modal("decade", "Top 20 by Decade SQL", decade_sql)
    ])

    # ── Row 1: Top 10 All Time ─────────────────────────────────────────────────
    top10_cards_html = ""
    for m in top_movies:
        card = components.build_tmdb_card(m['title'], m['year'], m['rating'], m['poster'], m['tmdbId'], from_page="home")
        top10_cards_html += f"""
        <div class="top10-card">
            <div class="top10-number">{m['rank']}</div>
            <div style="flex:1; position: relative; z-index: 2;">
                {card}
            </div>
        </div>
        """

    top10_row = f"""
    <div class="row-section first-row">
        <div class="row-header">
            <div class="row-title">
                Top 10 Global
                {components.render_info_icon('top10', "Le classement est établi selon le nombre total d'évaluations et la note moyenne des utilisateurs.")}
            </div>
        </div>
        <div class="carousel-wrapper">
            <button class="scroll-btn left" onclick="slideLeft(this)">&#10094;</button>
            <div class="posters-container">
                {top10_cards_html}
            </div>
            <button class="scroll-btn right" onclick="slideRight(this)">&#10095;</button>
        </div>
    </div>
    """

    # ── Row 2: Top 10 by Dynamic Genre ─────────────────────────────────────────
    category_items_html = ""
    genre_containers_html = ""

    first_genre = True
    sorted_genres = sorted(genre_data.keys())
    for label in sorted_genres:
        data = genre_data[label]
        safe_label = label.replace("é", "e").replace("-", "").replace(" ", "")

        active_class = "active" if first_genre else ""
        category_items_html += f'<div class="category-item {active_class}" onclick="switchGenre(\'{safe_label}\', \'{label}\', this)">{label}</div>'

        display_style = "display: block;" if first_genre else "display: none;"

        cards_html = "".join([
            f'<div class="top10-card"><div class="top10-number">{p["rank"]}</div><div style="flex:1; position: relative; z-index: 2;">{components.build_tmdb_card(p["title"], p["year"], p["rating"], p["poster"], p["tmdbId"], from_page="home")}</div></div>'
            for p in data['movies']
        ])

        genre_containers_html += f"""
        <div id="genre-carousel-{safe_label}" class="genre-carousel-group" style="{display_style}">
            <div class="carousel-wrapper">
                <button class="scroll-btn left" onclick="slideLeft(this)">&#10094;</button>
                <div class="posters-container">
                    {cards_html}
                </div>
                <button class="scroll-btn right" onclick="slideRight(this)">&#10095;</button>
            </div>
        </div>
        """
        first_genre = False

    genre_row = f"""
    <div class="row-section">
        <div class="row-header" style="justify-content: space-between; align-items: center;">
            <div class="row-title" style="margin-bottom:0;">
                Top 10&nbsp;<span id="selected-genre-name">{sorted_genres[0]}</span>
                {components.render_info_icon('genre', "Top 10 des films les plus populaires pour ce genre spécifique.")}
            </div>
            <div class="category-nav-wrapper">
                <div class="category-nav">
                    {category_items_html}
                </div>
            </div>
        </div>
        {genre_containers_html}
    </div>
    """

    # ── Row 3: Grands succès par Décennie ──────────────────────────────────────
    decade_items_html = ""
    decade_containers_html = ""

    first_dec = True
    ordered_labels = ["60s", "70s", "80s", "90s", "2000s", "2010s"]
    for label in ordered_labels:
        if label not in decade_data:
            continue
        data = decade_data[label]
        safe_dec = label.replace("s", "")

        active_class = "active" if first_dec else ""
        decade_items_html += f'<div class="category-item {active_class}" onclick="switchDecade(\'{safe_dec}\', \'{label}\', this)">{label}</div>'

        display_style = "display: block;" if first_dec else "display: none;"

        cards_html = "".join([
            f'<div class="poster-card" style="border-radius:8px; overflow:visible;">{components.build_tmdb_card(p["title"], p["year"], p["rating"], p["poster"], p["tmdbId"], from_page="home")}</div>'
            for p in data['movies']
        ])

        decade_containers_html += f"""
        <div id="decade-carousel-{safe_dec}" class="genre-carousel-group" style="{display_style}">
            <div class="carousel-wrapper">
                <button class="scroll-btn left" onclick="slideLeft(this)">&#10094;</button>
                <div class="posters-container">
                    {cards_html}
                </div>
                <button class="scroll-btn right" onclick="slideRight(this)">&#10095;</button>
            </div>
        </div>
        """
        first_dec = False

    decade_row = f"""
    <div class="row-section" style="margin-bottom: 4rem;">
        <div class="row-header" style="justify-content: space-between; align-items: center;">
            <div class="row-title" style="margin-bottom:0;">
                Grands succès des&nbsp;<span id="selected-decade-name">{ordered_labels[0]}</span>
                {components.render_info_icon('decade', "Les films les plus populaires de cette décennie.")}
            </div>
            <div class="category-nav-wrapper">
                <div class="category-nav">
                    {decade_items_html}
                </div>
            </div>
        </div>
        {decade_containers_html}
    </div>
    """

    # ──────────────────────────────────────────────────────────────────────────
    # IFRAME 1 : Hero + Top 10 Global + Top 10 par Genre
    # ──────────────────────────────────────────────────────────────────────────
    html_part1 = f"""
    <html>
    <head>{styles.get_css()}</head>
    <body>
        <div style="height: 0px;"></div>
        {hero_html}
        {top10_row}
        {genre_row}
        {modals_html}

        <script>
        {_CAROUSEL_JS}
        function switchGenre(safeLabel, originalLabel, clickedEl) {{
            document.querySelectorAll('.genre-carousel-group').forEach(el => el.style.display = 'none');
            document.getElementById('genre-carousel-' + safeLabel).style.display = 'block';
            document.getElementById('selected-genre-name').innerText = originalLabel;
            if (clickedEl) {{
                document.querySelectorAll('.category-item').forEach(el => el.classList.remove('active'));
                clickedEl.classList.add('active');
                const navContainer = document.querySelector('.category-nav');
                const scrollLeft = clickedEl.offsetLeft - (navContainer.offsetWidth / 2) + (clickedEl.offsetWidth / 2);
                navContainer.scrollTo({{ left: scrollLeft, behavior: 'smooth' }});
            }}
        }}

        // Scroll management for full-width navbar
        let lastScrollY = window.scrollY;
        const navWrapper = document.getElementById('nav-wrapper');
        window.addEventListener('scroll', () => {{
            const currentScrollY = window.scrollY;
            if (currentScrollY > lastScrollY && currentScrollY > 70) {{
                navWrapper.classList.add('nav-hidden');
            }} else {{
                navWrapper.classList.remove('nav-hidden');
            }}
            lastScrollY = currentScrollY;
        }});
        </script>
    </body>
    </html>
    """
    st.components.v1.html(html_part1, height=1800, scrolling=True)

    # ──────────────────────────────────────────────────────────────────────────
    # "Pour vous" – Native Streamlit (between genres & decades)
    # ──────────────────────────────────────────────────────────────────────────
    _render_pour_vous(db, tmdb)

    # ──────────────────────────────────────────────────────────────────────────
    # IFRAME 2 : Grands succès par Décennie
    # ──────────────────────────────────────────────────────────────────────────
    html_part2 = f"""
    <html>
    <head>{styles.get_css()}</head>
    <body>
        {decade_row}
        {components.render_sql_modal("decade2", "Top 20 by Decade SQL", decade_sql)}

        <script>
        {_CAROUSEL_JS}
        function switchDecade(safeLabel, originalLabel, clickedEl) {{
            document.querySelectorAll('[id^="decade-carousel-"]').forEach(el => el.style.display = 'none');
            document.getElementById('decade-carousel-' + safeLabel).style.display = 'block';
            document.getElementById('selected-decade-name').innerText = originalLabel;
            if (clickedEl) {{
                const wrapper = clickedEl.parentElement;
                wrapper.querySelectorAll('.category-item').forEach(el => el.classList.remove('active'));
                clickedEl.classList.add('active');
            }}
        }}
        </script>
    </body>
    </html>
    """
    st.components.v1.html(html_part2, height=600, scrolling=False)
