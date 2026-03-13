import os
from typing import Dict, List

from catboost import CatBoostRegressor


class ModelService:
    def __init__(self, model_path: str, feature_order: str):
        self.model_path = model_path
        self.feature_order = [f.strip() for f in feature_order.split(",") if f.strip()]
        self._model = None

    def _load(self) -> CatBoostRegressor:
        if self._model is None:
            if not os.path.exists(self.model_path):
                raise FileNotFoundError(
                    f"Model file not found: {self.model_path}. Train with CatBoost.py first."
                )
            model = CatBoostRegressor()
            model.load_model(self.model_path)
            self._model = model
        return self._model

    def _resolve_feature_order(self, model: CatBoostRegressor) -> List[str]:
        if self.feature_order:
            return self.feature_order
        names = model.feature_names_ if hasattr(model, "feature_names_") else []
        if not names:
            raise ValueError("MODEL_FEATURES not provided and model has no feature names.")
        return list(names)

    def predict(self, features: Dict[str, float]) -> float:
        model = self._load()
        feature_order = self._resolve_feature_order(model)

        missing = [f for f in feature_order if f not in features]
        if missing:
            raise ValueError(f"Missing features: {', '.join(missing)}")

        row = [[float(features[f]) for f in feature_order]]
        pred = model.predict(row)
        return float(pred[0])
