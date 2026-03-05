"""
query_builder.py – Business-logic / SQL builder layer
Pure functions that construct SQL strings.  No BigQuery calls here.
"""

from __future__ import annotations

from db import MOVIES_TABLE, RATINGS_TABLE


# ── Utility ────────────────────────────────────────────────────────────────────

def _escape(value: str) -> str:
    """Minimally escape a string for safe interpolation into SQL literals."""
    return value.replace("'", "\\'")


# ── Dropdown / autocomplete queries ───────────────────────────────────────────

def build_autocomplete_query(prefix: str) -> str:
    """Return up to 10 movie titles matching *prefix* (case-insensitive)."""
    safe = _escape(prefix)
    return f"""
SELECT DISTINCT title
FROM `{MOVIES_TABLE}`
WHERE LOWER(title) LIKE LOWER('%{safe}%')
ORDER BY title
LIMIT 10
""".strip()


def build_distinct_languages_query() -> str:
    return f"""
SELECT DISTINCT language
FROM `{MOVIES_TABLE}`
WHERE language IS NOT NULL AND language != ''
ORDER BY language
""".strip()


def build_distinct_genres_query() -> str:
    """Return individual genres by splitting the pipe-separated genres column."""
    return f"""
SELECT DISTINCT genre
FROM `{MOVIES_TABLE}`,
UNNEST(SPLIT(genres, '|')) AS genre
WHERE genres IS NOT NULL AND genres != ''
ORDER BY genre
""".strip()


# ── Main search query ──────────────────────────────────────────────────────────

def build_movie_search_query(
    title: str = "",
    language: str = "All",
    genres: list[str] | None = None,
    min_rating: float = 0.0,
    min_year: int = 1900,
    limit: int = 200,
    has_ratings_table: bool = True,
) -> str:
    """
    Build a dynamic SQL query combining all filters.

    Parameters
    ----------
    title          : partial title to match (LIKE)
    language       : exact language string, or "All" to skip
    genres         : list of genre strings (each must appear in genres column)
    min_rating     : minimum average rating threshold (0 = no filter)
    min_year       : movies released on or after this year
    limit          : max rows returned
    has_ratings_table : if False, skip the JOIN on ratings
    """
    genres = genres or []
    conditions: list[str] = []

    # Title filter
    if title.strip():
        safe_title = _escape(title.strip())
        conditions.append(f"LOWER(m.title) LIKE LOWER('%{safe_title}%')")

    # Language filter
    if language and language != "All":
        safe_lang = _escape(language)
        conditions.append(f"m.language = '{safe_lang}'")

    # Genre filter (each selected genre must be present)
    for g in genres:
        safe_g = _escape(g)
        conditions.append(
            f"(m.genres LIKE '{safe_g}|%' OR m.genres LIKE '%|{safe_g}|%' "
            f"OR m.genres LIKE '%|{safe_g}' OR m.genres = '{safe_g}')"
        )

    # Release year filter
    if min_year and min_year > 1900:
        conditions.append(f"m.release_year >= {int(min_year)}")

    where_clause = ("WHERE " + "\n  AND ".join(conditions)) if conditions else ""

    if has_ratings_table and min_rating > 0.0:
        # JOIN with ratings table to compute average rating
        rating_having = f"HAVING AVG(r.rating) >= {min_rating}"
        sql = f"""
SELECT
    m.movieId,
    m.title,
    m.genres,
    m.language,
    m.release_year,
    m.country,
    m.tmdbId,
    ROUND(AVG(r.rating), 2) AS avg_rating
FROM `{MOVIES_TABLE}` AS m
JOIN `{RATINGS_TABLE}` AS r
  ON CAST(m.movieId AS STRING) = CAST(r.movieId AS STRING)
{where_clause}
GROUP BY
    m.movieId, m.title, m.genres, m.language,
    m.release_year, m.country, m.tmdbId
{rating_having}
ORDER BY avg_rating DESC
LIMIT {limit}
""".strip()
    else:
        # No rating join needed
        # Replace "m." prefix with plain column names when no alias needed
        # Since we always alias as m, keep alias even without JOIN.
        sql = f"""
SELECT
    m.movieId,
    m.title,
    m.genres,
    m.language,
    m.release_year,
    m.country,
    m.tmdbId
FROM `{MOVIES_TABLE}` AS m
{where_clause}
ORDER BY m.release_year DESC, m.title
LIMIT {limit}
""".strip()

    return sql


# ── Genre/Year distribution charts ────────────────────────────────────────────

def build_genre_distribution_query(limit: int = 15) -> str:
    return f"""
SELECT genre, COUNT(*) AS movie_count
FROM `{MOVIES_TABLE}`,
UNNEST(SPLIT(genres, '|')) AS genre
WHERE genres IS NOT NULL AND genres != ''
GROUP BY genre
ORDER BY movie_count DESC
LIMIT {limit}
""".strip()


def build_year_distribution_query(min_year: int = 1980) -> str:
    return f"""
SELECT release_year, COUNT(*) AS movie_count
FROM `{MOVIES_TABLE}`
WHERE release_year >= {min_year} AND release_year IS NOT NULL
GROUP BY release_year
ORDER BY release_year
""".strip()
