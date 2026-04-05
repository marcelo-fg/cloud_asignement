# MovieFinder — Cloud & Advanced Analytics Assignment 2

Application de recommandation de films en architecture **2-tiers** :
**Streamlit** (frontend) + **Flask REST API** (backend), déployés sur **Google Cloud Run**.

---

## Live

| Service | URL |
|---------|-----|
| Frontend | https://moviefinder-frontend-262418330780.europe-west6.run.app |
| Backend API | https://moviefinder-backend-262418330780.europe-west6.run.app |

---

## Architecture

```
Utilisateur
 └─► Streamlit Frontend  (Cloud Run :8501)
          │  REST/JSON via api_client.py
          ▼
     Flask Backend  (Cloud Run :8080)
       ├── BigQuery       (recherche, filtres, métadonnées films)
       ├── BigQuery ML    (matrix_factorization — recommandations)
       ├── Elastic Cloud  (autocomplete search_as_you_type)
       └── TMDB API       (posters + métadonnées enrichies)
```

Le frontend **ne communique jamais directement** avec BigQuery ou Elasticsearch —
tout passe par l'API Flask via `api_client.py`.

---

## Fonctionnalités

| Fonctionnalité | Implémentation |
|----------------|----------------|
| Autocomplete | Elasticsearch `search_as_you_type` |
| Recherche avancée | Filtres genre, langue, année, note — SQL BigQuery dynamique |
| Top films | Films les mieux notés par genre et par décennie (window functions) |
| Recommandations personnalisées | BigQuery ML `matrix_factorization` via utilisateurs similaires |
| Fallback collaboratif | Films des users similaires si BQML indisponible |
| Fallback global | Top films (≥ 50 votes) si aucun film sélectionné |
| Posters & métadonnées | TMDB API (`/movie/{tmdbId}`) |
| Annuaire artistes | Recherche acteurs/réalisateurs via TMDB |
| Transparence | Toutes les requêtes BigQuery affichées dans le terminal backend |

---

## Structure du projet

```
cloud_asignement/
├── Dockerfile              ← Frontend Streamlit → Cloud Run
├── app.py                  ← Entrypoint Streamlit (routeur de pages)
├── api_client.py           ← Passerelle HTTP unique vers le backend Flask
├── tmdb.py                 ← Client TMDB API (frontend)
├── requirements.txt        ← Dépendances frontend (Streamlit, pandas, requests)
├── docker-compose.yml      ← Lancement local complet
├── deploy.sh               ← Script de déploiement Cloud Run (build + push + deploy)
├── train_model.py          ← Entraînement du modèle BQML
├── .env.example            ← Template variables d'environnement
│
├── ui/                     ← Pages et composants Streamlit
│   ├── home.py             ← Accueil : Top 10, carousels genre/décennie, "Pour vous"
│   ├── recommend.py        ← Recommandations personnalisées (cold-start pipeline)
│   ├── search.py           ← Recherche avancée multi-critères
│   ├── people.py           ← Annuaire artistes (acteurs / réalisateurs)
│   ├── movie.py            ← Page détail film
│   ├── components.py       ← Cards HTML réutilisables
│   └── styles.py           ← Thème sombre (CSS global)
│
├── backend/                ← Flask REST API → Cloud Run
│   ├── Dockerfile
│   ├── app.py              ← 11 routes REST (voir API Reference)
│   ├── recommender.py      ← Moteur de recommandation (cascade 3 niveaux)
│   ├── db.py               ← Client BigQuery backend
│   ├── es_client.py        ← Client Elasticsearch
│   ├── tmdb.py             ← Client TMDB API (backend)
│   ├── index_movies.py     ← Script d'indexation Elasticsearch
│   ├── train_model.sql     ← CREATE MODEL BigQuery ML
│   ├── utils.py            ← Normalisation des titres
│   └── requirements.txt
│
└── scripts/
    └── upload_data.py      ← Import données MovieLens → BigQuery
```

---

## API Reference

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| GET | `/health` | Statut du service |
| GET | `/autocomplete?q=<query>` | Suggestions Elasticsearch |
| POST | `/recommend` | Recommandations BigQuery ML (cold-start) |
| GET | `/movies/search` | Recherche filtrée (titre, genre, langue, année, note) |
| GET | `/movies/top` | Top films par note moyenne |
| GET | `/movies/top-per-genre` | Top N films par genre (window function) |
| GET | `/movies/top-per-decade` | Top N films par décennie (window function) |
| GET | `/movies/genres` | Liste des genres disponibles |
| GET | `/movies/languages` | Liste des langues disponibles |
| POST | `/movies/by-tmdb-ids` | Films BigQuery correspondant à une liste de TMDB IDs |
| POST | `/movies/ids-from-tmdb` | Convertit TMDB IDs → BigQuery movieIds |

---

## Méthode de recommandation — Cold-Start

Les utilisateurs web n'ont pas de `userId` dans les données d'entraînement.
Le pipeline résout le problème en 2 étapes :

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

| Table | Colonnes clés |
|-------|--------------|
| `movies` | movieId, title, genres, tmdbId, release_year |
| `ratings` | userId, movieId, rating, timestamp |

`tmdbId` est fusionné depuis `links.csv` lors de l'import (`scripts/upload_data.py`).

Modèle BQML : `assignement_1.movie_recommender`
Indice Elasticsearch : `movies` (champ `title` en `search_as_you_type`)

---

## Setup local

### Prérequis

- Docker + Docker Compose
- Un fichier `.env` rempli (copier depuis `.env.example`)

```bash
git clone https://github.com/marcelo-fg/cloud_asignement.git
cd cloud_asignement
cp .env.example .env
# Remplir .env avec vos credentials GCP, TMDB et Elasticsearch
```

### Lancement

```bash
docker-compose up --build
# Frontend : http://localhost:8501
# Backend  : http://localhost:5000
```

### Opérations one-time

```bash
# 1. Charger les données MovieLens dans BigQuery
python scripts/upload_data.py

# 2. Entraîner le modèle BQML
python train_model.py

# 3. Indexer les films dans Elasticsearch
python backend/index_movies.py
```

---

## Déploiement Cloud Run

### Variables d'environnement requises

| Variable | Description |
|----------|-------------|
| `GCP_PROJECT` | ID du projet GCP |
| `BQ_DATASET` | Dataset BigQuery (défaut : `assignement_1`) |
| `ES_URL` | URL du cluster Elasticsearch |

### Secrets dans Secret Manager

| Secret | Description |
|--------|-------------|
| `TMDB_API_KEY` | Clé API TMDB |
| `GCP_SERVICE_ACCOUNT` | JSON de la clé de service account GCP |
| `ES_API_KEY` | Clé API Elasticsearch |

### Déploiement automatique

```bash
export GCP_PROJECT=gen-lang-client-0671890527
export ES_URL=https://my-elasticsearch-project-cf23fb.es.us-central1.gcp.elastic.cloud:443
bash deploy.sh
```

Le script `deploy.sh` effectue dans l'ordre :
1. Active les APIs GCP nécessaires
2. Crée le dépôt Artifact Registry `moviefinder` (si absent)
3. Build et push des images Docker backend + frontend
4. Déploie le backend sur Cloud Run (`moviefinder-backend`)
5. Déploie le frontend sur Cloud Run (`moviefinder-frontend`) avec l'URL du backend injectée

---

## Tests

```bash
pip install pytest
pytest tests/ -v
```

---

## Auteur

Marcelo Gonçalves — Cloud & Advanced Analytics 2026
