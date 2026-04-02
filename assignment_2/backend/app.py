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
from recommender import get_recommendations
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
    movie_ids = data.get("movie_ids", [])
    n = int(data.get("n", 10))
    
    try:
        recommendations = get_recommendations(movie_ids, n)
        return jsonify(recommendations), 200
    except Exception as e:
        print(f"[API] Recommendation error: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    # Use port 5001 to avoid conflict with AirPlay (port 5000) on macOS
    app.run(host="0.0.0.0", port=5001, debug=True)
