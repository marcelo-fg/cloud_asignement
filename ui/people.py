import streamlit as st
from ui import styles
import pandas as pd

def render(db, qb, tmdb):
    artist_id = st.query_params.get("artist_id")
    
    # Shared Navigation
    styles.render_navbar("people")
    
    if artist_id:
        _render_profile(artist_id, db, qb, tmdb)
        st.stop()
    else:
        _render_directory(db, qb, tmdb)
        st.stop()


def _render_directory(db, qb, tmdb):
    st.markdown("<div style='height: 4rem'></div>", unsafe_allow_html=True)
    
    with st.container():
        st.markdown("<h1>Recherche d'Artistes (Acteurs & Réalisateurs)</h1>", unsafe_allow_html=True)
        st.markdown("<p style='color:#ccc; font-size:1.1rem;'>Trouvez un artiste pour découvrir ses films présents dans notre catalogue.</p>", unsafe_allow_html=True)
    
    query = st.text_input("Rechercher...", placeholder="Ex: Brad Pitt, Christopher Nolan, Steven Spielberg")
    
    if query:
        with st.spinner("Recherche TMDB en cours..."):
            people = tmdb.search_person(query)
            
        if not people:
            st.info("Aucun artiste trouvé sur The Movie Database pour cette recherche.")
            return

        grid_html = ""
        for p in people:
            link = f'/?page=people&artist_id={p["id"]}'
            img = p.get("profile_url") or "https://placehold.co/500x750/111111/444444?text=Photo+non+dispo"
            known_for = ", ".join(p.get("known_for", []))
            grid_html += f"""
<a href="{link}" target="_self" style="text-decoration:none; color:inherit;">
    <div class="person-card" style="background:#1a1a1c; border-radius:8px; overflow:hidden; border:1px solid rgba(255,255,255,0.05); transition:transform 0.3s; cursor:pointer;">
        <img src="{img}" alt="{p['name']}" style="width:100%; height:320px; object-fit:cover;">
        <div style="padding:15px;">
            <div style="font-weight:700; font-size:1.1rem; margin-bottom:5px; color:white;">{p['name']}</div>
            <div style="color:#888; font-size:0.9rem;">{p.get('known_for_department', '')} • {known_for}</div>
        </div>
    </div>
</a>
"""
            
        st.markdown(f"""
<div style="font-family: 'Helvetica', sans-serif; width: 100%;">
<style>
.person-card:hover {{ transform: scale(1.03); border-color: #01b4e4; }}
</style>
<div style="display:grid; grid-template-columns:repeat(5, minmax(0, 1fr)); gap:25px; padding:20px 0; width: 100%;">
{grid_html}
</div>
</div>
""", unsafe_allow_html=True)
    else:
        st.info("Saisissez un nom d'artiste dans la barre de recherche ci-dessus.")


def _render_profile(artist_id_str, db, qb, tmdb):
    artist_id = int(artist_id_str)
    
    st.markdown('<a href="/?page=people" target="_parent" style="color:#01b4e4; font-weight:600; text-decoration:none; margin-top:20px; display:inline-block;">← Retour à la recherche</a>', unsafe_allow_html=True)
    st.markdown("<hr style='border: 1px solid rgba(255,255,255,0.1); margin: 20px 0;'>", unsafe_allow_html=True)

    with st.spinner("Identification des films via TMDB et BigQuery..."):
        # 1. Fetch TMDB ids for this person
        movie_ids = tmdb.fetch_person_movie_tmdb_ids(artist_id, role="both")
        
        if not movie_ids:
            st.warning("Cet artiste n'a aucun film répertorié sur TMDB.")
            return
            
        # 2. SQL query to get only movies present in BigQuery
        limit = 60
        sql = qb.build_top_by_tmdb_ids_query(movie_ids, limit=limit)
        
        df = pd.DataFrame()
        if sql:
            df = db.run_query(sql)
            
    if df.empty:
        st.warning("Aucun des films de cet artiste n'est disponible dans notre base de données BigQuery.")
        return
        
    st.markdown(f"<h2 style='margin-bottom: 5px;'>Filmographie Disponible <span style='color:#01b4e4;'>({len(df)} films)</span></h2>", unsafe_allow_html=True)
    st.markdown("<p style='color:#ccc;'>Seuls les films existants dans notre base de données BigQuery sont affichés ici.</p>", unsafe_allow_html=True)
    
    show_sql = st.toggle("Voir la requête BigQuery SQL")
    if show_sql:
        st.info("Requête de jointure IN exécutée :")
        st.code(sql, language="sql")
        
    # Render the movie grid
    enriched_movies = []
    for _, row in df.iterrows():
        avg_r = float(row.get("avg_rating", 0)) if "avg_rating" in row else 0.0
        r_percent = int((avg_r / 5.0) * 100)
        
        tmdb_data = tmdb.fetch_movie_popularity_v2(row.get("tmdbId"))
        poster = tmdb_data.get("poster_url") if tmdb_data else None
        if not poster:
            safe_title = str(row["title"]).replace(" ", "+")
            poster = f"https://placehold.co/500x750/e3e3e3/9e9e9e?text={safe_title}"
            
        raw_date = str(row.get("release_year", ""))
        
        enriched_movies.append({
            "title": row["title"],
            "date": raw_date,
            "display_rating": f"{avg_r:.1f}",
            "rating_percent": r_percent,
            "img": poster,
            "tmdb_id": row.get("tmdbId")
        })
        
    # Build grid HTML (reusing the same card styling from search)
    grid_html = ""
    for m in enriched_movies:
        r_percent = m["rating_percent"]
        rating_color = "#21d07a" if r_percent >= 70 else "#d2d531" if r_percent >= 40 else "#db2360"
        conic = f"conic-gradient({rating_color} {r_percent}%, transparent 0)"
        
        grid_html += f"""
<a href="/?page=movie&movie_id={m.get('tmdb_id', '')}" target="_self" style="text-decoration:none; color:inherit; display:block;">
    <div class="tmdb-card">
        <div class="tmdb-card-img-wrap">
            <img src="{m['img']}" alt="Poster" />
        </div>
        <div class="tmdb-rating-circle">
            <div class="tmdb-rating-progress" style="background:conic-gradient({rating_color} {r_percent}%, transparent 0);">
                <div class="tmdb-rating-inner">
                    {m['display_rating']}
                </div>
            </div>
        </div>
        <div class="tmdb-card-info">
            <div class="tmdb-card-title">{m['title']}</div>
            <div class="tmdb-card-date">{m['date']}</div>
        </div>
    </div>
</a>
"""
        
    if grid_html:
        st.markdown(f"""
<div style="font-family: 'Source Sans Pro', Arial, sans-serif; padding:10px 0;">
<style>
.movie-grid-custom {{ display:grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap:20px; width: 100%; }}
</style>
<div class="movie-grid-custom">
{grid_html}
</div>
</div>
""", unsafe_allow_html=True)

