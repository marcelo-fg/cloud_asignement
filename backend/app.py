import os
import sys

# Load .env from assignment_2/ (one level up from this file)
_env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
try:
    from dotenv import load_dotenv
    load_dotenv(_env_path)
except ImportError:
    pass  # dotenv not available, rely on env vars being set externally

# Ensure this directory is on sys.path so local modules resolve correctly
sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask, request, jsonify
from flask_cors import CORS
from es_client import autocomplete
from recommender import get_recommendations, enrich_with_tmdb
from db import run_query, MOVIES_TABLE, RATINGS_TABLE
from tmdb import fetch_movie_popularity

app = Flask(__name__)
CORS(app)

@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok"}), 200

@app.route("/autocomplete", methods=["GET"])
def handle_autocomplete():
    """Autocomplete endpoint using Elasticsearch."""
    query = request.args.get("q", "")
    limit = int(request.args.get("limit", 8))
    
    if len(query) < 2:
        return jsonify([]), 200
        
    try:
        results = autocomplete(query, limit)
        return jsonify(results), 200
    except Exception as e:
        print(f"[API] Autocomplete error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/recommend", methods=["POST"])
def handle_recommend():
    """Recommendation endpoint."""
    data = request.json or {}
    movie_ids           = data.get("movie_ids", [])
    movie_ratings       = data.get("movie_ratings", None)
    genres              = data.get("genres") or None
    year_min            = data.get("year_min") or None
    year_max            = data.get("year_max") or None
    person_tmdb_ids     = data.get("person_tmdb_ids") or None
    excluded_movie_ids  = data.get("excluded_movie_ids") or None
    n                   = int(data.get("n", 10))

    try:
        recommendations = get_recommendations(
            liked_movie_ids    = movie_ids,
            movie_ratings      = movie_ratings,
            genres             = genres,
            year_min           = year_min,
            year_max           = year_max,
            person_tmdb_ids    = person_tmdb_ids,
            excluded_movie_ids = excluded_movie_ids,
            n                  = n,
        )
        return jsonify(recommendations), 200
    except Exception as e:
        print(f"[API] Recommendation error: {e}")
        return jsonify({"error": str(e)}), 500

# ── A1-style routes ──────────────────────────────────────────────────────────

@app.route("/movies/search", methods=["GET"])
def handle_search():
    """Search movies using BigQuery SQL with filters. Supports optional tmdb_ids filter."""
    title      = request.args.get("title", "").strip()
    genres     = request.args.getlist("genre")
    language   = request.args.get("language", "")
    year_min   = int(request.args.get("year_min", 1900))
    year_max   = int(request.args.get("year_max", 2026))
    rating_min = float(request.args.get("rating_min", 0.0))
    rating_max = float(request.args.get("rating_max", 5.0))
    limit      = min(int(request.args.get("limit", 100)), 500)
    tmdb_ids_raw = request.args.get("tmdb_ids", "")

    # Parse optional tmdb_ids filter (comma-separated string)
    # None  → no filter; empty list → impossible condition (0 results); list → IN clause
    tmdb_ids = None
    if tmdb_ids_raw != "":
        try:
            tmdb_ids = [int(x) for x in tmdb_ids_raw.split(",") if x.strip()]
        except ValueError:
            tmdb_ids = []

    conditions = []

    if tmdb_ids is not None:
        if not tmdb_ids:
            conditions.append("1 = 0")
        else:
            ids_str = ", ".join(str(i) for i in tmdb_ids[:500])
            conditions.append(f"CAST(m.tmdbId AS INT64) IN ({ids_str})")
    elif title:
        safe = title.replace("'", "\\'")
        conditions.append(f"LOWER(m.title) LIKE LOWER('%{safe}%')")

    if language and language not in ("", "All"):
        conditions.append(f"m.language = '{language}'")
    for g in genres:
        safe_g = g.replace("'", "\\'")
        conditions.append(
            f"(m.genres LIKE '{safe_g}|%' OR m.genres LIKE '%|{safe_g}|%' "
            f"OR m.genres LIKE '%|{safe_g}' OR m.genres = '{safe_g}')"
        )
    if year_min > 1900 or year_max < 2026:
        conditions.append(f"m.release_year BETWEEN {year_min} AND {year_max}")

    where         = ("WHERE " + "\n  AND ".join(conditions)) if conditions else ""
    rating_having = ""
    if rating_min > 0.0 or rating_max < 5.0:
        rating_having = (
            f"HAVING AVG(r.rating) BETWEEN {rating_min} AND {rating_max} "
            f"AND COUNT(r.rating) >= 5"
        )

    sql = f"""
    SELECT m.movieId, m.title, m.genres, m.language,
           m.release_year, m.country, m.tmdbId,
           ROUND(AVG(r.rating), 2) AS avg_rating,
           COUNT(r.rating)         AS nb_ratings
    FROM `{MOVIES_TABLE}` AS m
    JOIN `{RATINGS_TABLE}` AS r
      ON CAST(m.movieId AS STRING) = CAST(r.movieId AS STRING)
    {where}
    GROUP BY m.movieId, m.title, m.genres, m.language, m.release_year, m.country, m.tmdbId
    {rating_having}
    ORDER BY nb_ratings DESC, avg_rating DESC
    LIMIT {limit}
    """
    try:
        df      = run_query(sql)
        results = df.to_dict("records")
        results = enrich_with_tmdb(results[:20])
        return jsonify(results), 200
    except Exception as e:
        print(f"[API] Search error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/movies/by-tmdb-ids", methods=["POST"])
