import streamlit as st
from ui import styles
import db
import query_builder as qb
import tmdb

def render(database, query_b, tmdb_api):
    movie_id = st.query_params.get("movie_id")
    
    if not movie_id:
        styles.render_navbar("movie")
        st.error("Aucun identifiant de film fourni.")
        st.markdown('<a href="/?page=home" target="_parent" style="color:#01b4e4; font-weight:600; text-decoration:none;">← Retour à l\'accueil</a>', unsafe_allow_html=True)
        return

    with st.spinner("Chargement des détails du film..."):
        details = tmdb_api.fetch_movie_details(movie_id)
        
    # No navigation bar on the movie page as per user request
    
    # Render dynamic back button — uses st.query_params to stay in the same session
    from_page = st.query_params.get("from", "home")
    artist_id_ref = st.query_params.get("artist_id", "")

    if from_page == "search":
        back_label = "← Retour à la recherche"
        back_page  = "search"
        back_extra = {}
    elif from_page == "people" and artist_id_ref:
        back_label = "← Retour à l'artiste"
        back_page  = "people"
        back_extra = {"artist_id": artist_id_ref}
    elif from_page == "recommend":
        back_label = "← Retour aux recommandations"
        back_page  = "recommend"
        back_extra = {}
    else:
        back_label = "← Retour à l'accueil"
        back_page  = "home"
        back_extra = {}

    st.markdown("<div style='padding: 15px 0 5px 0;'>", unsafe_allow_html=True)
    if st.button(back_label, key="back_btn"):
        st.query_params["page"] = back_page
        for k, v in back_extra.items():
            st.query_params[k] = v
        # Clear movie_id and from params
        st.query_params.pop("movie_id", None)
        st.query_params.pop("from", None)
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
        
    if not details:
        st.error("Impossible de récupérer les détails de ce film via TMDB.")
        st.markdown('<a href="/?page=home" target="_parent" style="color:#01b4e4; font-weight:600; text-decoration:none;">← Retour à l\'accueil</a>', unsafe_allow_html=True)
        return

    # Extract info
    title = details.get("title", "Titre Inconnu")
    overview = details.get("overview", "Aucun résumé disponible.")
    poster = details.get("poster_url") or "https://placehold.co/500x750/111111/444444?text=Pas+d'affiche"
    backdrop = details.get("backdrop_url") or poster
    date = details.get("release_date", "Date inconnue")
    genres = ", ".join(details.get("genres", []))
    keywords = ", ".join(details.get("keywords", []))
    directors = ", ".join(details.get("directors", []))
    
    tmdb_rating = details.get("vote_average", 0)
    
    try:
        sql = query_b.build_top_by_tmdb_ids_query([int(movie_id)], limit=1)
        df = database.run_query(sql) if sql else None
    except Exception:
        df = None
    
    bq_rating_html = ""
    if df is not None and not df.empty:
        bq_rating = float(df.iloc[0].get("avg_rating", 0))
        bq_votes = int(df.iloc[0].get("nb_ratings", 0))
        bq_rating_html = f"<div><span style='font-weight:700; color:#38bdf8;'>Note Utilisateurs (DB):</span> {bq_rating:.1f}/5 ({bq_votes} avis)</div>"
    
    hero_html = f"""
    <div style="position:relative; width:100%; height:80vh; min-height:500px; background-image:url('{backdrop}'); background-size:cover; background-position:center; margin-bottom: 2rem; border-radius: 12px; overflow: hidden; box-shadow: 0 10px 30px rgba(0,0,0,0.5);">
        <div style="position:absolute; top:0; left:0; right:0; bottom:0; background:linear-gradient(to right, #0B0B0C 10%, rgba(11,11,12,0.85) 50%, rgba(11,11,12,0.3) 100%), linear-gradient(to top, #0B0B0C 0%, rgba(11,11,12,0) 40%);"></div>
        
        <div style="position:absolute; bottom:0; padding:0 4% 5% 4%; display:flex; gap:40px; align-items:flex-end; width:100%; box-sizing:border-box;">
            <div style="flex-shrink:0;">
                <img src="{poster}" style="width:250px; border-radius:12px; box-shadow:0 15px 40px rgba(0,0,0,0.9); z-index:10;" />
            </div>
            <div style="z-index:10; max-width:800px;">
                <h1 style="font-size:3.5rem; font-weight:900; line-height:1.1; margin-bottom:10px; text-shadow:2px 2px 8px rgba(0,0,0,0.9); text-transform:uppercase;">{title}</h1>
                <div style="font-size:1.1rem; color:#ccc; margin-bottom:20px; text-shadow:1px 1px 4px rgba(0,0,0,0.9);">
                    {date} &nbsp;•&nbsp; {genres} &nbsp;•&nbsp; <span style='color:#21d07a; font-weight:700;'>★ {tmdb_rating:.1f}/10 (TMDB)</span>
                </div>
                <p style="font-size:1.15rem; line-height:1.5; color:#eee; text-shadow:1px 1px 4px rgba(0,0,0,0.9); margin-bottom:20px;">{overview}</p>
                <div style="display:flex; flex-direction:column; gap:8px; font-size:1.05rem;">
                    <div><span style='font-weight:700; color:#aaa;'>Réalisateur(s) :</span> <span style="color:#fff;">{directors if directors else 'Non spécifié'}</span></div>
                    {bq_rating_html}
                </div>
            </div>
        </div>
    </div>
    """
    
    st.components.v1.html(f"""
    <!DOCTYPE html>
    <html>
    <head>
        {styles.get_css()}
        <style>
            body {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; background-color: #0B0B0C; margin:0; padding:0; color: white; }}
        </style>
    </head>
    <body>
        {hero_html}
    </body>
    </html>
    """, height=650, scrolling=False)
    
    st.markdown("<h2 style='margin-bottom: 20px;'>Têtes d'affiche</h2>", unsafe_allow_html=True)
    cast = details.get("cast", [])
    if cast:
        cast_html = ""
        for actor in cast:
            img = actor.get("profile_url") or "https://placehold.co/300x450/111111/444444?text=Photo+non+dispo"
            cast_html += f"""
            <div style="background:#1a1a1c; border-radius:8px; overflow:hidden; border:1px solid rgba(255,255,255,0.05); text-align:center;">
                <img src="{img}" style="width:100%; height:220px; object-fit:cover;" />
                <div style="padding:15px 10px;">
                    <div style="font-weight:700; font-size:1rem; margin-bottom:4px; color:white;">{actor.get('name')}</div>
                    <div style="color:#888; font-size:0.9rem;">{actor.get('character')}</div>
                </div>
            </div>
            """
        
        st.components.v1.html(f"""
        <!DOCTYPE html>
        <html>
        <head>
            {styles.get_css()}
            <style>
                body {{ font-family: 'Helvetica', sans-serif; background: transparent; margin: 0; }}
            </style>
        </head>
        <body>
            <div style="display:grid; grid-template-columns:repeat(auto-fill, minmax(160px, 1fr)); gap:20px; padding:10px 15px; width:100%; box-sizing:border-box;">
                {cast_html}
            </div>
        </body>
        </html>
        """, height=380, scrolling=True)
    else:
        st.info("Aucun acteur répertorié.")
        
    if keywords:
        st.markdown("<hr style='border-color: rgba(255,255,255,0.1); margin: 40px 0;'>", unsafe_allow_html=True)
        st.markdown("<h3 style='margin-bottom: 15px;'>Mots-clés</h3>", unsafe_allow_html=True)
        
        keywords_html = "".join([f"<span style='display:inline-block; background:rgba(255,255,255,0.05); border:1px solid rgba(255,255,255,0.1); padding:5px 15px; border-radius:20px; font-size:0.9rem; margin-right:10px; margin-bottom:10px;'>{kw.strip()}</span>" for kw in keywords.split(',') if kw.strip()])
        st.markdown(f"<div>{keywords_html}</div>", unsafe_allow_html=True)
        
    st.markdown("<div style='height: 100px;'></div>", unsafe_allow_html=True)
