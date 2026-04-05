-- BigQuery ML Matrix Factorization Model Training
-- Run this manually in the BigQuery Console

CREATE OR REPLACE MODEL `gen-lang-client-0671890527.assignement_1.movie_recommender`
OPTIONS (
  model_type='matrix_factorization',
  user_col='userId',
  item_col='movieId',
  rating_col='rating',
  feedback_type='explicit',
  -- Tuning des hyperparamètres
  num_trials=10,
  num_factors=HPARAM_CANDIDATES([32, 64, 128]),
  l2_reg=HPARAM_RANGE(0.01, 10.0),
  max_iterations=50,
  early_stop=TRUE
) AS
SELECT
  userId,
  movieId,
  AVG(rating) AS rating
FROM
  `gen-lang-client-0671890527.assignement_1.ratings`
GROUP BY
  userId,
  movieId;
