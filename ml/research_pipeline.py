import pandas as pd
import numpy as np
import mlflow
import mlflow.sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, precision_score
from services.data_lake_service import DataLakeService
from market.fetcher import MarketDataService, add_technical_indicators

# 1. LOAD DATA
print("--- STAGE 1: DATA LOADING ---")
lake = DataLakeService()
# You can load from the lake or use Yahoo directly
tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"]
mkt = MarketDataService()
data_bundles = {}
for t in tickers:
    df = mkt.get_historical(t, days=365)
    if df is not None:
        data_bundles[t] = df
        print(f"✓ Loaded {t}: {len(df)} rows")

# 2. FEATURE ENGINEERING
print("\n--- STAGE 2: FEATURE ENGINEERING ---")
full_df_list = []
for ticker, df in data_bundles.items():
    df = add_technical_indicators(df)
    df["Target"] = (df["Close"].shift(-1) > df["Close"]).astype(int)
    df["Ticker"] = ticker
    full_df_list.append(df.dropna())

all_data = pd.concat(full_df_list)
features = ["SMA20", "RSI14", "MACD"]
X = all_data[features]
y = all_data["Target"]
print(f"Total dataset size: {len(all_data)} samples")

# 3. TRAINING
print("\n--- STAGE 3: MODEL TRAINING ---")
mlflow.set_tracking_uri("sqlite:///data/mlflow.db")
mlflow.set_experiment("Quant_Research_Notebook")

with mlflow.start_run(run_name="Notebook_Research_RF"):
    model = RandomForestClassifier(n_estimators=100, max_depth=5)
    # Split
    split = int(len(all_data) * 0.8)
    model.fit(X.iloc[:split], y.iloc[:split])
    
    # 4. ANALYSIS
    print("\n--- STAGE 4: ANALYSIS ---")
    y_pred = model.predict(X.iloc[split:])
    acc = accuracy_score(y.iloc[split:], y_pred)
    prec = precision_score(y.iloc[split:], y_pred, zero_division=0)
    
    print(f"VALIDATION ACCURACY: {acc:.2%}")
    print(f"VALIDATION PRECISION: {prec:.2%}")
    
    mlflow.log_metrics({"accuracy": acc, "precision": prec})
    mlflow.sklearn.log_model(model, "alpha_model", registered_model_name="Notebook_Alpha")
    print("\n🚀 Pipeline Finished! Model registered in MLflow.")
