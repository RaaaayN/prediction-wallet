#!/usr/bin/env python3
"""
Predict script to load a pretrained LSTM model and scalers,
then forecast the next closing price for a given ticker and optionally plot it.
Usage:
  python predict.py <TICKER> [--steps N] [--plot]

It expects:
 - The trained model file (lstm_multivar_alltickers.h5) in the working directory.
 - CSV files for each ticker under the `data` folder named `<TICKER>_data.csv` (enriched with indicators).

This script:
 1. Loads all enriched CSVs to refit the scalers.
 2. Loads the pretrained LSTM model.
 3. Extracts the last TIME_STEP observations for the given ticker.
 4. Iteratively predicts the next N closing prices.
 5. Prints and, if requested, plots historical vs predicted prices on the same curve.
"""
import os
import glob
import argparse
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.preprocessing import MinMaxScaler
from tensorflow.keras.models import load_model

# Parameters (should match training)
DATA_FOLDER = "data"
MODEL_FILENAME = "lstm_multivar_alltickers.h5"
TIME_STEP = 50

# Load all enriched CSVs to refit scalers
def load_all_csv(data_folder):
    all_files = glob.glob(os.path.join(data_folder, "*_data.csv"))
    df_list = []
    for filepath in all_files:
        ticker = os.path.basename(filepath).split("_data.csv")[0]
        df = pd.read_csv(filepath, parse_dates=["Date"], index_col="Date")
        df["Ticker"] = ticker
        df_list.append(df)
    if not df_list:
        raise FileNotFoundError(f"No CSV files found in {data_folder}")
    big_df = pd.concat(df_list)
    big_df.sort_values(by=["Ticker", "Date"], inplace=True)
    return big_df

# Fill missing and ensure columns
def fill_and_check_columns(big_df):
    required = ["Close","High","Low","Open","Volume",
                "SMA20","EMA20","RSI14","Bollinger_Upper",
                "Bollinger_Lower","MACD","MACD_Signal","Ticker"]
    for c in required:
        if c not in big_df.columns:
            raise ValueError(f"Missing column {c}")
    big_df = big_df.groupby("Ticker").apply(lambda x: x.ffill().bfill())
    big_df.reset_index(level=0, drop=True, inplace=True)
    return big_df

# Refit scalers on all numeric data
def fit_scalers(big_df):
    df_num = big_df.drop(columns=["Ticker"]).copy()
    cols = df_num.columns.tolist()
    cols.remove("Close")
    df_num = df_num[["Close"] + cols]
    scaler_global = MinMaxScaler()
    scaler_global.fit(df_num.values)
    target_scaler = MinMaxScaler()
    target_scaler.fit(df_num[["Close"]].values)
    return scaler_global, target_scaler, df_num.columns.tolist()

# Extract last TIME_STEP sequence for a ticker
def get_last_sequence(big_df, ticker, scaler_global):
    df = big_df[big_df["Ticker"] == ticker]
    if len(df) < TIME_STEP:
        raise ValueError(f"Not enough data for ticker {ticker}")
    df_num = df.drop(columns=["Ticker"]).copy()
    cols = df_num.columns.tolist()
    cols.remove("Close")
    df_num = df_num[["Close"] + cols]
    values = df_num.values
    scaled = scaler_global.transform(values)
    return scaled[-TIME_STEP:]

# Predict and optionally plot
def predict_and_plot(ticker, steps, do_plot=False):
    big_df = load_all_csv(DATA_FOLDER)
    big_df = fill_and_check_columns(big_df)
    scaler_global, target_scaler, feature_cols = fit_scalers(big_df)
    model = load_model(MODEL_FILENAME)

    # Historical data
    df_ticker = big_df[big_df['Ticker'] == ticker]
    if df_ticker.empty:
        raise ValueError(f"No data found for ticker {ticker}")
    hist_close = df_ticker['Close']

        # Generate predictions
    seq = get_last_sequence(big_df, ticker, scaler_global)
    num_features = seq.shape[1]
    preds_norm = []
    current_seq = seq.copy()
    print(f"Generating {steps} predictions for {ticker}...")
    for i in range(steps):
        p = model.predict(current_seq.reshape(1, TIME_STEP, num_features), verbose=0)[0,0]
        preds_norm.append(p)
        print(f"Step {i+1}/{steps}: normalized prediction = {p:.6f}")
        new_row = current_seq[-1].copy()
        new_row[0] = p
        current_seq = np.vstack([current_seq[1:], new_row])

    preds = target_scaler.inverse_transform(np.array(preds_norm).reshape(-1,1)).flatten()

    # Print final predictions in original scale
    for i, val in enumerate(preds, 1):
        print(f"Day+{i}: {val:.2f}")

    for i, val in enumerate(preds, 1):
        print(f"Day+{i}: {val:.2f}")

    # Plot historical and predicted if flag set
    if do_plot:
        future_dates = pd.bdate_range(start=hist_close.index[-1] + pd.Timedelta(days=1),
                                      periods=steps)
        plt.figure(figsize=(12,6))
        plt.plot(hist_close.index, hist_close.values, label='Historical Close', color='blue')
        plt.plot(future_dates, preds, label='Predicted Close', color='red', marker='o')
        plt.title(f"Historical and Predicted Close Prices for {ticker}")
        plt.xlabel("Date")
        plt.ylabel("Price")
        plt.legend()
        plt.grid(True)
        plt.tight_layout()
        plt.show()

# CLI
def main():
    parser = argparse.ArgumentParser(
        description="Forecast next closing prices using pretrained LSTM model"
    )
    parser.add_argument("ticker", type=str, help="Ticker symbol (e.g. AAPL)")
    parser.add_argument("--steps", type=int, default=1, help="Number of days to predict")
    parser.add_argument("--plot", action="store_true",
                        help="Plot historical and predicted closing prices")
    args = parser.parse_args()
    predict_and_plot(args.ticker.upper(), args.steps, do_plot=args.plot)

if __name__ == "__main__":
    main()
