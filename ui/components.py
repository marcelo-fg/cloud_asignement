"""
ui/components.py – Shared UI components and HTML builders
"""

from __future__ import annotations
import re

def format_title(title: str) -> str:
    """Reformat titles stored as 'Matrix, The (1999)' to 'The Matrix (1999)'."""
    if not isinstance(title, str) or not title:
        return str(title)
    match = re.search(r', (The|A|An|La|Le|Les|L\')(\s*\(.*\))?$', title, re.IGNORECASE)
    if match:
        article = match.group(1)
        year_part = match.group(2) or ''
        base = title[:match.start()]
        if article.lower() == "l'":
            return f"{article}{base}{year_part}"
        return f"{article} {base}{year_part}"
    return title

def build_tmdb_card(title: str, release_year: str | int, avg_rating_str: str | float, poster_url: str, tmdb_id: str | int, from_page: str = "", artist_id: str | int = "") -> str:
    """Build a Netflix/TMDB-style movie card (HTML)."""
    title = format_title(title)
    try:
        avg_r = float(avg_rating_str)
    except (ValueError, TypeError):
        avg_r = 0.0
    
    rating_percent = int((avg_r / 5.0) * 100)
    display_rating = f"{avg_r:.1f}"
    
    # Rating colors: Green > 70%, Yellow > 40%, Red otherwise
    rating_color = "#21d07a" if rating_percent >= 70 else "#d2d531" if rating_percent >= 40 else "#db2360"
    formatted_date = str(release_year) if release_year else "N/A"
    
    url = f"/?page=movie&movie_id={tmdb_id}"
    if from_page:
        url += f"&from={from_page}"
    if artist_id:
        url += f"&artist_id={artist_id}"
    
    return f"""
<a href="{url}" target="_self" style="text-decoration:none; color:inherit; display:block;">
    <div class="tmdb-card">
        <div class="tmdb-card-img-wrap">
            <img src="{poster_url}" alt="Poster" />
        </div>
        <div class="tmdb-rating-circle">
            <div class="tmdb-rating-progress" style="background:conic-gradient({rating_color} {rating_percent}%, transparent 0);">
                <div class="tmdb-rating-inner">
                    {display_rating}
                </div>
            </div>
        </div>
        <div class="tmdb-card-info">
            <div class="tmdb-card-title">{title}</div>
            <div class="tmdb-card-date">{formatted_date}</div>
        </div>
    </div>
</a>
"""

def render_sql_modal(modal_id: str, title: str, sql: str) -> str:
    """Render a hidden SQL modal (HTML)."""
    return f"""
<div id="sql-modal-{modal_id}" class="sql-modal">
    <div class="sql-modal-content">
        <span class="sql-close-btn" onclick="hideSql('{modal_id}')">&times;</span>
        <h3 style="margin-top:0;">{title}</h3>
        <pre>{sql}</pre>
    </div>
</div>
"""

def render_info_icon(modal_id: str, tooltip_text: str) -> str:
    """Render an info icon that triggers an SQL modal (HTML)."""
    return f"""
<div class="info-icon" onclick="showSql('{modal_id}')">
    ?
    <div class="tooltip">
        {tooltip_text}
        <span class="tooltip-cta">Cliquez pour voir la requête SQL</span>
    </div>
</div>
"""