def handle_movies_by_tmdb_ids():
    """Return top-rated BQ movies matching a list of TMDB IDs (for filmography / people pages)."""
    data     = request.json or {}
    tmdb_ids = data.get("tmdb_ids", [])
    limit    = min(int(data.get("limit", 60)), 500)

    if not tmdb_ids:
        return jsonify([]), 200

    ids = [int(i) for i in tmdb_ids[:500]]
    ids_str = ", ".join(str(i) for i in ids)
    sql = f"""
    SELECT
        m.movieId, m.title, m.genres, m.release_year,
        m.language, m.country, m.tmdbId,
        COUNT(r.rating)         AS nb_ratings,
        ROUND(AVG(r.rating), 2) AS avg_rating
    FROM `{MOVIES_TABLE}` AS m
    JOIN `{RATINGS_TABLE}` AS r
      ON CAST(m.movieId AS STRING) = CAST(r.movieId AS STRING)
    WHERE CAST(m.tmdbId AS INT64) IN ({ids_str})
      AND m.release_year IS NOT NULL
    GROUP BY m.movieId, m.title, m.genres, m.release_year, m.language, m.country, m.tmdbId
    HAVING COUNT(r.rating) >= 100
    ORDER BY avg_rating DESC, nb_ratings DESC
    LIMIT {limit}
    """
    try:
        df      = run_query(sql)
        results = df.to_dict("records")
        return jsonify(results), 200
    except Exception as e:
        print(f"[API] by-tmdb-ids error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/movies/ids-from-tmdb", methods=["POST"])
def handle_ids_from_tmdb():
    """Convert a list of TMDB IDs to BigQuery movieIds."""
    data     = request.json or {}
    tmdb_ids = data.get("tmdb_ids", [])

    if not tmdb_ids:
        return jsonify([]), 200

    ids = [int(i) for i in tmdb_ids[:500]]
    ids_str = ", ".join(str(i) for i in ids)
    sql = f"SELECT movieId FROM `{MOVIES_TABLE}` WHERE CAST(tmdbId AS INT64) IN ({ids_str})"
    try:
        df = run_query(sql)
        return jsonify(df["movieId"].tolist()), 200
    except Exception as e:
        print(f"[API] ids-from-tmdb error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/movies/top-per-genre", methods=["GET"])
def handle_top_per_genre():
    """Top N movies per genre using a window function."""
    limit = min(int(request.args.get("limit", 10)), 20)
    sql = f"""
    WITH MovieGenres AS (
      SELECT
        m.movieId, m.title, m.release_year, m.tmdbId,
        TRIM(genre) AS genre,
        COUNT(r.rating)         AS nb_ratings,
        ROUND(AVG(r.rating), 2) AS avg_rating
      FROM `{MOVIES_TABLE}` AS m
      JOIN `{RATINGS_TABLE}` AS r
        ON CAST(m.movieId AS STRING) = CAST(r.movieId AS STRING),
      UNNEST(SPLIT(m.genres, '|')) AS genre
      WHERE m.release_year IS NOT NULL AND m.release_year BETWEEN 1900 AND 2015
        AND TRIM(genre) != '(no genres listed)'
      GROUP BY m.movieId, m.title, genre, m.release_year, m.tmdbId
      HAVING COUNT(r.rating) >= 50
    ),
    RankedGenres AS (
      SELECT *,
        ROW_NUMBER() OVER(PARTITION BY genre ORDER BY avg_rating DESC, nb_ratings DESC) AS rank_in_genre
      FROM MovieGenres
    )
    SELECT * FROM RankedGenres WHERE rank_in_genre <= {limit} ORDER BY genre, rank_in_genre
    """
    try:
        df      = run_query(sql)
        results = df.to_dict("records")
        return jsonify(results), 200
    except Exception as e:
        print(f"[API] top-per-genre error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/movies/top-per-decade", methods=["GET"])
