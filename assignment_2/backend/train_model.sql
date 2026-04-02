-- BigQuery ML Matrix Factorization Model Training
-- Run this manually in the BigQuery Console

CREATE OR REPLACE MODEL `gen-lang-client-0671890527.assignement_1.movie_recommender`
OPTIONS (
  model_type='matrix_factorization',
  user_col='userId',
  item_col='movieId',
  rating_col='rating',
  feedback_type='explicit',
  num_factors=16,
  l2_reg=0.1,
  max_iterations=15
) AS
SELECT
  userId,
  movieId,
  rating
FROM
  `gen-lang-client-0671890527.assignement_1.ratings`;
