"""
ui/home.py – Renders the complete Netflix-style cinematic home page.
"""

from __future__ import annotations

import streamlit as st
import pandas as pd
from ui import styles, components


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
                        <a href="/?page=movie&movie_id={m['tmdbId']}" target="_self" class="btn btn-primary">Plus d'info</a>
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
        card = components.build_tmdb_card(m['title'], m['year'], m['rating'], m['poster'], m['tmdbId'])
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
            f'<div class="top10-card"><div class="top10-number">{p["rank"]}</div><div style="flex:1; position: relative; z-index: 2;">{components.build_tmdb_card(p["title"], p["year"], p["rating"], p["poster"], p["tmdbId"])}</div></div>'
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
        if label not in decade_data: continue
        data = decade_data[label]
        safe_dec = label.replace("s", "")
        
        active_class = "active" if first_dec else ""
        decade_items_html += f'<div class="category-item {active_class}" onclick="switchDecade(\'{safe_dec}\', \'{label}\', this)">{label}</div>'
        
        display_style = "display: block;" if first_dec else "display: none;"
        
        cards_html = "".join([
            f'<div class="poster-card" style="border-radius:8px; overflow:visible;">{components.build_tmdb_card(p["title"], p["year"], p["rating"], p["poster"], p["tmdbId"])}</div>'
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

    html_content = f"""
    <html>
    <head>
        {styles.get_css()}
    </head>
    <body>
        <div style="height: 0px;"></div>
        {hero_html}
        {top10_row}
        {genre_row}
        {decade_row}
        {modals_html}
        
        <script>
        function slideLeft(btn) {{
            const container = btn.parentElement.querySelector('.posters-container');
            container.scrollBy({{ left: -container.clientWidth * 0.8, behavior: 'smooth' }});
        }}
        function slideRight(btn) {{
            const container = btn.parentElement.querySelector('.posters-container');
            container.scrollBy({{ left: container.clientWidth * 0.8, behavior: 'smooth' }});
        }}
        function showSql(id) {{
            document.getElementById('sql-modal-' + id).style.display = 'flex';
        }}
        function hideSql(id) {{
            document.getElementById('sql-modal-' + id).style.display = 'none';
        }}
        function switchGenre(safeLabel, originalLabel, clickedEl) {{
            // Update carousel visibility
            document.querySelectorAll('.genre-carousel-group').forEach(el => el.style.display = 'none');
            document.getElementById('genre-carousel-' + safeLabel).style.display = 'block';
            
            // Update title text
            document.getElementById('selected-genre-name').innerText = originalLabel;
            
            // Update active state on category navigation
            if (clickedEl) {{
                document.querySelectorAll('.category-item').forEach(el => el.classList.remove('active'));
                clickedEl.classList.add('active');
                
                // Optional: scroll the active item into view within its container
                const navContainer = document.querySelector('.category-nav');
                const scrollLeft = clickedEl.offsetLeft - (navContainer.offsetWidth / 2) + (clickedEl.offsetWidth / 2);
                navContainer.scrollTo({{ left: scrollLeft, behavior: 'smooth' }});
            }}
        }}
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
    
    st.components.v1.html(html_content, height=2500, scrolling=True)
