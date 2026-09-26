"""Offline training entries. Airflow/DVC import this module directly.

Heavy deps (mlflow/sklearn) are imported lazily inside functions so that
`import pipelines.train_pipeline` stays light. Model code lives in
pipelines/model_dev.py. Ratings default to data/processed/ratings.csv
(params: pipelines.train.ratings_csv).
"""
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _train_cfg():
    with open(PROJECT_ROOT / "params.yaml") as f:
        cfg = yaml.safe_load(f)
    return (cfg.get("pipelines", {}).get("train") or {})


def _ratings_df(csv=None):
    import pandas as pd  # ponytail: lazy, keeps module import light

    path = Path(csv or _train_cfg().get("ratings_csv", "data/processed/ratings.csv"))
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return pd.read_csv(path)


def save_user_item_matrix(csv=None):
    from pipelines.model_dev import compute_user_item_matrix  # lazy: pulls sklearn/mlflow

    df = _ratings_df(csv)
    compute_user_item_matrix(df)


def _get_or_train(model_instance):
    import mlflow  # lazy
    import mlflow.pyfunc as pyfunc
    from mlflow.tracking import MlflowClient

    client = MlflowClient()
    name = model_instance.__class__.__name__
    exp = client.get_experiment_by_name(name)
    exp_id = exp.experiment_id if exp else client.create_experiment(name)
    runs = client.search_runs([exp_id], f"tags.mlflow.runName = '{name}'",
                              order_by=["start_time desc"], max_results=1)
    if runs:
        return pyfunc.load_model(f"runs:/{runs[0].info.run_id}/model")
    model_instance.model.train()
    with mlflow.start_run(run_name=name):
        mlflow.log_param("model_type", name)
        pyfunc.log_model(artifact_path="model", python_model=model_instance,
                         registered_model_name=f"{name}_model",
                         input_example=[{"user_id": 1, "item_id": 1, "k": 5}])
    return model_instance


def user_based_cf_pipeline():
    from pipelines.model_dev import UserBasedCF, UserCFPyfuncModel  # lazy

    _get_or_train(UserCFPyfuncModel(model=UserBasedCF()))


def item_based_cf_pipeline():
    from pipelines.model_dev import ItemBasedCF, ItemCFPyfuncModel  # lazy

    _get_or_train(ItemCFPyfuncModel(model=ItemBasedCF()))


def content_based_filtering_pipeline():
    from pipelines.model_dev import ContentBasedFiltering, ContentFPyfuncModel  # lazy

    _get_or_train(ContentFPyfuncModel(model=ContentBasedFiltering()))


def evaluation_pipeline(model, X_test, y_test, k=10):
    import mlflow  # lazy
    from sklearn.metrics import mean_squared_error  # lazy

    mlflow.set_experiment("ModelEvaluation")
    with mlflow.start_run(run_name="EvaluationPipeline"):
        mlflow.log_metric("rmse", float(mean_squared_error(y_test, model.predict(X_test)) ** 0.5))
        mlflow.set_tag("step", "evaluation_pipeline")


if __name__ == "__main__":
    save_user_item_matrix()
