"""
ui/sidebar.py – Sidebar filters and search controls.

render(db, qb) → dict of selected filter values
"""

from __future__ import annotations

import streamlit as st


@st.cache_data(ttl=3600, show_spinner="Loading languages…")
def _load_languages(_run_query, _build_distinct_languages_query) -> list[str]:
    sql = _build_distinct_languages_query()
    df = _run_query(sql)
    langs = df["language"].dropna().tolist() if "language" in df.columns else []
    return ["All"] + sorted(set(langs))


@st.cache_data(ttl=3600, show_spinner="Loading genres…")
def _load_genres(_run_query, _build_distinct_genres_query) -> list[str]:
    sql = _build_distinct_genres_query()
    df = _run_query(sql)
    return df["genre"].dropna().tolist() if "genre" in df.columns else []


@st.cache_data(ttl=600, show_spinner=False)
def _has_ratings(_run_query, ratings_table: str) -> bool:
    try:
        _run_query(f"SELECT 1 FROM `{ratings_table}` LIMIT 1")
        return True
    except Exception:
        return False


def render(db, qb) -> dict:
    """
    Render the sidebar and return a dict of user-selected filter values.

    Returns
    -------
    {
        "title": str,
        "language": str,
        "genres": list[str],
        "min_rating": float,
        "min_year": int,
        "search_clicked": bool,
        "has_ratings": bool,
    }
    """
    with st.sidebar:
        st.markdown("## 🔍 Search & Filters")
        st.markdown("---")

        title_input = st.text_input(
            "🎬 Movie Title",
            placeholder="Start typing a title…",
            help="Searches with SQL LIKE '%…%'",
        )

        # Autocomplete suggestions
        if title_input.strip():
            try:
                ac_sql = qb.build_movie_title_search_query(title_input, limit=10)
                ac_df = db.run_query(ac_sql)
                if not ac_df.empty:
                    suggestions = ac_df["title"].tolist()
                    st.caption(f"💡 {len(suggestions)} suggestion(s)")
                    for s in suggestions[:5]:
                        st.markdown(f"<span class='pill'>🎥 {s}</span>", unsafe_allow_html=True)
            except Exception:
                pass

        st.markdown("---")

        try:
            languages = _load_languages(db.run_query, qb.build_distinct_languages_query)
        except Exception:
            languages = ["All"]
            st.warning("Could not load languages from BigQuery.")

        try:
            genres_list = _load_genres(db.run_query, qb.build_distinct_genres_query)
        except Exception:
            genres_list = []
            st.warning("Could not load genres from BigQuery.")

        language_sel = st.selectbox("🌍 Language", options=languages)
        genres_sel = st.multiselect("🎭 Genres", options=genres_list, default=[])

        st.markdown("---")

        min_rating_sel = st.slider(
            "⭐ Min. Average Rating",
            min_value=0.0, max_value=5.0, value=0.0, step=0.5,
            help="Requires a JOIN on the ratings table (0 = no filter)",
        )
        min_year_sel = st.slider(
            "📅 Released After",
            min_value=1900, max_value=2025, value=1900, step=1,
        )

        st.markdown("---")
        search_btn = st.button("🔎 Search", use_container_width=True, type="primary")

        has_ratings = _has_ratings(db.run_query, db.RATINGS_TABLE)
        if not has_ratings:
            st.info("ℹ️ Ratings table not found — rating filter disabled.")

    return {
        "title": title_input,
        "language": language_sel,
        "genres": genres_sel,
        "min_rating": min_rating_sel,
        "min_year": min_year_sel,
        "search_clicked": search_btn,
        "has_ratings": has_ratings,
    }
