class ModelLoader:
    def __init__(self):
        self.user_cf_model = None
        self.item_cf_model = None
        self.content_based_model = None

    def load_models(self):
        import mlflow.pyfunc as pyfunc  # ponytail: lazy so router imports without mlflow installed
        self.user_cf_model = pyfunc.load_model(model_uri="models:/UserCFPyfuncModel_model/Production")
        self.item_cf_model = pyfunc.load_model(model_uri="models:/ItemCFPyfuncModel_model/Production")
        self.content_based_model = pyfunc.load_model(model_uri="models:/ContentFPyfuncModel_model/Production")

    def get_user_cf_model(self):
        return self.user_cf_model

    def get_item_cf_model(self):
        return self.item_cf_model

    def get_content_based_model(self):
        return self.content_based_model
    