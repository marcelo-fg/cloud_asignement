# MovieFinder — Cloud & Advanced Analytics Assignment 2

Application de recommandation de films en architecture **2-tiers** :
**Streamlit** (frontend) + **Flask REST API** (backend), déployés sur **Google Cloud Run**.

---

## Live

| Service | URL |
|---------|-----|
| 🎬 Frontend | https://movie-frontend-262418330780.us-central1.run.app |
| ⚙️ Backend API | https://movie-backend-262418330780.us-central1.run.app |

---

## Architecture

```
Utilisateur
 └─► Streamlit Frontend  (Cloud Run)
          │  REST JSON
          ▼
     Flask Backend  (Cloud Run :8080)
       ├── BigQuery ML  (matrix_factorization — recommandations personnalisées)
       ├── Elastic Cloud (autocomplete search-as-you-type)
       └── TMDB API      (posters + métadonnées films)
```

Le frontend **ne communique jamais directement** avec BigQuery ou Elasticsearch — tout passe par l'API Flask.

---

## Fonctionnalités

| Fonctionnalité | Implémentation |
|----------------|----------------|
| Autocomplete | Elasticsearch `search_as_you_type` |
| Recommandations personnalisées | BigQuery ML `matrix_factorization` via utilisateurs similaires |
| Fallback SQL collaboratif | Agrégation des films des users similaires si BQML échoue |
| Fallback global | Top films les mieux notés (≥ 50 votes) si aucun film sélectionné |
| Posters | TMDB API (`/movie/{tmdbId}`) |
| Transparence SQL | Toutes les requêtes BigQuery affichées dans le terminal |

---

## Structure du projet

```
cloud_asignement/
├── Dockerfile              ← Frontend (Streamlit) → Cloud Run
├── app.py                  ← Entrypoint Streamlit
├── db.py                   ← Client BigQuery (frontend)
├── query_builder.py        ← Générateur SQL dynamique
├── tmdb.py                 ← Client TMDB API (frontend)
├── requirements.txt        ← Dépendances frontend
├── ui/                     ← Composants UI Streamlit
│   ├── home.py             ← Page d'accueil (Top 10, carousels genre/décennie)
│   ├── recommend.py        ← Page recommandations (cold-start pipeline)
│   ├── search.py           ← Recherche avancée avec filtres
│   ├── people.py           ← Recherche d'artistes (acteurs/réalisateurs)
│   ├── movie.py            ← Page détail film
│   ├── components.py       ← Cards HTML réutilisables
│   └── styles.py           ← Thème Netflix (CSS global)
│
├── backend/                ← Flask REST API → Cloud Run
│   ├── Dockerfile
│   ├── app.py              ← Routes (/autocomplete, /recommend, /movies/popular)
│   ├── recommender.py      ← Moteur de recommandation (cascade 3 niveaux)
│   ├── db.py               ← Client BigQuery (backend)
│   ├── es_client.py        ← Client Elasticsearch
│   ├── tmdb.py             ← Client TMDB API (backend)
│   ├── index_movies.py     ← Script d'indexation Elasticsearch
│   ├── train_model.sql     ← CREATE MODEL BigQuery ML
│   ├── utils.py            ← Normalisation des titres
│   └── requirements.txt
│
├── docker-compose.yml      ← Lancement local complet
├── .env.example            ← Template variables d'environnement
├── train_model.py          ← Script entraînement BQML
├── deploy.sh               ← Script déploiement Cloud Run
├── scripts/
│   └── upload_data.py      ← Import données MovieLens → BigQuery
└── tests/
    ├── test_query_builder.py
    └── test_tmdb.py
```

---

## Méthode de recommandation — Cold-Start

Les utilisateurs web n'ont pas de `userId` dans les données d'entraînement. Pipeline en 3 étapes :

### Étape 1 — Trouver les utilisateurs similaires (SQL BigQuery)
```sql
SELECT userId, COUNT(*) AS common_movies
FROM `assignement_1.ratings`
WHERE movieId IN (<films_sélectionnés>) AND rating >= 3.5
GROUP BY userId
ORDER BY common_movies DESC
LIMIT 50
```

### Étape 2 — Générer les recommandations via BigQuery ML
```sql
SELECT movieId, AVG(predicted_rating) AS avg_pred
FROM ML.RECOMMEND(
  MODEL `assignement_1.movie_recommender`,
  (SELECT userId FROM UNNEST([<top_50_users>]) AS userId)
)
GROUP BY movieId ORDER BY avg_pred DESC LIMIT 12
```

Modèle : `matrix_factorization`, **64 facteurs**, **20 itérations**, RMSE ≈ 0.37.

### Cascade de fallback

| Niveau | Méthode | Déclenchement |
|--------|---------|---------------|
| 1 | BigQuery ML `ML.RECOMMEND` | Toujours tenté en premier |
| 2 | SQL collaboratif (films des users similaires) | Si BQML indisponible |
| 3 | SQL global (top films, ≥ 50 votes) | Aucun film sélectionné ou tout échoue |

---

## Données

Dataset **MovieLens ml-latest-small** chargé dans BigQuery (`assignement_1`) :

| Table | Colonnes |
|-------|----------|
| `movies` | movieId, title, genres, tmdbId, language, release_year, country |
| `ratings` | userId, movieId, rating, timestamp |

> `tmdbId` provient de `links.csv` et est fusionné dans `movies` à l'import (`scripts/upload_data.py`).

---

## Setup local

```bash
# 1. Cloner et configurer
git clone https://github.com/marcelo-fg/cloud_asignement.git
cd cloud_asignement
cp .env.example .env
# Remplir .env avec vos credentials

# 2. Lancer avec Docker Compose
docker-compose up --build
# Frontend : http://localhost:8080
# Backend  : http://localhost:8080
```

### Opérations one-time
```bash
# Charger les données MovieLens dans BigQuery
python scripts/upload_data.py

# Entraîner le modèle BQML
python train_model.py

# Indexer les films dans Elasticsearch
cd backend && python index_movies.py
```

---

## Déploiement Cloud Run

```bash
# Backend
gcloud run deploy movie-backend \
  --source ./backend \
  --region us-central1 \
  --allow-unauthenticated \
  --port 8080 \
  --update-secrets="TMDB_API_KEY=TMDB_API_KEY:latest,GCP_SA_JSON=GCP_SERVICE_ACCOUNT:latest,ES_API_KEY=ES_API_KEY:latest" \
  --set-env-vars="GCP_PROJECT=gen-lang-client-0671890527,BQ_DATASET=assignement_1,ES_URL=<votre-es-url>"

# Frontend
gcloud run deploy movie-frontend \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --port 8080 \
  --update-secrets="TMDB_API_KEY=TMDB_API_KEY:latest,GCP_SA_JSON=GCP_SERVICE_ACCOUNT:latest" \
  --set-env-vars="BACKEND_URL=https://movie-backend-262418330780.us-central1.run.app"
```

---

## Tests

```bash
pip install pytest
pytest tests/ -v
```

---

## Auteur

Marcelo Gonçalves — Cloud & Advanced Analytics 2026
