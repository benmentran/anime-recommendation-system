import os
from abc import ABC, abstractmethod

import numpy as np
import pandas as pd

try:
    from sklearn.metrics.pairwise import cosine_similarity
except ImportError:  # ponytail: numpy fallback keeps the API image light (no sklearn)
    def cosine_similarity(X, Y=None):
        Y = X if Y is None else Y
        Xn = X / np.maximum(np.linalg.norm(X, axis=1, keepdims=True), 1e-12)
        Yn = Y / np.maximum(np.linalg.norm(Y, axis=1, keepdims=True), 1e-12)
        return Xn @ Yn.T


class Model(ABC):
    @abstractmethod
    def train(self, df: pd.DataFrame):
        pass

    @abstractmethod
    def recommend(self, user_id: int, N: int = 5):
        pass

def compute_user_item_matrix(df: pd.DataFrame) -> pd.DataFrame:
    user_item_matrix = df.pivot(index="user_id", columns="item_id", values="rating")
    os.makedirs("model", exist_ok=True)
    user_item_matrix.to_pickle('model/user_item_matrix.pkl')
    
    try:
        import mlflow  # optional: log artifact only when mlflow is installed
        mlflow.log_artifact('model/user_item_matrix.pkl', artifact_path='user_item_matrix')
    except ImportError:
        pass

    return user_item_matrix

class UserBasedCF(Model):
    def train(self, matrix_path: str = 'model/user_item_matrix.pkl'):
        self.user_item_matrix = pd.read_pickle(matrix_path).fillna(0)
        self.user_sim_matrix = cosine_similarity(self.user_item_matrix)
        self.user_sim_df = pd.DataFrame(self.user_sim_matrix,
                                        index=self.user_item_matrix.index,
                                        columns=self.user_item_matrix.index)

    def predict(self, user_id: int, item_id: int, k: int = 10):
        if item_id not in self.user_item_matrix.columns or user_id not in self.user_item_matrix.index:
            return np.nan

        users_rated = self.user_item_matrix[self.user_item_matrix[item_id] > 0].index
        if len(users_rated) == 0:
            return np.nan

        sim_scores = self.user_sim_df.loc[user_id, users_rated]
        top_k_users = sim_scores.sort_values(ascending=False).head(k)
        ratings = self.user_item_matrix.loc[top_k_users.index, item_id]

        if ratings.sum() == 0 or top_k_users.sum() == 0:
            return np.nan

        return np.dot(top_k_users, ratings) / np.sum(np.abs(top_k_users))

    def recommend(self, user_id: int, N: int = 10):
        if user_id not in self.user_item_matrix.index:
            return []

        items_rated = self.user_item_matrix.loc[user_id][self.user_item_matrix.loc[user_id] > 0].index
        all_items = self.user_item_matrix.columns
        unrated_items = [item for item in all_items if item not in items_rated]
        predictions = {item: self.predict(user_id, item) for item in unrated_items}
        ranked = sorted(predictions.items(), key=lambda x: x[1], reverse=True)
        return ranked[:N]

class ItemBasedCF(Model):
    def train(self, matrix_path: str = 'model/user_item_matrix.pkl'):
        self.user_item_matrix = pd.read_pickle(matrix_path)
        self.item_user_matrix = self.user_item_matrix.T.fillna(0)
        self.item_sim_matrix = cosine_similarity(self.item_user_matrix)
        self.item_sim_df = pd.DataFrame(self.item_sim_matrix,
                                        index=self.item_user_matrix.index,
                                        columns=self.item_user_matrix.index)

    def predict(self, user_id: int, item_id: int, k: int = 10):
        if user_id not in self.user_item_matrix.index or item_id not in self.item_sim_df.index:
            return np.nan

        user_ratings = self.user_item_matrix.loc[user_id].dropna()
        if item_id in user_ratings:
            return user_ratings[item_id]

        sim_scores = self.item_sim_df.loc[item_id, user_ratings.index]
        top_k_items = sim_scores.sort_values(ascending=False).head(k)
        top_k_ratings = user_ratings[top_k_items.index]

        if top_k_ratings.empty or top_k_items.sum() == 0:
            return np.nan

        return np.dot(top_k_items, top_k_ratings) / np.sum(np.abs(top_k_items))

    def recommend(self, user_id: int, N: int = 10):
        if user_id not in self.user_item_matrix.index:
            return []

        user_rated = self.user_item_matrix.loc[user_id].dropna().index
        all_items = self.item_user_matrix.index
        unrated_items = [item for item in all_items if item not in user_rated]
        predictions = {item: self.predict(user_id, item) for item in unrated_items}
        ranked = sorted(predictions.items(), key=lambda x: x[1], reverse=True)
        return ranked[:N]

class ContentBasedFiltering(Model):
    def train(self, df: pd.DataFrame | None = None, reviews_df: pd.DataFrame | None = None):
        """
        Train both feature-based and review-based similarity matrices.
        reviews_df is optional (anime has no reviews table -> feature-only).
        """
        if df is None or len(df) == 0:
            raise ValueError("ContentBasedFiltering.train needs item features df "
                             "(use scripts/build_cf_matrices.py for the live path)")
        # Build feature-based item-item similarity
        features = np.vstack(df['feature_vector'].to_numpy())
        self.feature_similarity = cosine_similarity(features)
        self.df = df.reset_index(drop=True)

        # Build review-based item-item similarity (if reviews exist)
        if reviews_df is not None and len(reviews_df) > 0:
            reviews = np.vstack(reviews_df['review_vectorize'].to_numpy())
            self.review_similarity = cosine_similarity(reviews)
        else:
            self.review_similarity = None
        
        # Map movie_id to index
        self.movie_id_to_index = {
            movie_id: idx for idx, movie_id in enumerate(df['movie_id'])
        }

        # Track movie_ids that have reviews
        self.movies_with_reviews = set(reviews_df['movie_id'].tolist()) \
            if reviews_df is not None and len(reviews_df) > 0 else set()

    def recommend(self, movie_index: int, top_k=10):
        """
        Recommend top_k similar movies to the given movie_id.
        Use review similarity if available, else fallback to feature similarity.
        """
        idx = self.movie_id_to_index.get(movie_index)
        if idx is None:
            return []  # Movie not found

        if movie_index in self.movies_with_reviews:
            sim_scores = self.review_similarity[idx].copy()
        else:
            sim_scores = self.feature_similarity[idx].copy()

        # Get top_k similar movies (excluding the movie itself)
        sim_scores[idx] = -1  # Exclude itself (trên bản copy, không độc ma trận cache)
        similar_indices = np.argsort(sim_scores)[::-1][:top_k]

        recommended_movie_ids = self.df.iloc[similar_indices]['movie_id'].tolist()
        
        return recommended_movie_ids
    
class MatrixFactorization(Model):
    def train(self, df, **kwargs):
        pass
    
