"""
ui/recommend.py – Full-featured recommendation system (MovieLens-style)
Sections: Film Grid · Search · Your Profile · Preferences · Generate
"""

import os
import requests
import streamlit as st
import api_client as api
from ui import styles, components
from streamlit_searchbox import st_searchbox
import ui.components as comp

MIN_MOVIES  = 3
TMDB_BASE   = "https://api.themoviedb.org/3"

# Mood presets: maps a mood label to a list of BigQuery genre strings
MOOD_PRESETS = {
    "Detente":    ["Comedy", "Romance", "Animation"],
    "Action":     ["Action", "Adventure", "Sci-Fi"],
    "Emotion":    ["Drama", "Romance"],
    "Suspense":   ["Thriller", "Horror", "Mystery", "Crime"],
    "Comedie":    ["Comedy"],
    "Decouverte": ["Documentary"],
}

ALL_GENRES = [
    "Action", "Adventure", "Animation", "Children", "Comedy", "Crime",
    "Documentary", "Drama", "Fantasy", "Horror", "Musical", "Mystery",
    "Romance", "Sci-Fi", "Thriller", "War", "Western",
]

SECTION_HEADING = """
<p style="
    font-size: 0.78rem;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: #555;
    margin: 0 0 6px 0;
">{label}</p>
"""

SECTION_DESC = """
<p style="font-size: 0.85rem; color: #777; margin: 0 0 18px 0; line-height: 1.55;">{desc}</p>
"""

DIVIDER = "<div style='height:1px; background:rgba(255,255,255,0.06); margin: 40px 0;'></div>"
SPACER  = lambda px: f"<div style='height:{px}px'></div>"


def _tmdb_key() -> str:
    try:
        k = st.secrets.get("TMDB_API_KEY", "")
        if k:
            return str(k)
    except Exception:
        pass
    return os.environ.get("TMDB_API_KEY", "")


@st.cache_data(ttl=3600, show_spinner=False)
def _search_people(query: str) -> list[dict]:
    key = _tmdb_key()
    if not key or not query or len(query) < 2:
        return []
    try:
        r = requests.get(
            f"{TMDB_BASE}/search/person",
            params={"api_key": key, "query": query, "language": "fr-FR"},
            timeout=5,
        )
        results = r.json().get("results", [])
        return [
            {"id": str(p["id"]), "name": p["name"], "role": p.get("known_for_department", "")}
            for p in results[:6]
        ]
    except Exception:
        return []


def _section(label: str, desc: str = "") -> None:
    st.markdown(SECTION_HEADING.format(label=label), unsafe_allow_html=True)
    if desc:
        st.markdown(SECTION_DESC.format(desc=desc), unsafe_allow_html=True)


def _person_search_func(query: str):
    if not query or len(query) < 2:
        return []
    people = _search_people(query)
    return [
        (f"{p['name']} ({p['role']})", f"{p['id']}::::{p['name']}")
        for p in people
    ]

def _exclude_search_func(query: str):
    if not query or len(query) < 2:
        return []
    try:
        suggs = api.autocomplete(query, limit=6)
        return [
            (
                f"{comp.format_title(s['title'])} ({s.get('release_year', '')})",
                f"{s['movieId']}::::{comp.format_title(s['title'])}",
            )
            for s in suggs
        ]
    except Exception:
        return []

def _film_search_func(searchterm: str):
    if not searchterm or len(searchterm) < 2:
        return []
    try:
        suggs = api.autocomplete(searchterm, limit=8)
        return [
            (
                f"{comp.format_title(s['title'])} ({s.get('release_year', '')})",
                f"{s['movieId']}::::{comp.format_title(s['title'])}",
            )
            for s in suggs
        ]
    except Exception:
        return []

