"""
tests/test_query_builder.py
Unit tests for the SQL builder functions in query_builder.py.
Run with: pytest tests/ -v
"""

import sys
import os
import types

# ── Minimal stubs to avoid importing BigQuery/Streamlit at collection time ────
# Stub `streamlit` so query_builder doesn't need a real Streamlit install
st_stub = types.ModuleType("streamlit")
st_stub.cache_data = lambda *a, **kw: (lambda f: f)
st_stub.cache_resource = lambda *a, **kw: (lambda f: f)
st_stub.secrets = {}
sys.modules.setdefault("streamlit", st_stub)

# Stub `google.*` family
for mod in [
    "google", "google.cloud", "google.cloud.bigquery",
    "google.oauth2", "google.oauth2.service_account",
    "google.cloud.bigquery_storage",
]:
    if mod not in sys.modules:
        sys.modules[mod] = types.ModuleType(mod)

# Stub pandas (only the parts db.py uses at import time)
if "pandas" not in sys.modules:
    pd_stub = types.ModuleType("pandas")
    sys.modules["pandas"] = pd_stub

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Patch the constants that query_builder.py reads from db after import
import importlib
import db as _db_module
_db_module.MOVIES_TABLE = "project.dataset.movies"
_db_module.RATINGS_TABLE = "project.dataset.ratings"

import query_builder as qb


# ── build_autocomplete_query ──────────────────────────────────────────────────

class TestAutocompleteQuery:
    def test_contains_prefix(self):
        sql = qb.build_autocomplete_query("inc")
        assert "inc" in sql.lower()

    def test_limit_10(self):
        sql = qb.build_autocomplete_query("star")
        assert "LIMIT 10" in sql

    def test_case_insensitive(self):
        sql = qb.build_autocomplete_query("star")
        assert "LOWER" in sql

    def test_empty_prefix(self):
        sql = qb.build_autocomplete_query("")
        assert "SELECT" in sql
        assert "LIMIT 10" in sql

    def test_sql_injection_escape(self):
        sql = qb.build_autocomplete_query("O'Brien")
        # Raw unescaped single-quote must not appear in the LIKE value
        # The escaped form \' or '' is acceptable
        assert "O'Brien" not in sql


# ── build_movie_search_query ──────────────────────────────────────────────────

class TestMovieSearchQuery:
    def test_no_filters(self):
        sql = qb.build_movie_search_query()
        assert "SELECT" in sql
        assert "FROM" in sql
        assert "WHERE" not in sql

    def test_title_filter(self):
        sql = qb.build_movie_search_query(title="inception")
        assert "inception" in sql.lower()
        assert "LIKE" in sql

    def test_language_filter(self):
        sql = qb.build_movie_search_query(language="en")
        assert "language" in sql.lower()
        assert "'en'" in sql

    def test_language_all_skipped(self):
        sql = qb.build_movie_search_query(language="All")
        assert "'All'" not in sql

    def test_genre_filter_single(self):
        sql = qb.build_movie_search_query(genres=["Action"])
        assert "Action" in sql
        assert "genres" in sql.lower()

    def test_genre_filter_multiple(self):
        sql = qb.build_movie_search_query(genres=["Action", "Comedy"])
        assert "Action" in sql
        assert "Comedy" in sql

    def test_genre_pipe_handling(self):
        sql = qb.build_movie_search_query(genres=["Sci-Fi"])
        assert "|" in sql  # Handles pipe-separated genres column

    def test_year_filter(self):
        sql = qb.build_movie_search_query(min_year=2000)
        assert "2000" in sql
        assert "release_year" in sql

    def test_year_1900_not_applied(self):
        sql = qb.build_movie_search_query(min_year=1900)
        assert "1900" not in sql

    def test_rating_filter_with_join(self):
        sql = qb.build_movie_search_query(min_rating=3.5, has_ratings_table=True)
        assert "JOIN" in sql
        assert "AVG" in sql
        assert "HAVING" in sql
        assert "3.5" in sql

    def test_rating_filter_no_ratings_table(self):
        sql = qb.build_movie_search_query(min_rating=3.5, has_ratings_table=False)
        assert "JOIN" not in sql

    def test_combo_filters(self):
        sql = qb.build_movie_search_query(
            title="toy",
            language="en",
            genres=["Animation"],
            min_year=1995,
        )
        assert "toy" in sql.lower()
        assert "'en'" in sql
        assert "Animation" in sql
        assert "1995" in sql
        assert "AND" in sql

    def test_limit_applied(self):
        sql = qb.build_movie_search_query(limit=50)
        assert "LIMIT 50" in sql

    def test_impossible_title_no_crash(self):
        sql = qb.build_movie_search_query(title="xyzxyzxyz_impossible_1234")
        assert "SELECT" in sql


# ── build_distinct_languages_query ────────────────────────────────────────────

class TestLanguagesQuery:
    def test_returns_select(self):
        sql = qb.build_distinct_languages_query()
        assert "SELECT DISTINCT language" in sql

    def test_filters_null(self):
        sql = qb.build_distinct_languages_query()
        assert "IS NOT NULL" in sql


# ── build_distinct_genres_query ───────────────────────────────────────────────

class TestGenresQuery:
    def test_uses_unnest_split(self):
        sql = qb.build_distinct_genres_query()
        assert "UNNEST" in sql
        assert "SPLIT" in sql
        assert "|" in sql

    def test_orders_by_genre(self):
        sql = qb.build_distinct_genres_query()
        assert "ORDER BY genre" in sql


# ── build_genre_distribution_query ────────────────────────────────────────────

class TestGenreDistributionQuery:
    def test_has_count(self):
        sql = qb.build_genre_distribution_query()
        assert "COUNT(*)" in sql
        assert "movie_count" in sql

    def test_default_limit(self):
        sql = qb.build_genre_distribution_query()
        assert "LIMIT 15" in sql

    def test_custom_limit(self):
        sql = qb.build_genre_distribution_query(limit=5)
        assert "LIMIT 5" in sql

    def test_groups_by_genre(self):
        sql = qb.build_genre_distribution_query()
        assert "GROUP BY genre" in sql


# ── build_year_distribution_query ─────────────────────────────────────────────

class TestYearDistributionQuery:
    def test_has_release_year(self):
        sql = qb.build_year_distribution_query()
        assert "release_year" in sql

    def test_min_year_applied(self):
        sql = qb.build_year_distribution_query(min_year=1990)
        assert "1990" in sql

    def test_orders_by_year(self):
        sql = qb.build_year_distribution_query()
        assert "ORDER BY release_year" in sql
