from db import run_query, RATINGS_TABLE, MOVIES_TABLE, MODEL_NAME
from tmdb import fetch_movie_popularity, fetch_person_movie_tmdb_ids
from utils import normalize_title
from typing import List, Dict, Any, Optional
import requests, os

TMDB_API_KEY = os.getenv("TMDB_API_KEY")
TMDB_BASE    = "https://api.themoviedb.org/3"


# ── Public entry point ────────────────────────────────────────────────────────

def get_recommendations(
    liked_movie_ids:  List[int],
    genres:           Optional[List[str]] = None,
    year_min:         Optional[int]       = None,
    year_max:         Optional[int]       = None,
    person_tmdb_ids:  Optional[List[int]] = None,
    n:                int                 = 10,
) -> List[Dict[str, Any]]:
    """
    Enriched recommendation engine.

    Seeds  = liked_movie_ids
           + top movies of preferred genres (BigQuery)
           + movies of preferred actors/directors (TMDB → BigQuery)

    Output = BQML predictions filtered by genres & year range
           → SQL collaborative fallback
           → global top-rated fallback
    """

    # ── 1. Expand seed movie_ids from preferences ─────────────────────────────
    seed_ids = set(liked_movie_ids)

    if genres:
        seed_ids |= _top_movies_by_genres(genres, limit=30)

    if person_tmdb_ids:
        seed_ids |= _movies_by_persons(person_tmdb_ids, limit=40)

    seed_ids = list(seed_ids)

    if not seed_ids:
        return _global_fallback(n, genres, year_min, year_max)

    # ── 2. Build output filter clauses ────────────────────────────────────────
    genre_filter = _genre_sql_filter(genres, table_alias="m")
    year_filter  = _year_sql_filter(year_min, year_max, table_alias="m")

    # ── 3. Run BQML → SQL fallback → global fallback ──────────────────────────
    try:
        results = _bqml(seed_ids, liked_movie_ids, genre_filter, year_filter, n)
        if results:
            return enrich_with_tmdb(results)
    except Exception as e:
        print(f"[RECOMMENDER] BQML failed: {e}")

    try:
        results = _sql_collaborative(seed_ids, liked_movie_ids, genre_filter, year_filter, n)
        if results:
            return enrich_with_tmdb(results)
    except Exception as e:
        print(f"[RECOMMENDER] SQL fallback failed: {e}")

    return _global_fallback(n, genres, year_min, year_max)


# ── Seed expansion helpers ────────────────────────────────────────────────────

def _top_movies_by_genres(genres: List[str], limit: int = 30) -> set:
    """Return movieIds of top-rated films matching any of the given genres."""
    conditions = " OR ".join([f"m.genres LIKE '%{g}%'" for g in genres])
    sql = f"""
    WITH stats AS (
        SELECT movieId, AVG(rating) as avg_r, COUNT(*) as cnt
        FROM `{RATINGS_TABLE}`
        GROUP BY movieId HAVING cnt >= 30
    )
    SELECT s.movieId
    FROM stats s
    JOIN `{MOVIES_TABLE}` m ON s.movieId = m.movieId
    WHERE {conditions}
    ORDER BY avg_r DESC
    LIMIT {limit}
    """
    try:
        df = run_query(sql)
        return set(df["movieId"].tolist())
    except Exception as e:
        print(f"[RECOMMENDER] genre seed query failed: {e}")
        return set()


def _movies_by_persons(person_tmdb_ids: List[int], limit: int = 40) -> set:
    """Resolve TMDB person IDs → their movie tmdbIds → BigQuery movieIds."""
    tmdb_ids = set()
    for pid in person_tmdb_ids:
        try:
            r = requests.get(
                f"{TMDB_BASE}/person/{pid}/combined_credits",
                params={"api_key": TMDB_API_KEY},
                timeout=4,
            )
            if r.status_code == 200:
                data = r.json()
                # Grab cast + crew movie tmdbIds
                for item in data.get("cast", []) + data.get("crew", []):
                    if item.get("media_type") == "movie" and item.get("id"):
                        tmdb_ids.add(item["id"])
        except Exception as e:
            print(f"[RECOMMENDER] TMDB person {pid} failed: {e}")

    if not tmdb_ids:
        return set()

    tmdb_ids_str = ", ".join(map(str, list(tmdb_ids)[:200]))
    sql = f"""
    SELECT movieId FROM `{MOVIES_TABLE}`
    WHERE tmdbId IN ({tmdb_ids_str})
    LIMIT {limit}
    """
    try:
        df = run_query(sql)
        return set(df["movieId"].tolist())
    except Exception as e:
        print(f"[RECOMMENDER] person→movieId query failed: {e}")
        return set()


# ── SQL filter builders ───────────────────────────────────────────────────────

def _genre_sql_filter(genres: Optional[List[str]], table_alias: str = "m") -> str:
    if not genres:
        return ""
    conditions = " OR ".join([f"{table_alias}.genres LIKE '%{g}%'" for g in genres])
    return f"AND ({conditions})"

