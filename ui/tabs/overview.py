"""
ui/tabs/overview.py – Tab 3: Dataset Overview (genre + year charts).
"""

from __future__ import annotations

import streamlit as st


def render(db, qb) -> None:
    """Render the Dataset Overview tab with bar and line charts."""
    st.markdown("### 📊 Dataset Overview")
    col1, col2 = st.columns(2, gap="large")

    with col1:
        st.markdown("#### Top Genres by Movie Count")
        try:
            with st.spinner("Loading genre distribution…"):
                sql = qb.build_genre_distribution_query()
                df = db.run_query(sql)
            if not df.empty:
                with st.expander("SQL", expanded=False):
                    st.code(sql, language="sql")
                st.bar_chart(df.set_index("genre")["movie_count"])
        except Exception as e:
            st.warning(f"Could not load genre chart: {e}")

    with col2:
        st.markdown("#### Movies Released Per Year (since 1980)")
        try:
            with st.spinner("Loading year distribution…"):
                sql = qb.build_year_distribution_query(min_year=1980)
                df = db.run_query(sql)
            if not df.empty:
                with st.expander("SQL", expanded=False):
                    st.code(sql, language="sql")
                st.line_chart(df.set_index("release_year")["movie_count"])
        except Exception as e:
            st.warning(f"Could not load year chart: {e}")
