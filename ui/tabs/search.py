"""
ui/tabs/search.py – Tab 1: Search Results + Movie Detail.
"""

from __future__ import annotations

import streamlit as st

from ui.components import (
    render_empty_state,
    render_metric_card,
    render_no_poster,
    render_sql_expander,
)


@st.cache_data(ttl=600, show_spinner="Running query…")
def _search_movies(_run_query, _build_query, title, language, genres, min_rating, min_year, has_ratings):
    sql = _build_query(
        title=title,
        language=language,
        genres=list(genres),
        min_rating=min_rating,
        min_year=min_year,
        has_ratings_table=has_ratings,
    )
    df = _run_query(sql)
    return df, sql


def render(filters: dict, db, qb, tmdb) -> None:
    """
    Render the Search Results tab.

    Parameters
    ----------
    filters : dict returned by ui.sidebar.render()
    db      : db module
    qb      : query_builder module
    tmdb    : tmdb module
    """
    active = (
        filters["search_clicked"]
        or filters["title"]
        or filters["genres"]
        or filters["language"] != "All"
        or filters["min_rating"] > 0
        or filters["min_year"] > 1900
    )

    if not active:
        render_empty_state(
            "🎬",
            "Start your search",
            "Use the sidebar filters to search for movies — results will appear here.",
        )
        return

    try:
        with st.spinner("Querying BigQuery…"):
            df, sql = _search_movies(
                db.run_query,
                qb.build_movie_search_query,
                title=filters["title"],
                language=filters["language"],
                genres=tuple(filters["genres"]),
                min_rating=filters["min_rating"] if filters["has_ratings"] else 0.0,
                min_year=filters["min_year"],
                has_ratings=filters["has_ratings"],
            )
    except Exception as e:
        st.error(f"❌ Error querying BigQuery: {e}")
        st.info("Make sure your BigQuery credentials are configured in `.streamlit/secrets.toml`.")
        return

    # ── Metrics row ───────────────────────────────────────────────────────────
    col_m1, col_m2, col_m3 = st.columns(3)
    with col_m1:
        render_metric_card("Results Found", str(len(df)))
    with col_m2:
        if "release_year" in df.columns and not df.empty:
            yr = f"{int(df['release_year'].min())} – {int(df['release_year'].max())}"
        else:
            yr = "—"
        render_metric_card("Year Range", yr)
    with col_m3:
        avg = f"{df['avg_rating'].mean():.2f}" if "avg_rating" in df.columns and not df.empty else "—"
        render_metric_card("Avg Rating", avg)

    st.markdown("<br>", unsafe_allow_html=True)
    render_sql_expander(sql, "🧾 View Executed SQL")

    # ── Results table ─────────────────────────────────────────────────────────
    if df.empty:
        st.info("No movies found matching your filters. Try broadening your search.")
        return

    display_cols = [c for c in ["title", "genres", "language", "release_year", "country", "avg_rating"] if c in df.columns]
    st.dataframe(
        df[display_cols],
        use_container_width=True,
        hide_index=True,
        column_config={
            "title":        st.column_config.TextColumn("🎬 Title"),
            "genres":       st.column_config.TextColumn("🎭 Genres"),
            "language":     st.column_config.TextColumn("🌍 Language"),
            "release_year": st.column_config.NumberColumn("📅 Year", format="%d"),
            "country":      st.column_config.TextColumn("🗺️ Country"),
            "avg_rating":   st.column_config.NumberColumn("⭐ Rating", format="%.2f"),
        },
    )

    # ── Movie detail panel ────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 🎥 Movie Details")

    selected_title = st.selectbox(
        "Select a movie for details:",
        options=["— choose a movie —"] + df["title"].tolist(),
    )
    if not selected_title or selected_title == "— choose a movie —":
        return

    row = df[df["title"] == selected_title].iloc[0]
    tmdb_id = row.get("tmdbId") or row.get("movieId")

    details = {}
    if tmdb_id and str(tmdb_id).strip() not in ("", "nan"):
        with st.spinner("Fetching TMDB data…"):
            details = tmdb.fetch_movie_details(tmdb_id)

    col_poster, col_info = st.columns([1, 2], gap="large")

    with col_poster:
        if details.get("poster_url"):
            st.image(details["poster_url"], use_container_width=True)
        else:
            render_no_poster(height=360)

    with col_info:
        st.markdown(f"## {row['title']}")
        if details.get("tagline"):
            st.markdown(f"*{details['tagline']}*")

        genres_src = details.get("genres") or str(row.get("genres", "")).split("|")
        genre_html = " ".join(f"<span class='pill'>{g}</span>" for g in genres_src)
        st.markdown(genre_html, unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

        inf1, inf2 = st.columns(2)
        with inf1:
            if details.get("vote_average"):
                st.metric("⭐ TMDB Rating", f"{details['vote_average']:.1f} / 10")
            if row.get("release_year"):
                st.metric("📅 Release Year", int(row["release_year"]))
        with inf2:
            if row.get("country"):
                st.metric("🗺️ Country", row["country"])
            if row.get("language"):
                st.metric("🌍 Language", row["language"])

        if details.get("overview"):
            st.markdown("#### 📖 Overview")
            st.markdown(details["overview"])
        if details.get("homepage"):
            st.markdown(f"🔗 [Official Website]({details['homepage']})")

    if details.get("cast"):
        st.markdown("#### 🎭 Cast")
        cast_cols = st.columns(min(len(details["cast"]), 4))
        for i, actor in enumerate(details["cast"][:4]):
            with cast_cols[i]:
                if actor.get("profile_url"):
                    st.image(actor["profile_url"], use_container_width=True)
                else:
                    render_no_poster(height=120, icon="👤")
                st.markdown(
                    f"<div class='cast-card'>"
                    f"<div class='cast-name'>{actor['name']}</div>"
                    f"<div class='cast-char'>{actor['character']}</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
