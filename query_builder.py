"""
query_builder.py – SQL builder layer
Pure functions that construct SQL strings. No BigQuery calls here.
"""

from __future__ import annotations

from db import MOVIES_TABLE, RATINGS_TABLE


# ── Utility ────────────────────────────────────────────────────────────────────

def _escape(value: str) -> str:
    """Escape single quotes for safe interpolation into SQL literals."""
    return value.replace("'", "\\'")


def _genre_condition(genre: str, alias: str = "m") -> str:
    """Return a WHERE condition that matches a genre in a pipe-separated column."""
    g = _escape(genre)
    col = f"{alias}.genres"
    return (
        f"({col} LIKE '{g}|%' OR {col} LIKE '%|{g}|%' "
        f"OR {col} LIKE '%|{g}' OR {col} = '{g}')"
    )


# ── Dropdown / autocomplete queries ───────────────────────────────────────────

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


# ── Movie search / autocomplete ────────────────────────────────────────────────

def build_movie_search_query(
    title: str = "",
    language: str = "All",
    genres: list[str] | None = None,
    rating_min: float = 0.0,
    rating_max: float = 5.0,
    year_min: int = 1900,
    year_max: int = 2026,
    limit: int = 200,
    has_ratings_table: bool = True,
    tmdb_ids: list[int] | None = None,
) -> str:
    """
    Build a dynamic SQL query combining all search filters.
    """
    genres = genres or []
    conditions: list[str] = []

    if tmdb_ids is not None:
        if not tmdb_ids:
            # If the user requested an explicit list of IDs but it's empty, return an impossible SQL condition
            # so the BigQuery query executes but correctly yields 0 results.
            conditions.append("1 = 0")
        else:
            # Max of 500 IDs to avoid query bloat
            sliced_ids = tmdb_ids[:500]
            ids_str = ", ".join(str(i) for i in sliced_ids)
            conditions.append(f"CAST(m.tmdbId AS INT64) IN ({ids_str})")
    elif title.strip():
        conditions.append(f"LOWER(m.title) LIKE LOWER('%{_escape(title.strip())}%')")

    if language and language != "All":
        conditions.append(f"m.language = '{_escape(language)}'")

    for g in genres:
        conditions.append(_genre_condition(g))

    if year_min > 1900 or year_max < 2026:
        conditions.append(f"m.release_year BETWEEN {int(year_min)} AND {int(year_max)}")

    where = ("WHERE " + "\n  AND ".join(conditions)) if conditions else ""

    if has_ratings_table:
        # Use a safe threshold to avoid movies with a single 5.0 rating jumping to the top of filters
        rating_clause = ""
        if rating_min > 0.0 or rating_max < 5.0:
            rating_clause = f"HAVING AVG(r.rating) BETWEEN {rating_min} AND {rating_max} AND COUNT(r.rating) >= 5"
            
        return f"""
SELECT
    m.movieId, m.title, m.genres, m.language,
    m.release_year, m.country, m.tmdbId,
    ROUND(AVG(r.rating), 2) AS avg_rating,
    COUNT(r.rating) AS nb_ratings
FROM `{MOVIES_TABLE}` AS m
JOIN `{RATINGS_TABLE}` AS r
  ON CAST(m.movieId AS STRING) = CAST(r.movieId AS STRING)
{where}
GROUP BY m.movieId, m.title, m.genres, m.language, m.release_year, m.country, m.tmdbId
{rating_clause}
ORDER BY nb_ratings DESC, avg_rating DESC
LIMIT {limit}
""".strip()

    return f"""
SELECT
    m.movieId, m.title, m.genres, m.language,
    m.release_year, m.country, m.tmdbId
FROM `{MOVIES_TABLE}` AS m
{where}
ORDER BY m.release_year DESC, m.title
LIMIT {limit}
""".strip()


def build_movie_title_search_query(title_prefix: str, limit: int = 10) -> str:
    """
    Title autocomplete with tmdbId filter — used by the Similar Movies picker.
    Only returns movies that have a tmdbId and release_year.
    """
    safe = _escape(title_prefix.strip())
    return f"""
SELECT movieId, title, release_year, genres, tmdbId
FROM `{MOVIES_TABLE}`
WHERE LOWER(title) LIKE LOWER('%{safe}%')
  AND tmdbId IS NOT NULL
  AND release_year IS NOT NULL
ORDER BY release_year DESC
LIMIT {limit}
""".strip()


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


# ── Top Charts ─────────────────────────────────────────────────────────────────

# Decade label → (min_year, max_year)
DECADES: dict[str, tuple[int, int]] = {
    "🎞️ 1950s": (1950, 1959),
    "🕺 1960s": (1960, 1969),
    "🪩 1970s": (1970, 1979),
    "🎸 1980s": (1980, 1989),
    "📼 1990s": (1990, 1999),
    "💿 2000s": (2000, 2009),
    "📱 2010s": (2010, 2015),
}

