"""
app.py – Streamlit UI layer (logic + UI combined, as per assignment spec)
Architecture:
  Layer 1: Database  →  db.py
  Layer 2: Logic/UI  →  app.py  (uses query_builder.py + tmdb.py)
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

import db
import query_builder as qb
import tmdb

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="🎬 Movie Explorer",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS for premium look ────────────────────────────────────────────────
st.markdown(
    """
<style>
/* Google Font */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

/* Dark gradient hero header */
.hero-header {
    background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
    border-radius: 16px;
    padding: 2.5rem 2rem;
    margin-bottom: 1.5rem;
    color: white;
}
.hero-header h1 { font-size: 2.6rem; font-weight: 700; margin: 0; }
.hero-header p  { font-size: 1.1rem; opacity: 0.75; margin: 0.4rem 0 0; }

/* Metric cards */
.metric-card {
    background: linear-gradient(135deg, #1a1a2e, #16213e);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 12px;
    padding: 1.2rem 1.5rem;
    color: white;
    text-align: center;
}
.metric-card .label { font-size: 0.78rem; opacity: 0.65; text-transform: uppercase; letter-spacing: .08em; }
.metric-card .value { font-size: 2rem; font-weight: 700; color: #a78bfa; }

/* Result table tweaks */
[data-testid="stDataFrame"] { border-radius: 12px; overflow: hidden; }

/* Sidebar */
[data-testid="stSidebar"] { background: linear-gradient(180deg, #0d0d1a 0%, #1a1a2e 100%); }
[data-testid="stSidebar"] * { color: #e2e8f0 !important; }
[data-testid="stSidebar"] label { font-weight: 600; }

/* SQL expander */
.stExpander { border: 1px solid rgba(167,139,250,.3) !important; border-radius: 8px !important; }

/* Pill badges */
.pill {
    display: inline-block;
    background: rgba(167,139,250,0.18);
    border: 1px solid rgba(167,139,250,0.4);
    color: #a78bfa;
    border-radius: 999px;
    padding: 2px 12px;
    font-size: 0.78rem;
    margin: 2px;
}

/* Movie detail card */
.detail-card {
    background: linear-gradient(135deg, #1a1a2e, #16213e);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 16px;
    padding: 1.5rem;
    color: white;
}
.cast-card {
    text-align: center;
    padding: 0.5rem;
    background: rgba(255,255,255,0.04);
    border-radius: 10px;
}
.cast-name { font-weight: 600; font-size: 0.82rem; color: #e2e8f0; }
.cast-char { font-size: 0.75rem; color: #94a3b8; }
</style>
""",
    unsafe_allow_html=True,
)


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner="Loading languages…")
def load_languages() -> list[str]:
    sql = qb.build_distinct_languages_query()
    df = db.run_query(sql)
    langs = df["language"].dropna().tolist() if "language" in df.columns else []
    return ["All"] + sorted(set(langs))


@st.cache_data(ttl=3600, show_spinner="Loading genres…")
def load_genres() -> list[str]:
    sql = qb.build_distinct_genres_query()
    df = db.run_query(sql)
    return df["genre"].dropna().tolist() if "genre" in df.columns else []


def check_ratings_table() -> bool:
    """Check whether the ratings table exists in BigQuery."""
    try:
        sql = f"SELECT 1 FROM `{db.RATINGS_TABLE}` LIMIT 1"
        db.run_query(sql)
        return True
    except Exception:
        return False


@st.cache_data(ttl=600, show_spinner="Running query…")
def search_movies(
    title: str,
    language: str,
    genres: tuple[str, ...],
    min_rating: float,
    min_year: int,
    has_ratings: bool,
) -> tuple[pd.DataFrame, str]:
    sql = qb.build_movie_search_query(
        title=title,
        language=language,
        genres=list(genres),
        min_rating=min_rating,
        min_year=min_year,
        has_ratings_table=has_ratings,
    )
    df = db.run_query(sql)
    return df, sql


# ──────────────────────────────────────────────────────────────────────────────
# Sidebar – Filters
# ──────────────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## 🔍 Search & Filters")
    st.markdown("---")

    # Title autocomplete
    title_input = st.text_input(
        "🎬 Movie Title",
        placeholder="Start typing a title…",
        help="Searches with SQL LIKE '%…%'",
    )

    # Autocomplete suggestions (shown below input while typing)
    if title_input.strip():
        ac_sql = qb.build_autocomplete_query(title_input)
        ac_df = db.run_query(ac_sql)
        if not ac_df.empty:
            suggestions = ac_df["title"].tolist()
            st.caption(f"💡 {len(suggestions)} suggestion(s)")
            for s in suggestions[:5]:
                st.markdown(f"<span class='pill'>🎥 {s}</span>", unsafe_allow_html=True)

    st.markdown("---")

    # Load filter options (cached)
    try:
        languages = load_languages()
    except Exception:
        languages = ["All"]
        st.warning("Could not load languages from BigQuery.")

    try:
        genres_list = load_genres()
    except Exception:
        genres_list = []
        st.warning("Could not load genres from BigQuery.")

    language_sel = st.selectbox("🌍 Language", options=languages)
    genres_sel = st.multiselect("🎭 Genres", options=genres_list, default=[])

    st.markdown("---")

    min_rating_sel = st.slider(
        "⭐ Min. Average Rating",
        min_value=0.0,
        max_value=5.0,
        value=0.0,
        step=0.5,
        help="Requires a JOIN on the ratings table (0 = no filter)",
    )
    min_year_sel = st.slider(
        "📅 Released After",
        min_value=1900,
        max_value=2025,
        value=1900,
        step=1,
    )

    st.markdown("---")
    search_btn = st.button("🔎 Search", use_container_width=True, type="primary")

    # Ratings table availability check (cached)
    @st.cache_data(ttl=600, show_spinner=False)
    def _has_ratings() -> bool:
        return check_ratings_table()

    has_ratings = _has_ratings()
    if not has_ratings:
        st.info("ℹ️ Ratings table not found — rating filter disabled.")


# ──────────────────────────────────────────────────────────────────────────────
# Hero Header
# ──────────────────────────────────────────────────────────────────────────────

st.markdown(
    """
<div class="hero-header">
  <h1>🎬 Movie Explorer</h1>
  <p>Search millions of films with real-time SQL queries on Google BigQuery</p>
</div>
""",
    unsafe_allow_html=True,
)


# ──────────────────────────────────────────────────────────────────────────────
# Main Content
# ──────────────────────────────────────────────────────────────────────────────

tab_search, tab_charts = st.tabs(["🔍 Search Results", "📊 Dataset Overview"])

# ── Tab 1: Search Results ─────────────────────────────────────────────────────
with tab_search:

    # Trigger search on button click OR when any filter changes
    if search_btn or title_input or genres_sel or language_sel != "All" or min_rating_sel > 0 or min_year_sel > 1900:
        try:
            with st.spinner("Querying BigQuery…"):
                df_results, executed_sql = search_movies(
                    title=title_input,
                    language=language_sel,
                    genres=tuple(genres_sel),
                    min_rating=min_rating_sel if has_ratings else 0.0,
                    min_year=min_year_sel,
                    has_ratings=has_ratings,
                )

            # ── Metrics row ───────────────────────────────────────────────────
            col_m1, col_m2, col_m3 = st.columns(3)
            with col_m1:
                st.markdown(
                    f"""<div class="metric-card">
                    <div class="label">Results Found</div>
                    <div class="value">{len(df_results)}</div></div>""",
                    unsafe_allow_html=True,
                )
            with col_m2:
                if "release_year" in df_results.columns and not df_results.empty:
                    yr_range = f"{int(df_results['release_year'].min())} – {int(df_results['release_year'].max())}"
                else:
                    yr_range = "—"
                st.markdown(
                    f"""<div class="metric-card">
                    <div class="label">Year Range</div>
                    <div class="value" style="font-size:1.3rem">{yr_range}</div></div>""",
                    unsafe_allow_html=True,
                )
            with col_m3:
                if "avg_rating" in df_results.columns and not df_results.empty:
                    avg = f"{df_results['avg_rating'].mean():.2f}"
                else:
                    avg = "—"
                st.markdown(
                    f"""<div class="metric-card">
                    <div class="label">Avg Rating</div>
                    <div class="value">{avg}</div></div>""",
                    unsafe_allow_html=True,
                )

            st.markdown("<br>", unsafe_allow_html=True)

            # ── SQL Expander ──────────────────────────────────────────────────
            with st.expander("🧾 View Executed SQL", expanded=False):
                st.code(executed_sql, language="sql")

            # ── Results DataFrame ─────────────────────────────────────────────
            if df_results.empty:
                st.info("No movies found matching your filters. Try broadening your search.")
            else:
                # Columns to display
                display_cols = [
                    c for c in ["title", "genres", "language", "release_year", "country", "avg_rating"]
                    if c in df_results.columns
                ]
                st.dataframe(
                    df_results[display_cols],
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "title": st.column_config.TextColumn("🎬 Title"),
                        "genres": st.column_config.TextColumn("🎭 Genres"),
                        "language": st.column_config.TextColumn("🌍 Language"),
                        "release_year": st.column_config.NumberColumn("📅 Year", format="%d"),
                        "country": st.column_config.TextColumn("🗺️ Country"),
                        "avg_rating": st.column_config.NumberColumn("⭐ Rating", format="%.2f"),
                    },
                )

                # ── Movie Detail Section ──────────────────────────────────────
                st.markdown("---")
                st.markdown("### 🎥 Movie Details")

                movie_titles = df_results["title"].tolist()
                selected_title = st.selectbox(
                    "Select a movie for details:",
                    options=["— choose a movie —"] + movie_titles,
                )

                if selected_title and selected_title != "— choose a movie —":
                    row = df_results[df_results["title"] == selected_title].iloc[0]
                    tmdb_id = row.get("tmdbId") or row.get("movieId")

                    if tmdb_id and str(tmdb_id).strip() not in ("", "nan"):
                        with st.spinner("Fetching TMDB data…"):
                            details = tmdb.fetch_movie_details(tmdb_id)
                    else:
                        details = {}

                    # Layout: poster | info
                    col_poster, col_info = st.columns([1, 2], gap="large")

                    with col_poster:
                        if details.get("poster_url"):
                            st.image(details["poster_url"], use_container_width=True)
                        else:
                            st.markdown(
                                """<div style="background:#1a1a2e;border-radius:12px;height:360px;
                                display:flex;align-items:center;justify-content:center;color:#64748b;
                                font-size:3rem;">🎬</div>""",
                                unsafe_allow_html=True,
                            )

                    with col_info:
                        st.markdown(f"## {row['title']}")
                        if details.get("tagline"):
                            st.markdown(f"*{details['tagline']}*")

                        genre_html = " ".join(
                            f"<span class='pill'>{g}</span>"
                            for g in (details.get("genres") or str(row.get("genres", "")).split("|"))
                        )
                        st.markdown(genre_html, unsafe_allow_html=True)
                        st.markdown("<br>", unsafe_allow_html=True)

                        # Key facts
                        info_col1, info_col2 = st.columns(2)
                        with info_col1:
                            if details.get("vote_average"):
                                st.metric("⭐ TMDB Rating", f"{details['vote_average']:.1f} / 10")
                            if row.get("release_year"):
                                st.metric("📅 Release Year", int(row["release_year"]))
                        with info_col2:
                            if row.get("country"):
                                st.metric("🗺️ Country", row["country"])
                            if row.get("language"):
                                st.metric("🌍 Language", row["language"])

                        if details.get("overview"):
                            st.markdown("#### 📖 Overview")
                            st.markdown(details["overview"])

                        if details.get("homepage"):
                            st.markdown(f"🔗 [Official Website]({details['homepage']})")

                    # Cast section
                    if details.get("cast"):
                        st.markdown("#### 🎭 Cast")
                        cast_cols = st.columns(min(len(details["cast"]), 4))
                        for i, actor in enumerate(details["cast"][:4]):
                            with cast_cols[i]:
                                if actor.get("profile_url"):
                                    st.image(actor["profile_url"], use_container_width=True)
                                else:
                                    st.markdown(
                                        "<div style='background:#1a1a2e;border-radius:8px;height:120px;"
                                        "display:flex;align-items:center;justify-content:center;"
                                        "color:#64748b;font-size:2rem;'>👤</div>",
                                        unsafe_allow_html=True,
                                    )
                                st.markdown(
                                    f"<div class='cast-card'>"
                                    f"<div class='cast-name'>{actor['name']}</div>"
                                    f"<div class='cast-char'>{actor['character']}</div>"
                                    f"</div>",
                                    unsafe_allow_html=True,
                                )

        except Exception as e:
            st.error(f"❌ Error querying BigQuery: {e}")
            st.info("Make sure your BigQuery credentials are configured in `.streamlit/secrets.toml`.")

    else:
        st.markdown(
            """
<div style="text-align:center;padding:4rem 2rem;color:#64748b;">
  <div style="font-size:5rem">🎬</div>
  <h3 style="color:#94a3b8">Start your search</h3>
  <p>Use the sidebar filters to search for movies — results will appear here.</p>
</div>
""",
            unsafe_allow_html=True,
        )


# ── Tab 2: Dataset Overview Charts ────────────────────────────────────────────
with tab_charts:
    st.markdown("### 📊 Dataset Overview")
    col_chart1, col_chart2 = st.columns(2, gap="large")

    with col_chart1:
        st.markdown("#### Top Genres by Movie Count")
        try:
            with st.spinner("Loading genre distribution…"):
                sql_genre = qb.build_genre_distribution_query()
                df_genre = db.run_query(sql_genre)
            if not df_genre.empty:
                with st.expander("SQL", expanded=False):
                    st.code(sql_genre, language="sql")
                st.bar_chart(df_genre.set_index("genre")["movie_count"])
        except Exception as e:
            st.warning(f"Could not load genre chart: {e}")

    with col_chart2:
        st.markdown("#### Movies Released Per Year (since 1980)")
        try:
            with st.spinner("Loading year distribution…"):
                sql_year = qb.build_year_distribution_query(min_year=1980)
                df_year = db.run_query(sql_year)
            if not df_year.empty:
                with st.expander("SQL", expanded=False):
                    st.code(sql_year, language="sql")
                st.line_chart(df_year.set_index("release_year")["movie_count"])
        except Exception as e:
            st.warning(f"Could not load year chart: {e}")
