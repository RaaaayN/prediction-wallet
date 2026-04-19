"""Model Training Pipeline for Quantitative ML."""

import importlib
import importlib.util
import sys
import pandas as pd
import mlflow
import mlflow.sklearn
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score

from services.mlflow_service import MLflowService
from services.data_lake_service import DataLakeService

class MLTrainerService:
    def __init__(self, experiment_name: str = "Quantitative_Alpha"):
        self.mlflow_svc = MLflowService(experiment_name=experiment_name)
        self.lake = DataLakeService()
        
        # Reload alpha_factory to get the latest functions from the user
        import ml.alpha_factory
        importlib.reload(ml.alpha_factory)
        
        self.features = ml.alpha_factory.get_feature_list()
        
        # Get the model definition from the factory
        if hasattr(ml.alpha_factory, "get_model"):
            self.model_builder = ml.alpha_factory.get_model
        else:
            # Institutional Default: Random Forest
            from sklearn.ensemble import RandomForestClassifier
            self.model_builder = lambda: RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)

    def train_model(self, dataset_name: str, **kwargs):
        """Train a model on a specific Gold dataset with user-defined architecture."""
        data_dict = self.lake.load_gold(dataset_name)
        if not data_dict:
            raise ValueError(f"Dataset {dataset_name} not found in Gold layer.")

        # Combine all tickers into one training set
        all_data = pd.concat(data_dict.values())
        X = all_data[self.features]
        y = all_data["Target"]

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        # Build the specific model from user's custom code
        model = self.model_builder()
        model_class_name = model.__class__.__name__

        with self.mlflow_svc.start_run(run_name=f"{model_class_name}_{dataset_name}"):
            # 1. Train Model
            model.fit(X_train, y_train)

            # 2. Evaluate
            y_pred = model.predict(X_test)
            acc = accuracy_score(y_test, y_pred)
            prec = precision_score(y_test, y_pred, zero_division=0)

            # 3. Log to MLflow
            try:
                # Introspect parameters from the model object
                model_params = model.get_params()
            except Exception:
                model_params = {}
                
            mlflow.log_params({
                "model_class": model_class_name,
                "strategy_type": "predictive_ml",
                "features": self.features,
                **{k: str(v) for k, v in model_params.items() if len(str(v)) < 250}
            })
            mlflow.log_metrics({
                "accuracy": acc,
                "precision": prec
            })
            
            # Log the model binary
            mlflow.sklearn.log_model(model, "alpha_model", registered_model_name="Sklearn_Quant_Alpha")
            
            return {
                "run_id": mlflow.active_run().info.run_id,
                "accuracy": acc,
                "precision": prec,
                "model_class": model_class_name
            }
