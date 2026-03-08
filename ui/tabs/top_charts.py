"""
ui/tabs/top_charts.py – Tab 2: Top Charts with 5 sub-tabs (Genre, Person, Saga, Theme, Similar).
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from ui.components import (
    render_divider,
    render_empty_state,
    render_sql_expander,
    render_top_movie_cards,
)


def _render_sub_genre(db, qb, tmdb) -> None:
    fc1, fc2, fc3 = st.columns([1, 1, 1], gap="medium")

    with fc1:
        try:
            sql_g = qb.build_distinct_genres_query()
            genre_opts = db.run_query(sql_g)["genre"].dropna().tolist()
        except Exception:
            genre_opts = []
        top_genre = st.selectbox("🎭 Genre", ["— Tous les genres —"] + genre_opts, key="top_genre")
        selected_genre = None if top_genre == "— Tous les genres —" else top_genre

    with fc2:
        decade_opts = ["— Toutes les époques —"] + list(qb.DECADES.keys())
        top_decade = st.selectbox("🗓️ Époque", decade_opts, key="top_decade")
        selected_decade = None if top_decade == "— Toutes les époques —" else top_decade

    with fc3:
        top_n = st.selectbox("🔢 Nombre de films", [5, 10, 15, 20], index=1, key="top_n")

    st.markdown("<br>", unsafe_allow_html=True)
    title_parts = [selected_decade or "All Time"]
    if selected_genre:
        title_parts.append(f"· {selected_genre}")
    st.markdown(f"### 🎬 Top {top_n} — {' '.join(title_parts)}")
    render_divider()

    try:
        with st.spinner("Requête BigQuery en cours…"):
            sql = qb.build_top_charts_query(genre=selected_genre, decade_label=selected_decade, limit=top_n)
            df = db.run_query(sql)

        render_sql_expander(sql)

        if df.empty:
            st.info("Aucun film trouvé pour cette combinaison de filtres.")
        else:
            render_top_movie_cards(df, tmdb.fetch_movie_popularity)
    except Exception as e:
        st.error(f"❌ Erreur BigQuery : {e}")


def _render_sub_person(db, qb, tmdb) -> None:
    st.markdown("#### 🔎 Rechercher un réalisateur ou un acteur")
    st.markdown(
        "<p style='color:#94a3b8;font-size:0.9rem'>Tapez un nom, sélectionnez la personne, "
        "choisissez son rôle puis lancez la recherche.</p>",
        unsafe_allow_html=True,
    )

    p1, p2, p3 = st.columns([2, 1, 1], gap="medium")
    with p1:
        person_query = st.text_input("👤 Nom", placeholder="Ex: Robert De Niro…", key="person_query")
    with p2:
        person_role = st.radio("🎭 Rôle", ["Acteur", "Réalisateur", "Les deux"], horizontal=True, key="person_role")
        role_map = {"Acteur": "actor", "Réalisateur": "director", "Les deux": "both"}
    with p3:
        person_top_n = st.selectbox("🔢 Nombre de films", [5, 10, 15, 20], index=1, key="person_top_n")

    if not person_query.strip():
        render_empty_state("🎬", "Recherchez un réalisateur ou un acteur", "Exemples : Quentin Tarantino, Robert De Niro…")
        return

    with st.spinner(f"Recherche de '{person_query}' sur TMDB…"):
        candidates = tmdb.search_person(person_query)

    if not candidates:
        st.warning("Aucune personne trouvée sur TMDB pour ce nom.")
        return

    labels = [f"{c['name']} ({c['known_for_department']}) — {', '.join(c['known_for']) or '?'}" for c in candidates]
    chosen_label = st.selectbox("✅ Sélectionner la bonne personne", labels, key="person_choice")
    chosen = candidates[labels.index(chosen_label)]

    pc, ic = st.columns([0.15, 0.85], gap="medium")
    with pc:
        if chosen.get("profile_url"):
            st.image(chosen["profile_url"], use_container_width=True)
        else:
            render_empty_state("👤", "", height=100)
    with ic:
        st.markdown(
            f"""<div style="padding:0.5rem 0">
            <div style="font-size:1.2rem;font-weight:700;color:#e2e8f0">{chosen['name']}</div>
            <div style="font-size:0.82rem;color:#94a3b8">{chosen['known_for_department']} &nbsp;·&nbsp;
            Connu pour : <em>{', '.join(chosen['known_for']) or '?'}</em></div></div>""",
            unsafe_allow_html=True,
        )

    render_divider()
    role_key = role_map[person_role]
    with st.spinner(f"Récupération des films de {chosen['name']}…"):
        tmdb_ids = tmdb.fetch_person_movie_tmdb_ids(chosen["id"], role=role_key)

    if not tmdb_ids:
        st.info(f"Aucun film trouvé pour {chosen['name']}.")
        return

    sql = qb.build_top_by_tmdb_ids_query(tmdb_ids, limit=person_top_n)
    rf = {"actor": "joue dans", "director": "a réalisé", "both": "est dans / a réalisé"}.get(role_key, "")
    st.markdown(f"### 🎬 Top {person_top_n} films où **{chosen['name']}** {rf}")

    try:
        with st.spinner("Requête BigQuery en cours…"):
            df = db.run_query(sql)
        render_sql_expander(sql)
        if df.empty:
            st.info(f"Aucun film matché dans le dataset (sur {len(tmdb_ids)} TMDB).")
        else:
            st.caption(f"✅ {len(df)} film(s) matchés sur {len(tmdb_ids)} crédits TMDB")
            render_top_movie_cards(df, tmdb.fetch_movie_popularity)
    except Exception as e:
        st.error(f"❌ {e}")


def _render_sub_saga(db, qb, tmdb) -> None:
    st.markdown("#### 🎪 Rechercher une Franchise ou une Saga")
    st.markdown(
        "<p style='color:#94a3b8;font-size:0.9rem'>Ex: <em>Star Wars</em>, <em>James Bond</em>…</p>",
        unsafe_allow_html=True,
    )

    s1, s2 = st.columns([3, 1], gap="medium")
    with s1:
        query = st.text_input("🎪 Nom de la Franchise", placeholder="Star Wars…", key="saga_query")
    with s2:
        top_n = st.selectbox("🔢 Films", [5, 10, 15, 20], index=1, key="saga_n")

    if not query.strip():
        render_empty_state("🎪", "Recherchez une franchise", "Ex: Star Wars Collection, The Dark Knight…")
        return

    with st.spinner(f"Recherche de '{query}' sur TMDB…"):
        collections = tmdb.search_collection(query)

    if not collections:
        st.warning("Aucune saga trouvée.")
        return

    labels = [c["name"] for c in collections]
    chosen_label = st.selectbox("✅ Sélectionner la saga", labels, key="saga_choice")
    chosen = collections[labels.index(chosen_label)]

    if chosen.get("poster_url"):
        bc1, bc2 = st.columns([0.12, 0.88])
        with bc1:
            st.image(chosen["poster_url"], use_container_width=True)
        with bc2:
            st.markdown(f'<div style="padding:0.8rem 0;font-size:1.3rem;font-weight:700">{chosen["name"]}</div>', unsafe_allow_html=True)

    render_divider()
    with st.spinner("Récupération des films de la saga…"):
        coll_ids, _, _ = tmdb.fetch_collection_tmdb_ids(chosen["id"])

    if not coll_ids:
        st.info("Aucun film trouvé dans cette collection TMDB.")
        return

    sql = qb.build_top_by_tmdb_ids_query(coll_ids, limit=top_n)
    st.markdown(f"### 🎪 Top {top_n} — {chosen['name']}")

    try:
        with st.spinner("Requête BigQuery…"):
            df = db.run_query(sql)
        render_sql_expander(sql)
        if df.empty:
            st.info(f"Aucun film dans notre dataset sur les {len(coll_ids)} connus.")
        else:
            st.caption(f"✅ {len(df)} film(s) matchés sur {len(coll_ids)} dans la saga")
            render_top_movie_cards(df, tmdb.fetch_movie_popularity)
    except Exception as e:
        st.error(f"❌ {e}")


def _render_sub_theme(db, qb, tmdb) -> None:
    st.markdown("#### 🏷️ Filtrer par Thème")
    st.markdown("<p style='color:#94a3b8;font-size:0.9rem'>Ex: <em>heist</em>, <em>zombie</em>…</p>", unsafe_allow_html=True)

    t1, t2 = st.columns([3, 1], gap="medium")
    with t1:
        query = st.text_input("🏷️ Thème", placeholder="time travel, zombie…", key="theme_query")
    with t2:
        top_n = st.selectbox("🔢 Films", [5, 10, 15, 20], index=1, key="theme_n")

    if not query.strip():
        render_empty_state("🏷️", "Cherchez un thème cinématographique")
        st.markdown("**Populaires** (en anglais): time travel, heist, zombie, dystopia, serial killer, road trip")
        return

    with st.spinner(f"Recherche du keyword '{query}'…"):
        keywords = tmdb.search_keyword(query)

    if not keywords:
        st.warning("Aucun keyword trouvé.")
        return

    labels = [f"{k['name']} (id:{k['id']})" for k in keywords]
    chosen_label = st.selectbox("✅ Sélectionner le keyword", labels, key="kw_choice")
    chosen = keywords[labels.index(chosen_label)]

    render_divider()
    with st.spinner(f"Récupération des films taggués '{chosen['name']}'…"):
        kw_ids = tmdb.fetch_movies_by_keyword(chosen["id"])

    if not kw_ids:
        st.info("Aucun film trouvé pour ce keyword.")
        return

    sql = qb.build_top_by_tmdb_ids_query(kw_ids, limit=top_n)
    st.markdown(f"### 🏷️ Top {top_n} — '{chosen['name']}'")

    try:
        with st.spinner("Requête BigQuery…"):
            df = db.run_query(sql)
        render_sql_expander(sql)
        if df.empty:
            st.info(f"0 succès dataset / {len(kw_ids)} TMDB")
        else:
            st.caption(f"✅ {len(df)} match(s) sur {len(kw_ids)}")
            render_top_movie_cards(df, tmdb.fetch_movie_popularity)
    except Exception as e:
        st.error(f"❌ {e}")


def _render_sub_similar(db, qb, tmdb) -> None:
    st.markdown("#### 🔗 Films similaires")
    st.markdown("<p style='color:#94a3b8;font-size:0.9rem'>Entrez un film de référence :</p>", unsafe_allow_html=True)

    s1, s2 = st.columns([3, 1], gap="medium")
    with s1:
        query = st.text_input("🎬 Film", placeholder="Pulp Fiction…", key="sim_query")
    with s2:
        top_n = st.selectbox("🔢 Films", [5, 10, 15, 20], index=1, key="sim_n")

    if not query.strip():
        render_empty_state("🔗", "Tapez un film pour voir ce qui lui ressemble")
        return

    sql_ac = qb.build_movie_title_search_query(query, limit=8)
    try:
        df_ac = db.run_query(sql_ac)
    except Exception:
        df_ac = pd.DataFrame()

    if df_ac.empty:
        st.warning("Aucun film trouvé dans le dataset avec ce titre.")
        return

    labels = [f"{r['title']} ({int(r['release_year'])})" for _, r in df_ac.iterrows()]
    chosen_label = st.selectbox("✅ Sélectionner le film", labels, key="sim_choice")
    chosen_row = df_ac.iloc[labels.index(chosen_label)]
    ref_tmdb_id = chosen_row.get("tmdbId")

    ref_data = tmdb.fetch_movie_popularity(ref_tmdb_id) if ref_tmdb_id else {}
    rc1, rc2 = st.columns([0.12, 0.88])
    with rc1:
        if ref_data.get("poster_url"):
            st.image(ref_data["poster_url"], use_container_width=True)
    with rc2:
        g = str(chosen_row.get("genres", "")).replace("|", " · ")
        st.markdown(
            f'<div style="padding:0.5rem 0"><div style="font-size:1.2rem;font-weight:700">{chosen_label}</div>'
            f'<div style="font-size:0.82rem;color:#94a3b8">{g}</div></div>',
            unsafe_allow_html=True,
        )

    render_divider()

    if not ref_tmdb_id or str(ref_tmdb_id).strip() in ("", "nan"):
        st.info("Ce film n'a pas de tmdbId.")
        return

    with st.spinner(f"Recherche des films similaires…"):
        sim_ids = tmdb.fetch_similar_movie_tmdb_ids(ref_tmdb_id)

    if not sim_ids:
        st.info("Aucun similaire retourné par TMDB.")
        return

    sql_sim = qb.build_top_by_tmdb_ids_query(sim_ids, limit=top_n)
    st.markdown(f"### 🔗 Similaires à {chosen_label}")

    try:
        with st.spinner("Requête BigQuery…"):
            df_sim = db.run_query(sql_sim)
        render_sql_expander(sql_sim)
        if df_sim.empty:
            st.info(f"Aucun similaire dans notre base (sur {len(sim_ids)} TMDB).")
        else:
            st.caption(f"✅ {len(df_sim)} match(s) dataset sur {len(sim_ids)} candidats TMDB")
            render_top_movie_cards(df_sim, tmdb.fetch_movie_popularity)
    except Exception as e:
        st.error(f"❌ {e}")


def render(db, qb, tmdb) -> None:
    """Render the full Top Charts tab with its 5 sub-tabs."""
    st.markdown(
        """<div style="margin-bottom:1.5rem">
        <h2 style="color:white;margin:0">🏆 Top Charts</h2>
        <p style="color:#94a3b8;margin:0.3rem 0 0">Les films les plus populaires du dataset — classés par nombre de ratings (20M+ votes)</p>
        </div>""",
        unsafe_allow_html=True,
    )

    t1, t2, t3, t4, t5 = st.tabs([
        "🎭 Genre & Époque",
        "🎬 Réalisateur / Acteur",
        "🎪 Franchise / Saga",
        "🏷️ Thème / Keyword",
        "🔗 Films Similaires",
    ])

    with t1: _render_sub_genre(db, qb, tmdb)
    with t2: _render_sub_person(db, qb, tmdb)
    with t3: _render_sub_saga(db, qb, tmdb)
    with t4: _render_sub_theme(db, qb, tmdb)
    with t5: _render_sub_similar(db, qb, tmdb)