# Common JOIN + GROUP BY block reused by top-chart queries
_TOP_SELECT = """\
SELECT
    m.movieId, m.title, m.genres, m.release_year,
    m.language, m.country, m.tmdbId,
    COUNT(r.rating)          AS nb_ratings,
    ROUND(AVG(r.rating), 2)  AS avg_rating
FROM `{movies}` AS m
JOIN `{ratings}` AS r
  ON CAST(m.movieId AS STRING) = CAST(r.movieId AS STRING)
{{where}}
GROUP BY m.movieId, m.title, m.genres, m.release_year, m.language, m.country, m.tmdbId
HAVING COUNT(r.rating) >= 100
ORDER BY avg_rating DESC, nb_ratings DESC
LIMIT {{limit}}"""


def build_top_charts_query(
    genre: str | None = None,
    decade_label: str | None = None,
    limit: int = 10,
) -> str:
    """
    Top `limit` movies ranked by nb_ratings, with optional genre + decade filters.
    Year range capped at 1900–2015 to avoid ML-20M data-quality outliers.
    """
    conditions = [
        "m.release_year IS NOT NULL",
        "m.release_year BETWEEN 1900 AND 2015",
    ]
    if genre:
        conditions.append(_genre_condition(genre))
    if decade_label and decade_label in DECADES:
        min_y, max_y = DECADES[decade_label]
        conditions.append(f"m.release_year BETWEEN {min_y} AND {max_y}")

    where = "WHERE " + "\n  AND ".join(conditions)
    base = _TOP_SELECT.format(movies=MOVIES_TABLE, ratings=RATINGS_TABLE)
    return base.format(where=where, limit=limit)


def build_top_movies_per_genre_query(limit: int = 10) -> str:
    """Return the top N movies per genre using a window function."""
    return f"""
WITH MovieGenres AS (
  SELECT
    m.movieId, m.title, m.release_year, m.tmdbId,
    TRIM(genre) AS genre,
    COUNT(r.rating)          AS nb_ratings,
    ROUND(AVG(r.rating), 2)  AS avg_rating
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
    ROW_NUMBER() OVER(PARTITION BY genre ORDER BY avg_rating DESC, nb_ratings DESC) as rank_in_genre
  FROM MovieGenres
)
SELECT * FROM RankedGenres WHERE rank_in_genre <= {limit} ORDER BY genre, rank_in_genre
""".strip()


def build_top_by_tmdb_ids_query(tmdb_ids: list[int], limit: int = 10) -> str:
    """
    Top `limit` movies from our dataset that match a given list of TMDB IDs,
    ranked by nb_ratings.

    Used for: actor/director filmography, franchise films, keyword-tagged films,
              similar-movie recommendations.

    Caps the IN list at 500 IDs to avoid oversized queries on prolific actors.
    """
    if not tmdb_ids:
        return ""

    ids = tmdb_ids[:500]
    ids_str = ", ".join(str(int(i)) for i in ids)
    where = f"WHERE CAST(m.tmdbId AS INT64) IN ({ids_str})\n  AND m.release_year IS NOT NULL"

    base = _TOP_SELECT.format(movies=MOVIES_TABLE, ratings=RATINGS_TABLE)
    return base.format(where=where, limit=limit)


def build_top_movies_per_decade_query(limit: int = 20) -> str:
    """Return the top N movies per decade using a window function."""
    return f"""
WITH MovieDecades AS (
  SELECT
    m.movieId, m.title, m.release_year, m.tmdbId,
    CAST(FLOOR(m.release_year / 10) * 10 AS INT64) AS decade,
    COUNT(r.rating)          AS nb_ratings,
    ROUND(AVG(r.rating), 2)  AS avg_rating
  FROM `{MOVIES_TABLE}` AS m
  JOIN `{RATINGS_TABLE}` AS r
    ON CAST(m.movieId AS STRING) = CAST(r.movieId AS STRING)
  WHERE m.release_year IS NOT NULL AND m.release_year BETWEEN 1900 AND 2015
  GROUP BY m.movieId, m.title, m.release_year, m.tmdbId
  HAVING COUNT(r.rating) >= 50
),
RankedDecades AS (
  SELECT *,
    ROW_NUMBER() OVER(PARTITION BY decade ORDER BY avg_rating DESC, nb_ratings DESC) as rank_in_decade
  FROM MovieDecades
)
SELECT * FROM RankedDecades 
WHERE rank_in_decade <= {limit} 
  AND decade IN (1960, 1970, 1980, 1990, 2000, 2010)
ORDER BY decade DESC, rank_in_decade
""".strip()
