import pytest
from unittest.mock import patch, MagicMock
import tmdb

def test_poster_url():
    assert tmdb._poster_url("/path.jpg") == "https://image.tmdb.org/t/p/w500/path.jpg"
    assert tmdb._poster_url(None) is None

@patch("tmdb.requests.get")
def test_fetch_movie_details(mock_get):
    # Mock return for movie details
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "title": "Test Movie",
        "overview": "Test Overview",
        "poster_path": "/test.jpg",
        "genres": [{"name": "Action"}],
        "credits": {"cast": [{"name": "Actor", "character": "Hero", "profile_path": "/profile.jpg"}], "crew": []}
    }
    mock_get.return_value = mock_resp
    
    with patch("tmdb._get_api_key", return_value="fake_key"):
        details = tmdb.fetch_movie_details(123)
        assert details["title"] == "Test Movie"
        assert details["genres"] == ["Action"]
        assert len(details["cast"]) == 1
        assert details["cast"][0]["name"] == "Actor"

@patch("tmdb.requests.get")
def test_fetch_movie_popularity(mock_get):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "title": "Famous Movie",
        "popularity": 100.0,
        "poster_path": "/famous.jpg"
    }
    mock_get.return_value = mock_resp
    
    with patch("tmdb._get_api_key", return_value="fake_key"):
        pop = tmdb.fetch_movie_popularity(456)
        assert pop["title"] == "Famous Movie"
        assert pop["popularity"] == 100.0
