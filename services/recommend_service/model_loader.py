"""Model loading: local pickles first (demo, no registry), mlflow kept for compat."""
import os
import pickle


def _load(path):
    try:
        with open(path, "rb") as f:
            return pickle.load(f)
    except (OSError, pickle.PickleError):
        return None


class ModelLoader:
    def __init__(self, model_dir: str | None = None):
        self.model_dir = model_dir or os.getenv("MODEL_DIR", "model")
        self.user_cf_model = None
        self.item_cf_model = None
        self.content_based_model = None
        self.popular: list = []
        self._loaded = False

    def load_models(self):
        """Legacy mlflow-registry path (training envs only)."""
        import mlflow.pyfunc as pyfunc  # ponytail: lazy so router imports without mlflow installed
        self.user_cf_model = pyfunc.load_model(model_uri="models:/UserCFPyfuncModel_model/Production")
        self.item_cf_model = pyfunc.load_model(model_uri="models:/ItemCFPyfuncModel_model/Production")
        self.content_based_model = pyfunc.load_model(model_uri="models:/ContentFPyfuncModel_model/Production")
        self._loaded = True

    def load_local(self, model_dir: str | None = None):
        """Load matrices built by scripts/build_cf_matrices.py. Missing files -> None (not fatal)."""
        d = model_dir or self.model_dir
        self.user_cf_model = _load(os.path.join(d, "user_cf.pkl"))
        self.item_cf_model = _load(os.path.join(d, "item_cf.pkl"))
        self.content_based_model = _load(os.path.join(d, "content_cf.pkl"))
        self.popular = _load(os.path.join(d, "popular.pkl")) or []
        self._loaded = True

    def ensure_loaded(self):
        if not self._loaded:
            try:
                self.load_local()
            except Exception:
                pass  # getters below decide 503 vs popularity fallback
        return self

    def get_user_cf_model(self):
        return self.user_cf_model

    def get_item_cf_model(self):
        return self.item_cf_model

    def get_content_based_model(self):
        return self.content_based_model

    def get_popular(self, k: int = 10) -> list:
        return list(self.popular[:k])