def handle_top_per_decade():
    """Top N movies per decade using a window function."""
    limit = min(int(request.args.get("limit", 20)), 50)
    sql = f"""
    WITH MovieDecades AS (
      SELECT
        m.movieId, m.title, m.release_year, m.tmdbId,
        CAST(FLOOR(m.release_year / 10) * 10 AS INT64) AS decade,
        COUNT(r.rating)         AS nb_ratings,
        ROUND(AVG(r.rating), 2) AS avg_rating
      FROM `{MOVIES_TABLE}` AS m
      JOIN `{RATINGS_TABLE}` AS r
        ON CAST(m.movieId AS STRING) = CAST(r.movieId AS STRING)
      WHERE m.release_year IS NOT NULL AND m.release_year BETWEEN 1900 AND 2015
      GROUP BY m.movieId, m.title, m.release_year, m.tmdbId
      HAVING COUNT(r.rating) >= 50
    ),
    RankedDecades AS (
      SELECT *,
        ROW_NUMBER() OVER(PARTITION BY decade ORDER BY avg_rating DESC, nb_ratings DESC) AS rank_in_decade
      FROM MovieDecades
    )
    SELECT * FROM RankedDecades
    WHERE rank_in_decade <= {limit}
      AND decade IN (1960, 1970, 1980, 1990, 2000, 2010)
    ORDER BY decade DESC, rank_in_decade
    """
    try:
        df      = run_query(sql)
        results = df.to_dict("records")
        return jsonify(results), 200
    except Exception as e:
        print(f"[API] top-per-decade error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/movies/top", methods=["GET"])
def handle_top():
    """Top-rated movies with optional genre and decade filters."""
    genre  = request.args.get("genre", "")
    decade = request.args.get("decade", "")
    limit  = min(int(request.args.get("limit", 12)), 50)

    conditions = ["m.release_year IS NOT NULL", "m.release_year BETWEEN 1900 AND 2015"]
    if genre:
        conditions.append(
            f"(m.genres LIKE '{genre}|%' OR m.genres LIKE '%|{genre}|%' "
            f"OR m.genres LIKE '%|{genre}' OR m.genres = '{genre}')"
        )
    if decade:
        try:
            dec = int(decade)
            conditions.append(f"m.release_year BETWEEN {dec} AND {dec + 9}")
        except ValueError:
            pass

    where = "WHERE " + "\n  AND ".join(conditions)
    sql   = f"""
    SELECT m.movieId, m.title, m.genres, m.release_year,
           m.language, m.country, m.tmdbId,
           COUNT(r.rating)         AS nb_ratings,
           ROUND(AVG(r.rating), 2) AS avg_rating
    FROM `{MOVIES_TABLE}` AS m
    JOIN `{RATINGS_TABLE}` AS r
      ON CAST(m.movieId AS STRING) = CAST(r.movieId AS STRING)
    {where}
    GROUP BY m.movieId, m.title, m.genres, m.release_year, m.language, m.country, m.tmdbId
    HAVING COUNT(r.rating) >= 100
    ORDER BY avg_rating DESC, nb_ratings DESC
    LIMIT {limit}
    """
    try:
        df      = run_query(sql)
        results = df.to_dict("records")
        results = enrich_with_tmdb(results)
        return jsonify(results), 200
    except Exception as e:
        print(f"[API] Top charts error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/movies/genres", methods=["GET"])
def handle_genres():
    try:
        sql = f"""
        SELECT DISTINCT genre FROM `{MOVIES_TABLE}`,
        UNNEST(SPLIT(genres, '|')) AS genre
        WHERE genres IS NOT NULL AND genres != ''
          AND genre != '(no genres listed)'
        ORDER BY genre
        """
        df = run_query(sql)
        return jsonify(df["genre"].tolist()), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/movies/languages", methods=["GET"])
def handle_languages():
    try:
        sql = f"""
        SELECT DISTINCT language FROM `{MOVIES_TABLE}`
        WHERE language IS NOT NULL AND language != ''
        ORDER BY language LIMIT 60
        """
        df = run_query(sql)
        return jsonify(df["language"].tolist()), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    # Use port 5001 to avoid conflict with AirPlay (port 5000) on macOS
    app.run(host="0.0.0.0", port=5001, debug=True)