def render(db, qb, tmdb):
    styles.render_navbar("recommend")
    st.markdown("<div style='height: 4rem'></div>", unsafe_allow_html=True)

    # ── Global CSS ──────────────────────────────────────────────────────────────
    st.markdown("""
    <style>
    button[kind="primary"] {
        background-color: #01b4e4 !important;
        color: #000 !important;
        font-weight: 700 !important;
        font-size: 1rem !important;
        height: 52px !important;
        border-radius: 6px !important;
        letter-spacing: 0.02em;
    }
    div[data-testid="stSlider"] > div { padding-bottom: 0 !important; }
    div[data-testid="stSlider"] label { display: none !important; }
    </style>
    """, unsafe_allow_html=True)

    # ── Session State Init ──────────────────────────────────────────────────────
    for key, default in [
        ("taste_profile",     []),
        ("pending_movie",     None),
        ("suggestion_movies", None),
        ("excluded_movies",   []),
        ("selected_persons",  []),
        ("selected_mood",     ""),
        ("recs_result",       None),
    ]:
        if key not in st.session_state:
            st.session_state[key] = default

    # ── Layout ──────────────────────────────────────────────────────────────────
    _, center_col, _ = st.columns([1, 5, 1])

    with center_col:

        # ── HERO ────────────────────────────────────────────────────────────────
        st.markdown("""
        <div style="text-align:center; padding: 2rem 0 3rem;">
            <h1 style="margin-bottom: 0.75rem; font-size: 2.4rem;">Recommandations</h1>
            <p style="color: #999; font-size: 1rem; max-width: 620px; margin: 0 auto; line-height: 1.7;">
                Notez les films que vous avez vus. Le moteur BigQuery ML analyse
                vos notes pour identifier des spectateurs au profil identique au vôtre
                et déduire vos prochains coups de coeur.
            </p>
        </div>
        """, unsafe_allow_html=True)

        # ── SECTION 1 : FILM GRID ───────────────────────────────────────────────
        _section(
            "Films populaires",
            "Glissez le curseur sous une affiche pour noter le film de 0 à 5. "
            "Les films notés sont mis en avant par un contour bleu."
        )

        if st.session_state.suggestion_movies is None:
            with st.spinner("Chargement..."):
                st.session_state.suggestion_movies = api.get_top_movies(limit=16)

        suggestion_movies = st.session_state.suggestion_movies or []
        already_rated = {m["id"]: m["rating"] for m in st.session_state.taste_profile}

        def on_rating_change(movie_id, movie_title, key):
            rating = st.session_state.get(key, 0.0)
            st.session_state.taste_profile = [
                m for m in st.session_state.taste_profile if m["id"] != movie_id
            ]
            if rating > 0:
                st.session_state.taste_profile.append(
                    {"id": movie_id, "title": movie_title, "rating": rating}
                )

        if suggestion_movies:
            PAGE_SIZE = 4
            total_pages = (len(suggestion_movies) + PAGE_SIZE - 1) // PAGE_SIZE
            if "popular_page" not in st.session_state:
                st.session_state.popular_page = 0

            page = st.session_state.popular_page
            start = page * PAGE_SIZE
            row   = suggestion_movies[start:start + PAGE_SIZE]

            cols = st.columns(4, gap="medium")
            for i, movie in enumerate(row):
                with cols[i]:
                    m_id    = str(movie.get("movieId", ""))
                    m_title = comp.format_title(movie.get("title", ""))
                    poster  = (
                        movie.get("poster_url")
                        or "https://via.placeholder.com/300x450/111/444?text=N/A"
                    )
                    current_rating = already_rated.get(m_id, 0.0)
                    is_rated = current_rating > 0
                    border   = (
                        "border:2px solid #01b4e4; box-shadow:0 0 12px rgba(1,180,228,0.3);"
                        if is_rated else "border:2px solid transparent;"
                    )

                    st.markdown(
                        f"""<div style="border-radius:8px; overflow:hidden; {border}
                                       margin-bottom:8px; transition:border 0.2s;">
                            <img src="{poster}" style="width:100%; display:block;"
                                 title="{m_title}" />
                        </div>""",
                        unsafe_allow_html=True,
                    )

                    st.slider(
                        " ",
                        min_value=0.0, max_value=5.0,
                        value=float(current_rating), step=0.5,
                        format="%.1f",
                        key=f"rating_{m_id}",
                        on_change=on_rating_change,
                        args=(m_id, m_title, f"rating_{m_id}"),
                        label_visibility="collapsed",
                    )

            # Pagination controls — [1, 2, 1] mirrors the 4 equal film columns
            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
            nav_cols = st.columns([1, 2, 1], gap="medium")
            with nav_cols[0]:
                if st.button("‹", disabled=(page == 0), key="popular_prev"):
                    st.session_state.popular_page -= 1
                    st.rerun()
            with nav_cols[1]:
                st.markdown(
                    f"<p style='text-align:center; color:#555; font-size:0.82rem; margin:6px 0;'>"
                    f"{page + 1} / {total_pages}</p>",
                    unsafe_allow_html=True,
                )
            with nav_cols[2]:
                if st.button("›", disabled=(page >= total_pages - 1), key="popular_next"):
                    st.session_state.popular_page += 1
                    st.rerun()

        st.markdown(DIVIDER, unsafe_allow_html=True)

        # ── SECTION 2 : ADD OTHER FILMS ─────────────────────────────────────────
        _section(
            "Ajouter d'autres films",
            "Vous ne trouvez pas un film dans la grille ? Recherchez-le ici pour le noter."
        )

        selected_raw = st_searchbox(
            _film_search_func,
            key="rec_searchbox",
            placeholder="Titre d'un film...",
            label=None,
            clear_on_submit=True,
            default_use_searchterm=False,
            style_absolute=False,
        )

        if selected_raw:
            m_id, m_title = selected_raw.split("::::")
            if any(m["id"] == m_id for m in st.session_state.taste_profile):
                st.toast("Ce film est déjà dans votre profil.")
            else:
                st.session_state.pending_movie = {"id": m_id, "title": m_title}

        if st.session_state.pending_movie:
            pm = st.session_state.pending_movie
            st.markdown(SPACER(16), unsafe_allow_html=True)
            st.markdown(
                f"<p style='color:#ccc; font-size:0.9rem; margin-bottom:8px;'>"
                f"Note pour <strong>{pm['title']}</strong></p>",
                unsafe_allow_html=True,
            )
            pc1, pc2, pc3 = st.columns([5, 1.4, 1.4], vertical_alignment="bottom")
            with pc1:
                pending_rating = st.slider(
                    "Note", min_value=0.5, max_value=5.0, value=3.0,
                    step=0.5, format="%.1f",
                    label_visibility="collapsed", key="pending_slider",
                )
            with pc2:
                if st.button("Annuler", use_container_width=True, key="cancel_pending"):
                    st.session_state.pending_movie = None
                    st.rerun()
            with pc3:
                if st.button("Valider", type="primary", use_container_width=True, key="validate_pending"):
                    st.session_state.taste_profile.append(
                        {"id": pm["id"], "title": pm["title"], "rating": float(pending_rating)}
                    )
                    st.session_state.pending_movie = None
                    st.rerun()

        st.markdown(DIVIDER, unsafe_allow_html=True)

        # ── SECTION 3 : PROFILE DISPLAY ─────────────────────────────────────────
        movies_count = len(st.session_state.taste_profile)
        _section(
            f"Votre profil  —  {movies_count} film(s) note(s)",
            f"Minimum {MIN_MOVIES} films requis pour lancer l'analyse. "
            "Cliquez sur un film pour modifier sa note ou le retirer."
        )

        if st.session_state.taste_profile:
            def chunks(lst, n):
                for i in range(0, len(lst), n):
                    yield lst[i:i + n]

            for row_movies in chunks(st.session_state.taste_profile, 4):
                cols = st.columns(4)
                for i, p in enumerate(row_movies):
                    with cols[i]:
                        label = f"{p['title']}   {p['rating']:.1f}/5   x"
                        if st.button(label, key=f"del_{p['id']}", use_container_width=True):
                            st.session_state.taste_profile = [
                                m for m in st.session_state.taste_profile if m["id"] != p["id"]
                            ]
                            st.rerun()
        else:
            st.markdown(
                "<p style='color:#555; font-style:italic; font-size:0.88rem;'>"
                "Aucun film note pour l'instant.</p>",
                unsafe_allow_html=True,
            )

        st.markdown(DIVIDER, unsafe_allow_html=True)

        # ── SECTION 4 : PREFERENCES ─────────────────────────────────────────────
        _section(
            "Preferences du moment",
            "Ces criteres sont optionnels. Ils filtrent et orientent les resultats "
            "produits par l'IA selon votre envie du moment."
        )

        # 4-A  Mood ──────────────────────────────────────────────────────────────
        st.markdown(SECTION_HEADING.format(label="Humeur"), unsafe_allow_html=True)
        st.markdown(SPACER(6),  unsafe_allow_html=True)

        mood_options = [""] + list(MOOD_PRESETS.keys())
        mood_labels  = ["Pas de preference"] + list(MOOD_PRESETS.keys())
        mood_cols    = st.columns(len(mood_options))
        for i, mood in enumerate(mood_options):
            with mood_cols[i]:
                active = st.session_state.selected_mood == mood
                if st.button(
                    mood_labels[i],
                    key=f"mood_{i}",
                    use_container_width=True,
                    type="primary" if active else "secondary",
                ):
                    st.session_state.selected_mood = mood
                    st.rerun()

        st.markdown(SPACER(28), unsafe_allow_html=True)

        # 4-B  Genres ────────────────────────────────────────────────────────────
        st.markdown(SECTION_HEADING.format(label="Genres specifiques"), unsafe_allow_html=True)
        st.markdown(
            SECTION_DESC.format(
                desc="Optionnel. Cumulatif avec l'humeur choisie ci-dessus."
            ),
            unsafe_allow_html=True,
        )
        selected_genres = st.multiselect("Genres", ALL_GENRES, label_visibility="collapsed")

        st.markdown(SPACER(24), unsafe_allow_html=True)

        # 4-C  Period ────────────────────────────────────────────────────────────
        st.markdown(SECTION_HEADING.format(label="Periode de sortie"), unsafe_allow_html=True)
        st.markdown(SPACER(6), unsafe_allow_html=True)
        years = st.slider("Periode", min_value=1900, max_value=2024,
                          value=(1980, 2024), label_visibility="collapsed")

        st.markdown(SPACER(28), unsafe_allow_html=True)

        # 4-D  Actor / Director ──────────────────────────────────────────────────
        st.markdown(SECTION_HEADING.format(label="Acteur ou realisateur"), unsafe_allow_html=True)
        st.markdown(
            SECTION_DESC.format(
                desc="Les films impliquant cet artiste seront privileges dans les recommandations."
            ),
            unsafe_allow_html=True,
        )

        selected_person_raw = st_searchbox(
            _person_search_func,
            key="person_searchbox",
            placeholder="Nom d'un acteur ou realisateur...",
            label=None,
            clear_on_submit=True,
            default_use_searchterm=False,
            style_absolute=False,
        )

        if selected_person_raw:
            p_id, p_name = selected_person_raw.split("::::")
            if not any(p["id"] == p_id for p in st.session_state.selected_persons):
                st.session_state.selected_persons.append({"id": p_id, "name": p_name})

        if st.session_state.selected_persons:
            st.markdown(SPACER(10), unsafe_allow_html=True)
            pcols = st.columns(min(len(st.session_state.selected_persons), 4))
            for i, person in enumerate(st.session_state.selected_persons[:4]):
                with pcols[i]:
                    if st.button(
                        f"{person['name']}   x",
                        key=f"del_person_{person['id']}",
                        use_container_width=True,
                    ):
                        st.session_state.selected_persons = [
                            p for p in st.session_state.selected_persons
                            if p["id"] != person["id"]
                        ]
                        st.rerun()

        st.markdown(SPACER(28), unsafe_allow_html=True)

        # 4-E  Films to exclude ──────────────────────────────────────────────────
        st.markdown(SECTION_HEADING.format(label="Films a exclure"), unsafe_allow_html=True)
        st.markdown(
            SECTION_DESC.format(
                desc="Films que vous avez deja vus et ne souhaitez pas voir recommandes."
            ),
            unsafe_allow_html=True,
        )

        excluded_raw = st_searchbox(
            _exclude_search_func,
            key="exclude_searchbox",
            placeholder="Titre d'un film a exclure...",
            label=None,
            clear_on_submit=True,
            default_use_searchterm=False,
            style_absolute=False,
        )

        if excluded_raw:
            ex_id, ex_title = excluded_raw.split("::::")
            if not any(m["id"] == ex_id for m in st.session_state.excluded_movies):
                st.session_state.excluded_movies.append({"id": ex_id, "title": ex_title})

        if st.session_state.excluded_movies:
            st.markdown(SPACER(10), unsafe_allow_html=True)
            exc_cols = st.columns(min(len(st.session_state.excluded_movies), 4))
            for i, exm in enumerate(st.session_state.excluded_movies[:4]):
                with exc_cols[i]:
                    if st.button(
                        f"{exm['title']}   x",
                        key=f"del_ex_{exm['id']}",
                        use_container_width=True,
                    ):
                        st.session_state.excluded_movies = [
                            m for m in st.session_state.excluded_movies if m["id"] != exm["id"]
                        ]
                        st.rerun()

        st.markdown(DIVIDER, unsafe_allow_html=True)

        # ── SECTION 5 : GENERATE ────────────────────────────────────────────────
        movies_count = len(st.session_state.taste_profile)
        can_generate = movies_count >= MIN_MOVIES

        if not can_generate:
            remaining = MIN_MOVIES - movies_count
            st.markdown(
                f"<p style='color:#888; font-size:0.88rem; text-align:center; margin-bottom:16px;'>"
                f"Notez encore <strong style='color:#e8e8e8;'>{remaining} film(s)</strong> "
                f"pour pouvoir lancer l'analyse.</p>",
                unsafe_allow_html=True,
            )

        generate_btn = st.button(
            "Generer mes Recommandations",
            type="primary",
            use_container_width=True,
            disabled=not can_generate,
        )

        st.markdown(SPACER(60), unsafe_allow_html=True)

        # ── RESULTS ─────────────────────────────────────────────────────────────
        if generate_btn and can_generate:
            st.session_state.recs_result = None  # reset previous
            with st.spinner("Analyse en cours — identification des profils similaires..."):
                selected_ratings = {str(m["id"]): float(m["rating"]) for m in st.session_state.taste_profile}

                # Merge mood genres + explicit genre selection
                mood_genres     = MOOD_PRESETS.get(st.session_state.selected_mood, [])
                merged_genres   = list(set(mood_genres + selected_genres)) or None

                y_min, y_max    = years
                person_ids      = [int(p["id"]) for p in st.session_state.selected_persons]
                excluded_ids    = [int(m["id"]) for m in st.session_state.excluded_movies]

                recs = api.get_recommendations(
                    movie_ratings      = selected_ratings,
                    genres             = merged_genres,
                    year_min           = y_min if y_min > 1900 else None,
                    year_max           = y_max if y_max < 2024 else None,
                    person_tmdb_ids    = person_ids or None,
                    excluded_movie_ids = excluded_ids or None,
                    n                  = 12,
                )
                st.session_state.recs_result = recs

        if st.session_state.recs_result:
            recs = st.session_state.recs_result
            st.markdown(
                "<h3 style='margin-bottom:24px; color:#e8e8e8; font-size:1.2rem;'>"
                "Resultats de l'analyse</h3>",
                unsafe_allow_html=True,
            )

            cards_html = ""
            for m in recs:
                title    = m.get("title", "Unknown")
                year     = str(m.get("release_year", ""))
                poster   = m.get("poster_url") or "https://via.placeholder.com/500x750/111/444?text=N/A"
                tmdb_id  = m.get("tmdbId", "")

                # Rating display priority:
                # 1. community_rating = real avg from global ratings table (0-5, always correct)
                # 2. avg_rating       = SQL collaborative avg (0-5, correct)
                # 3. Never use avg_pred — it's a raw inner product from ML.RECOMMEND (can be 40+)
                score_val = m.get("community_rating") or m.get("avg_rating") or 0
                try:
                    sf = float(score_val)
                    rating_fmt = f"{sf:.1f}"
                except (ValueError, TypeError):
                    rating_fmt = "N/A"

                card = components.build_tmdb_card(
                    title, year, rating_fmt, poster, tmdb_id, from_page="recommend"
                )
                cards_html += f'<div style="flex:0 0 auto; width:200px;">{card}</div>'

            carousel_html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  {styles.get_css()}
  <style>
    body {{ background: transparent; margin: 0; padding: 0; overflow-x: hidden; }}
  </style>
</head>
<body>
<div class="carousel-wrapper">
  <button class="scroll-btn left" onclick="slideLeft(this)">&#10094;</button>
  <div class="posters-container">
    {cards_html}
  </div>
  <button class="scroll-btn right" onclick="slideRight(this)">&#10095;</button>
</div>
<script>
function slideLeft(btn) {{
  const c = btn.parentElement.querySelector('.posters-container');
  c.scrollBy({{ left: -c.clientWidth * 0.8, behavior: 'smooth' }});
}}
function slideRight(btn) {{
  const c = btn.parentElement.querySelector('.posters-container');
  c.scrollBy({{ left: c.clientWidth * 0.8, behavior: 'smooth' }});
}}
</script>
</body>
</html>"""
            st.components.v1.html(carousel_html, height=420, scrolling=False)
            st.markdown(SPACER(40), unsafe_allow_html=True)

        elif st.session_state.recs_result is not None and len(st.session_state.recs_result) == 0:
            st.warning(
                "Aucun film trouve avec ces criteres. "
                "Essayez d'elargir la periode, de reduire les filtres de genre "
                "ou d'ajouter d'autres films a votre profil."
            )
