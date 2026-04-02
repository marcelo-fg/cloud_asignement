import streamlit as st
from ui import styles, components
import db
import query_builder
import tmdb
import pandas as pd
import random
import requests
import os

def _get_backend_url() -> str:
    try:
        return st.secrets.get("BACKEND_URL", os.environ.get("BACKEND_URL", "http://localhost:5001"))
    except Exception:
        return os.environ.get("BACKEND_URL", "http://localhost:5001")

@st.cache_data(ttl=10, show_spinner=False)
def _fetch_autocomplete(query: str) -> list:
    """Call ES backend /autocomplete endpoint. Returns list of suggestion dicts."""
    try:
        url = _get_backend_url()
        r = requests.get(f"{url}/autocomplete", params={"q": query}, timeout=2)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return []

def render(database, qb, tmdb_api):
    # ── Nav Bar (Injected globally) ──────────────────────────────────────────
    styles.render_navbar("search")
    
    st.markdown("<div style='height: 4rem'></div>", unsafe_allow_html=True)
    
    with st.container():
        st.markdown("<h1>Recherche de Films</h1>", unsafe_allow_html=True)
        # SQL Toggle
        show_sql = st.toggle("View BigQuery SQL")
        st.markdown("<br>", unsafe_allow_html=True)

    # ── Horizontal Filters ───────────────────────────────────────────────────

        # Row 1: Single search bar (ES used internally on search)
        col_search_text, col_search_btn = st.columns([5, 1], gap="medium")
        with col_search_text:
            title_input = st.text_input("Rechercher un film", placeholder="Ex: Inception, The Matrix, Star Wars…", label_visibility="collapsed")
        with col_search_btn:
            search_btn = st.button("Rechercher")

        # ES autocomplete hint shown below input (no interaction required)
        if len(title_input) >= 2:
            suggestions = _fetch_autocomplete(title_input)
            if suggestions:
                hint = " · ".join(f"{s['title']}" for s in suggestions[:5])
                st.caption(f"💡 Suggestions : {hint}")

        # Row 2: Secondary Dropdowns and Sliders
        col_sort, col_genre, col_lang, col_year, col_rate_min, col_rate_max = st.columns([2, 2, 2, 2, 3, 3], gap="large")
        
        with col_sort:
            sort_by = st.selectbox("Trier par", ["Année de Sortie Décroissante", "Année de Sortie Croissante", "Note Décroissante", "Note Croissante"])

        @st.cache_data(ttl=3600, show_spinner="Chargement des filtres...")
        def get_filters(_db, _qb) -> tuple[list[str], list[str]]:
            try:
                genres_df = _db.run_query(_qb.build_distinct_genres_query())
                all_genres = sorted([str(g) for g in genres_df['genre'].dropna().tolist() if str(g).strip()])
            except Exception:
                all_genres = ["Action", "Adventure", "Animation", "Comedy", "Crime", "Documentary", "Drama", "Family", "Fantasy", "History", "Horror", "Music", "Mystery", "Romance", "Science Fiction", "TV Movie", "Thriller", "War", "Western"]
            
            try:
                langs_df = _db.run_query(_qb.build_distinct_languages_query())
                all_langs = sorted([str(l) for l in langs_df['language'].dropna().tolist() if str(l).strip()])
            except Exception:
                all_langs = ["en", "fr", "es", "ja", "ko", "it", "de"]
            
            return all_genres, all_langs

        all_genres, all_langs = get_filters(database, qb)

        with col_genre:
            genres_sel = st.multiselect("Genres", options=all_genres, default=[])

        with col_lang:
            # Full ISO 639-1 Dictionary for TMDB/BigQuery language codes
            friendly_lang = {
                "en": "Anglais (English)", "fr": "Français (French)", "es": "Espagnol (Spanish)",
                "ja": "Japonais (Japanese)", "ko": "Coréen (Korean)", "it": "Italien (Italian)",
                "de": "Allemand (German)", "ru": "Russe (Russian)", "zh": "Chinois (Chinese)", 
                "hi": "Hindi", "pt": "Portugais (Portuguese)", "ar": "Arabe (Arabic)",
                "cs": "Tchèque (Czech)", "da": "Danois (Danish)", "nl": "Néerlandais (Dutch)",
                "fi": "Finnois (Finnish)", "el": "Grec (Greek)", "he": "Hébreu (Hebrew)",
                "id": "Indonésien (Indonesian)", "no": "Norvégien (Norwegian)", "pl": "Polonais (Polish)",
                "ro": "Roumain (Romanian)", "sv": "Suédois (Swedish)", "th": "Thaï (Thai)",
                "tr": "Turc (Turkish)", "vi": "Vietnamien (Vietnamese)", "tl": "Tagalog",
                "cn": "Cantonais (Cantonese)", "fa": "Persan (Persian)", "hu": "Hongrois (Hungarian)",
                "xx": "Muet (No Language)"
            }
            valid_langs: list[str] = [l for l in all_langs if l in friendly_lang]
            lang_options: list[str] = ["Toutes les langues"] + [friendly_lang[l] for l in valid_langs]
            lang_map_reverse: dict[str, str] = {friendly_lang[l]: l for l in valid_langs}
            lang_map_reverse["Toutes les langues"] = "None Selected"
            
            language_sel_name = st.selectbox("Langue", options=lang_options)
            language_sel = lang_map_reverse.get(language_sel_name, "None Selected")
        
        with col_year:
            year_sel = st.slider("Année de sortie", 1900, 2026, (1900, 2026))
            
        with col_rate_min:
            rating_min = st.slider("Note MIN", min_value=0.0, max_value=5.0, value=0.0, step=0.5)
            
        with col_rate_max:
            rating_max = st.slider("Note MAX", min_value=0.0, max_value=5.0, value=5.0, step=0.5)

        # ES used internally to resolve tmdbIds from the title query
        autocomplete_tmdb_id = None

        # Handle "random selection if no filters"
        if not search_btn and not title_input and not genres_sel and language_sel == "None Selected" and rating_min == 0.0 and rating_max == 5.0 and year_sel[0] == 1900 and year_sel[1] == 2026:
            genres_sel = [random.choice(all_genres)]

        st.markdown("<hr style='border: 1px solid rgba(255,255,255,0.1); margin: 30px 0;'>", unsafe_allow_html=True)


        # ── Main Content: BigQuery Execution ──────────────────────────────────────
        
        tab_general, tab_person, tab_saga = st.tabs(["Recherche Générale", "Par Artiste", "Par Saga / Collection"])
        
        with tab_general:
            # Add a slider to control the max number of results
            limit = st.slider("Nombre maximum de résultats", min_value=10, max_value=500, value=100, step=10, key="limit_general", help="Un nombre maximum de 100 résultats est recommandé pour préserver la fluidité de la page.")
            
            if search_btn or title_input or genres_sel or language_sel != "None Selected" or rating_min > 0.0 or rating_max < 5.0 or year_sel[0] > 1900 or year_sel[1] < 2026:
                tmdb_ids_list = None

                if title_input:
                    # Try ES first for fast, typo-tolerant title matching
                    es_suggestions = _fetch_autocomplete(title_input)
                    if es_suggestions:
                        tmdb_ids_list = [s["tmdbId"] for s in es_suggestions if s.get("tmdbId")]
                    else:
                        # Fallback to TMDB semantic search
                        with st.spinner("Analyse sémantique TMDB en cours..."):
                            tmdb_ids_list = tmdb_api.search_advanced_concepts(title_input, limit_pages=2)
                            if not tmdb_ids_list:
                                tmdb_ids_list = []
                            
                sql = qb.build_movie_search_query(
                    title="" if tmdb_ids_list is not None else title_input, # Don't use text LIKE if we have TMDB IDs
                    language=language_sel if language_sel != "None Selected" else "All",
                    genres=list(genres_sel),
                    rating_min=rating_min,
                    rating_max=rating_max,
                    year_min=year_sel[0],
                    year_max=year_sel[1],
                    limit=limit,
                    has_ratings_table=True,
                    tmdb_ids=tmdb_ids_list
                )
            
                if show_sql:
                    st.info("Requête SQL générée envoyée à Google BigQuery :")
                    st.code(sql, language="sql")
                
                with st.spinner("Recherche dans BigQuery via l'API..."):
                    df = db.run_query(sql)
                
                # Fetch routine continues below inside the tab...
                _render_results(df, sort_by, tmdb_api)
                
        with tab_person:
            person_query = st.text_input("Nom de l'acteur ou réalisateur", placeholder="Ex: Leonardo DiCaprio, Christopher Nolan...")
            limit_person = st.slider("Nombre maximum de résultats", min_value=10, max_value=500, value=100, step=10, key="limit_person", help="Un nombre maximum de 100 résultats est recommandé pour préserver la fluidité de la page.")
            
            if person_query:
                with st.spinner("Recherche TMDB en cours..."):
                    people = tmdb_api.search_person(person_query)
                if not people:
                    st.info("Aucun artiste trouvé.")
                else:
                    selected_person_id = st.selectbox(
                        "Sélectionnez l'artiste",
                        options=[p["id"] for p in people],
                        format_func=lambda x: next((f"{p['name']} ({p.get('known_for_department', '')})" for p in people if p["id"] == x), str(x))
                    )
                    
                    if selected_person_id:
                        with st.spinner("Récupération de la filmographie..."):
                            person_movie_ids = tmdb_api.fetch_person_movie_tmdb_ids(selected_person_id, role="both")
                            
                        if person_movie_ids:
                            sql = qb.build_movie_search_query(
                                title="", language=language_sel if language_sel != "None Selected" else "All",
                                genres=list(genres_sel), rating_min=rating_min, rating_max=rating_max,
                                year_min=year_sel[0], year_max=year_sel[1], limit=limit_person, has_ratings_table=True,
                                tmdb_ids=person_movie_ids
                            )
                            df = db.run_query(sql)
                            _render_results(df, sort_by, tmdb_api)
                        else:
                            st.info("Cet artiste n'a aucun film répertorié sur TMDB.")
                            
        with tab_saga:
            saga_query = st.text_input("Nom de la saga ou collection", placeholder="Ex: Harry Potter, Star Wars...")
            limit_saga = st.slider("Nombre maximum de résultats", min_value=10, max_value=500, value=100, step=10, key="limit_saga", help="Un nombre maximum de 100 résultats est recommandé pour préserver la fluidité de la page.")
            
            if saga_query:
                with st.spinner("Recherche TMDB en cours..."):
                    collections = tmdb_api.search_collection(saga_query)
                if not collections:
                    st.info("Aucune saga trouvée.")
                else:
                    selected_collection_id = st.selectbox(
                        "Sélectionnez la saga",
                        options=[c["id"] for c in collections],
                        format_func=lambda x: next((c["name"] for c in collections if c["id"] == x), str(x))
                    )
                    
                    if selected_collection_id:
                        with st.spinner("Récupération des films de la saga..."):
                            collection_movie_ids, c_name, c_poster = tmdb_api.fetch_collection_tmdb_ids(selected_collection_id)
                            
                        if collection_movie_ids:
                            sql = qb.build_movie_search_query(
                                title="", language=language_sel if language_sel != "None Selected" else "All",
                                genres=list(genres_sel), rating_min=rating_min, rating_max=rating_max,
                                year_min=year_sel[0], year_max=year_sel[1], limit=limit_saga, has_ratings_table=True,
                                tmdb_ids=collection_movie_ids
                            )
                            df = db.run_query(sql)
                            _render_results(df, sort_by, tmdb_api)
                        else:
                            st.info("Cette saga ne contient pas de films.")
                            

