from db import run_query, RATINGS_TABLE, MOVIES_TABLE, MODEL_NAME
from tmdb import fetch_movie_popularity
from utils import normalize_title
from typing import List, Dict, Any

def get_recommendations(liked_movie_ids: List[int], n: int = 10) -> List[Dict[str, Any]]:
    """
    3-step recommendation engine.
    """
    if not liked_movie_ids:
        return get_global_fallback(n)

    movie_ids_str = ", ".join(map(str, liked_movie_ids))
    
    # 1. Find similar users
    similar_users_sql = f"""
    SELECT userId, COUNT(*) as common_movies
    FROM `{RATINGS_TABLE}`
    WHERE movieId IN ({movie_ids_str}) AND rating >= 3.5
    GROUP BY userId
    ORDER BY common_movies DESC
    LIMIT 10
    """
    
    try:
        similar_users = [row["userId"] for row in run_query(similar_users_sql)]
        if not similar_users:
            return get_global_fallback(n)
        
        users_str = ", ".join(map(str, [f"'{u}'" if isinstance(u, str) else str(u) for u in similar_users]))
        
        # 2. Get BQML Recommendations
        bqml_sql = f"""
        SELECT 
            t.movieId, 
            AVG(t.predicted_rating) as avg_pred, 
            COUNT(DISTINCT t.userId) as user_count,
            m.title,
            m.genres,
            m.release_year,
            m.tmdbId
        FROM ML.RECOMMEND(MODEL `{MODEL_NAME}`, (SELECT userId FROM UNNEST([{users_str}]) as userId)) t
        JOIN `{MOVIES_TABLE}` m ON t.movieId = m.movieId
        WHERE t.movieId NOT IN ({movie_ids_str})
        GROUP BY t.movieId, m.title, m.genres, m.release_year, m.tmdbId
        ORDER BY avg_pred DESC, user_count DESC
        LIMIT {n}
        """
        
        recommendations = run_query(bqml_sql)
        results = [dict(row) for row in recommendations]
        
        if not results:
            return get_sql_fallback(liked_movie_ids, n)
            
        return enrich_with_tmdb(results)
        
    except Exception as e:
        print(f"[RECOMMENDER] BQML failed: {e}. Falling back to SQL...")
        return get_sql_fallback(liked_movie_ids, n)

def get_sql_fallback(liked_movie_ids: List[int], n: int = 10) -> List[Dict[str, Any]]:
    """
    SQL-based collaborative filtering fallback if BQML fails.
    """
    movie_ids_str = ", ".join(map(str, liked_movie_ids))
    
    sql = f"""
    WITH similar_users AS (
        SELECT userId, COUNT(*) as common_movies
        FROM `{RATINGS_TABLE}`
        WHERE movieId IN ({movie_ids_str}) AND rating >= 3.5
        GROUP BY userId
        ORDER BY common_movies DESC
        LIMIT 20
    ),
    recommended_movies AS (
        SELECT r.movieId, AVG(r.rating) as avg_rating, COUNT(DISTINCT r.userId) as user_count
        FROM `{RATINGS_TABLE}` r
        JOIN similar_users s ON r.userId = s.userId
        WHERE r.movieId NOT IN ({movie_ids_str}) AND r.rating >= 4.0
        GROUP BY r.movieId
        ORDER BY avg_rating DESC, user_count DESC
        LIMIT {n}
    )
    SELECT rm.movieId, rm.avg_rating, rm.user_count, m.title, m.genres, m.release_year, m.tmdbId
    FROM recommended_movies rm
    JOIN `{MOVIES_TABLE}` m ON rm.movieId = m.movieId
    """
    
    try:
        results = [dict(row) for row in run_query(sql)]
        if not results:
            return get_global_fallback(n)
        return enrich_with_tmdb(results)
    except Exception as e:
        print(f"[RECOMMENDER] SQL fallback failed: {e}. Global fallback...")
        return get_global_fallback(n)

def get_global_fallback(n: int = 10) -> List[Dict[str, Any]]:
    """
    Global top-rated fallback (highest average rating with at least 50 ratings).
    """
    sql = f"""
    WITH stats AS (
        SELECT movieId, AVG(rating) as avg_rating, COUNT(*) as vote_count
        FROM `{RATINGS_TABLE}`
        GROUP BY movieId
        HAVING vote_count >= 50
    )
    SELECT s.movieId, s.avg_rating, s.vote_count, m.title, m.genres, m.release_year, m.tmdbId
    FROM stats s
    JOIN `{MOVIES_TABLE}` m ON s.movieId = m.movieId
    ORDER BY avg_rating DESC, vote_count DESC
    LIMIT {n}
    """
    results = [dict(row) for row in run_query(sql)]
    return enrich_with_tmdb(results)

def enrich_with_tmdb(movies: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Enriches movie dicts with TMDB poster URLs and normalizes titles."""
    for m in movies:
        m["title"] = normalize_title(m.get("title", ""))
        tmdb_info = fetch_movie_popularity(m.get("tmdbId"))
        m["poster_url"] = tmdb_info.get("poster_url")
    return movies