def _year_sql_filter(year_min: Optional[int], year_max: Optional[int], table_alias: str = "m") -> str:
    clauses = []
    if year_min:
        clauses.append(f"{table_alias}.release_year >= {year_min}")
    if year_max:
        clauses.append(f"{table_alias}.release_year <= {year_max}")
    return ("AND " + " AND ".join(clauses)) if clauses else ""


# ── Core engines ──────────────────────────────────────────────────────────────

def _bqml(
    seed_ids:      List[int],
    exclude_ids:   List[int],
    genre_filter:  str,
    year_filter:   str,
    n:             int,
) -> List[Dict]:
    seed_str    = ", ".join(map(str, seed_ids))
    exclude_str = ", ".join(map(str, exclude_ids)) if exclude_ids else "NULL"

    # Find users who liked our seed movies
    similar_users_sql = f"""
    SELECT userId, COUNT(*) as common_movies
    FROM `{RATINGS_TABLE}`
    WHERE movieId IN ({seed_str}) AND rating >= 3.5
    GROUP BY userId
    ORDER BY common_movies DESC
    LIMIT 50
    """
    df_users = run_query(similar_users_sql)
    similar_users = df_users["userId"].tolist()

    if not similar_users:
        return []

    users_str = ", ".join([f"'{u}'" if isinstance(u, str) else str(u) for u in similar_users])

    bqml_sql = f"""
    SELECT
        t.movieId,
        AVG(t.predicted_rating) as avg_pred,
        COUNT(DISTINCT t.userId)  as user_count,
        m.title, m.genres, m.release_year, m.tmdbId
    FROM ML.RECOMMEND(
        MODEL `{MODEL_NAME}`,
        (SELECT userId FROM UNNEST([{users_str}]) as userId)
    ) t
    JOIN `{MOVIES_TABLE}` m ON t.movieId = m.movieId
    WHERE t.movieId NOT IN ({exclude_str})
    {genre_filter}
    {year_filter}
    GROUP BY t.movieId, m.title, m.genres, m.release_year, m.tmdbId
    ORDER BY avg_pred DESC, user_count DESC
    LIMIT {n}
    """
    df = run_query(bqml_sql)
    return df.to_dict("records")


def _sql_collaborative(
    seed_ids:     List[int],
    exclude_ids:  List[int],
    genre_filter: str,
    year_filter:  str,
    n:            int,
) -> List[Dict]:
    seed_str    = ", ".join(map(str, seed_ids))
    exclude_str = ", ".join(map(str, exclude_ids)) if exclude_ids else "NULL"

    sql = f"""
    WITH similar_users AS (
        SELECT userId, COUNT(*) as common_movies
        FROM `{RATINGS_TABLE}`
        WHERE movieId IN ({seed_str}) AND rating >= 3.5
        GROUP BY userId ORDER BY common_movies DESC LIMIT 50
    ),
    candidates AS (
        SELECT r.movieId, AVG(r.rating) as avg_rating, COUNT(DISTINCT r.userId) as user_count
        FROM `{RATINGS_TABLE}` r
        JOIN similar_users s ON r.userId = s.userId
        WHERE r.movieId NOT IN ({exclude_str}) AND r.rating >= 3.5
        GROUP BY r.movieId
        ORDER BY avg_rating DESC, user_count DESC
        LIMIT {n * 3}
    )
    SELECT c.movieId, c.avg_rating, c.user_count,
           m.title, m.genres, m.release_year, m.tmdbId
    FROM candidates c
    JOIN `{MOVIES_TABLE}` m ON c.movieId = m.movieId
    WHERE 1=1
    {genre_filter}
    {year_filter}
    ORDER BY c.avg_rating DESC
    LIMIT {n}
    """
    df = run_query(sql)
    return df.to_dict("records")


def _global_fallback(
    n:          int,
    genres:     Optional[List[str]] = None,
    year_min:   Optional[int]       = None,
    year_max:   Optional[int]       = None,
) -> List[Dict[str, Any]]:
    genre_filter = _genre_sql_filter(genres, "m")
    year_filter  = _year_sql_filter(year_min, year_max, "m")

    sql = f"""
    WITH stats AS (
        SELECT movieId, AVG(rating) as avg_rating, COUNT(*) as vote_count
        FROM `{RATINGS_TABLE}`
        GROUP BY movieId HAVING vote_count >= 50
    )
    SELECT s.movieId, s.avg_rating, s.vote_count,
           m.title, m.genres, m.release_year, m.tmdbId
    FROM stats s
    JOIN `{MOVIES_TABLE}` m ON s.movieId = m.movieId
    WHERE 1=1
    {genre_filter}
    {year_filter}
    ORDER BY avg_rating DESC, vote_count DESC
    LIMIT {n}
    """
    try:
        df = run_query(sql)
        return enrich_with_tmdb(df.to_dict("records"))
    except Exception as e:
        print(f"[RECOMMENDER] global fallback failed: {e}")
        return []


# ── TMDB enrichment ───────────────────────────────────────────────────────────

def enrich_with_tmdb(movies: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    for m in movies:
        m["title"] = normalize_title(m.get("title", ""))
        tmdb_info  = fetch_movie_popularity(m.get("tmdbId"))
        m["poster_url"] = tmdb_info.get("poster_url") if tmdb_info else None
    return movies