def _render_results(df, sort_by, tmdb_api):
            
            # Post-fetch sorting using the new French labels
            if not df.empty:
                if sort_by == "Note Décroissante":
                    df = df.sort_values(by="avg_rating", ascending=False)
                elif sort_by == "Note Croissante":
                    df = df.sort_values(by="avg_rating", ascending=True)
                elif sort_by == "Année de Sortie Décroissante":
                    df = df.sort_values(by="release_year", ascending=False)
                elif sort_by == "Année de Sortie Croissante":
                    df = df.sort_values(by="release_year", ascending=True)
            
            st.markdown(f"<div style='color:#ccc; font-size:1.1rem; margin-bottom:20px;'><span style='color:#01b4e4; font-weight:bold;'>{len(df)}</span> résultat(s) trouvé(s)</div>", unsafe_allow_html=True)
            
            # ── Enrichment & TMDB White Card Grid Render ──────────────────────────
            enriched_movies = []
            for _, row in df.iterrows():
            
                # STRICTLY use BigQuery ratings out of 5!
                # Do NOT show TMDB scale (no 83%). Show 4.1.
                avg_r = float(row.get("avg_rating", 0)) if "avg_rating" in row else 0.0
                rating_percent = int((avg_r / 5.0) * 100)
                display_rating = f"{avg_r:.1f}"
            
                # Fetch TMDB data solely for the poster image
                pop = tmdb_api.fetch_movie_popularity(row.get("tmdbId")) if pd.notna(row.get("tmdbId")) else {}
                poster = pop.get("poster_url") if pop else None
                
                # Light placeholder for TMDB theme
                if not poster:
                    safe_title = str(row["title"]).replace(" ", "+")
                    poster = f"https://placehold.co/500x750/e3e3e3/9e9e9e?text={safe_title}"
                
                # Simulate date format "Feb 05, 2026"
                raw_date = str(row.get("release_year", ""))
                formatted_date = f"Jan 01, {raw_date}" if raw_date else "N/A"
            
                enriched_movies.append({
                    "title": row["title"],
                    "date": formatted_date,
                    "rating_percent": rating_percent,
                    "display_rating": display_rating,
                    "img": poster,
                    "tmdb_id": row.get("tmdbId")
                })

            grid_html = "".join([
                components.build_tmdb_card(m['title'], m['date'].split(', ')[-1], f"{float(m['display_rating']):.1f}", m['img'], m.get('tmdb_id', ''), from_page="search")
                for m in enriched_movies
            ])
            
            if grid_html:
                st.markdown(f"""
<div style="font-family: 'Source Sans Pro', Arial, sans-serif; padding:10px 0;">
<style>.movie-grid-custom {{ display:grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap:20px; width: 100%; }}</style>
<div class="movie-grid-custom">{grid_html}</div>
</div>
""", unsafe_allow_html=True)
            else:
                st.info("Aucun film de cette sélection n'est présent dans notre base BigQuery.")
