"""MLflow pyfunc wrappers (isolated: importing this requires mlflow installed).

The pure CF algorithms live in pipelines/model_dev.py (numpy/pandas only).
Only pipelines/train_pipeline.py imports from here (lazy, offline training).
"""
import mlflow.pyfunc as pyfunc

from pipelines.model_dev import ContentBasedFiltering, ItemBasedCF, UserBasedCF


class UserCFPyfuncModel(pyfunc.PythonModel):
    def __init__(self, model: UserBasedCF):
        self.model = model

    def predict(self, model_input: list[dict[str, int]], params=None):
        results = []

        for row in model_input:
            user_id = row.get('user_id', None)
            item_id = row.get('item_id', None)
            k = row.get('k', 5)

            results.append(self.model.predict(user_id=user_id, item_id=item_id, k=k))

        return results


class ItemCFPyfuncModel(pyfunc.PythonModel):
    def __init__(self, model: ItemBasedCF):
        self.model = model

    def predict(self, model_input: list[dict[str, int]], params=None):
        results = []

        for row in model_input:
            user_id = row.get('user_id', None)
            item_id = row.get('item_id', None)
            k = row.get('k', 5)

            results.append(self.model.predict(user_id=user_id, item_id=item_id, k=k))

        return results


class ContentFPyfuncModel(pyfunc.PythonModel):
    def __init__(self, model: ContentBasedFiltering):
        self.model = model

    def predict(self, model_input: list[dict[str, int]], params=None):
        """
        Given input as list of dicts with 'movie_id', return recommended movie_ids.
        Example input: [{'movie_id': 123}, {'movie_id': 456}]
        """
        results = []
        for item in model_input:
            movie_id = item.get('movie_id')
            recommended = self.model.recommend(movie_id, top_k=params.get('top_k', 5) if params else 5)
            results.append({'movie_id': movie_id, 'recommendations': recommended})

        return results
