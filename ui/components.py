"""
ui/components.py – Reusable Streamlit UI primitives.

All functions here are pure renderers: they receive data and call st.*
but never query BigQuery or the TMDB API directly.
"""

from __future__ import annotations

import streamlit as st


# ── Generic helpers ───────────────────────────────────────────────────────────

def render_sql_expander(sql: str, label: str = "🧾 Voir le SQL exécuté") -> None:
    """Show an expander containing a SQL code block."""
    with st.expander(label, expanded=False):
        st.code(sql, language="sql")


def render_no_poster(height: int = 120, icon: str = "🎬") -> None:
    """Render a dark placeholder box when no poster is available."""
    st.markdown(
        f"""<div style="background:#1a1a2e;border-radius:8px;height:{height}px;
        display:flex;align-items:center;justify-content:center;
        color:#475569;font-size:2rem;">{icon}</div>""",
        unsafe_allow_html=True,
    )


def render_metric_card(label: str, value: str) -> None:
    """Render a dark glassmorphism metric card."""
    st.markdown(
        f"""<div class="metric-card">
        <div class="label">{label}</div>
        <div class="value">{value}</div></div>""",
        unsafe_allow_html=True,
    )


def render_divider() -> None:
    st.markdown(
        "<hr style='border-color:rgba(255,255,255,0.05);margin:0.3rem 0'>",
        unsafe_allow_html=True,
    )


def render_section_header(title: str, subtitle: str = "") -> None:
    """Render a styled section header (h2 + optional subtitle)."""
    sub = f'<p style="color:#94a3b8;margin:0.3rem 0 0">{subtitle}</p>' if subtitle else ""
    st.markdown(
        f"""<div style="margin-bottom:1.5rem">
        <h2 style="color:white;margin:0">{title}</h2>
        {sub}</div>""",
        unsafe_allow_html=True,
    )


def render_empty_state(icon: str, title: str, body: str = "") -> None:
    """Render a centered empty-state placeholder."""
    st.markdown(
        f"""<div style="text-align:center;padding:3rem 2rem;color:#64748b;">
        <div style="font-size:4rem">{icon}</div>
        <h4 style="color:#94a3b8">{title}</h4>
        {"<p>" + body + "</p>" if body else ""}
        </div>""",
        unsafe_allow_html=True,
    )


# ── Ranked movie cards (used by all Top Charts sub-tabs) ─────────────────────

def render_top_movie_cards(df_top: "import pandas; pandas.DataFrame", fetch_popularity_fn) -> None:  # type: ignore[valid-type]
    """
    Render a ranked list of movie cards enriched with TMDB poster + stats.

    Parameters
    ----------
    df_top            : DataFrame with columns nb_ratings, avg_rating, tmdbId, title,
                        genres, release_year
    fetch_popularity_fn : callable(tmdb_id) → dict  (tmdb.fetch_movie_popularity)
    """
    import pandas as pd  # local import to keep module lightweight

    max_ratings = int(df_top["nb_ratings"].max())

    for rank, (_, row) in enumerate(df_top.iterrows(), start=1):
        tmdb_id = row.get("tmdbId")
        tmdb_data: dict = {}
        if tmdb_id and str(tmdb_id).strip() not in ("", "nan"):
            try:
                tmdb_data = fetch_popularity_fn(tmdb_id)
            except Exception:
                tmdb_data = {}

        with st.container():
            c0, c1, c2, c3 = st.columns([0.08, 0.12, 0.55, 0.25], gap="small")

            # Rank badge
            with c0:
                medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(rank, f"#{rank}")
                st.markdown(
                    f"""<div style="font-size:2rem;text-align:center;
                    padding-top:1.5rem;color:#a78bfa;font-weight:700">{medal}</div>""",
                    unsafe_allow_html=True,
                )

            # Poster
            with c1:
                if tmdb_data.get("poster_url"):
                    st.image(tmdb_data["poster_url"], use_container_width=True)
                else:
                    render_no_poster()

            # Title + popularity bar
            with c2:
                genre_str = str(row.get("genres", "")).replace("|", " · ")
                year_str = int(row["release_year"]) if row.get("release_year") else "?"
                st.markdown(
                    f"""<div style="padding:0.5rem 0">
                    <div style="font-size:1.15rem;font-weight:700;color:#e2e8f0">{row['title']}</div>
                    <div style="color:#94a3b8;font-size:0.82rem;margin:0.3rem 0">{genre_str} &nbsp;·&nbsp; {year_str}</div>
                    </div>""",
                    unsafe_allow_html=True,
                )
                pct = int(row["nb_ratings"] / max_ratings * 100)
                st.markdown(
                    f"""<div style="background:#1e293b;border-radius:999px;height:8px;overflow:hidden;margin-top:0.3rem">
                      <div style="background:linear-gradient(90deg,#7c3aed,#a78bfa);width:{pct}%;height:100%;border-radius:999px"></div>
                    </div>
                    <div style="font-size:0.75rem;color:#64748b;margin-top:0.2rem">{int(row['nb_ratings']):,} ratings</div>""",
                    unsafe_allow_html=True,
                )

            # Stats card
            with c3:
                ml_rating = row.get("avg_rating", 0)
                tmdb_rating = tmdb_data.get("vote_average", 0)
                tmdb_pop = tmdb_data.get("popularity", 0)
                tmdb_block = (
                    f'<div style="font-size:0.72rem;color:#64748b;margin-top:0.5rem;text-transform:uppercase;letter-spacing:.06em">TMDB</div>'
                    f'<div style="font-size:1.1rem;font-weight:600;color:#38bdf8">🎬 {tmdb_rating:.1f}/10</div>'
                    if tmdb_rating else ""
                )
                pop_block = (
                    f'<div style="font-size:0.72rem;color:#64748b;margin-top:0.3rem">🔥 {tmdb_pop:.0f} pts</div>'
                    if tmdb_pop else ""
                )
                st.markdown(
                    f"""<div style="padding:0.5rem;background:rgba(255,255,255,0.03);border-radius:10px;
                    border:1px solid rgba(255,255,255,0.06);text-align:center;margin-top:0.3rem">
                    <div style="font-size:0.72rem;color:#64748b;text-transform:uppercase;letter-spacing:.06em">ML-20M</div>
                    <div style="font-size:1.4rem;font-weight:700;color:#a78bfa">⭐ {ml_rating:.1f}</div>
                    {tmdb_block}{pop_block}
                    </div>""",
                    unsafe_allow_html=True,
                )

        render_divider()
