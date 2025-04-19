#!/usr/bin/env python3
"""
Predict script to load a pretrained LSTM model and scaler,
then forecast the next N steps for all indicators (Close, High, Low, Open,
Volume, SMA20, EMA20, RSI14, Bollinger_Upper, Bollinger_Lower,
MACD, MACD_Signal) for a given ticker and optionally plot.
Usage:
  python predict.py <TICKER> [--steps N] [--plot]
"""
import os
import glob
import argparse
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.preprocessing import MinMaxScaler
from tensorflow.keras.models import load_model

# Parameters (must match training)
DATA_FOLDER = "data"
MODEL_FILENAME = "lstm_multivar_alltickers.h5"
TIME_STEP = 50


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


def fill_and_check_columns(big_df):
    required = ["Close", "High", "Low", "Open", "Volume",
                "SMA20", "EMA20", "RSI14", "Bollinger_Upper",
                "Bollinger_Lower", "MACD", "MACD_Signal", "Ticker"]
    for c in required:
        if c not in big_df.columns:
            raise ValueError(f"Missing column {c}")
    big_df = big_df.groupby("Ticker", group_keys=False).apply(lambda x: x.ffill().bfill())
    return big_df


def fit_scaler(big_df):
    df_num = big_df.drop(columns=["Ticker"]).copy()
    feature_cols = df_num.columns.tolist()
    scaler = MinMaxScaler()
    scaler.fit(df_num.values)
    return scaler, feature_cols


def get_last_sequence(big_df, ticker, scaler):
    df = big_df[big_df["Ticker"] == ticker]
    if len(df) < TIME_STEP:
        raise ValueError(f"Not enough data for ticker {ticker}")
    df_num = df.drop(columns=["Ticker"]).copy()
    values = df_num.values
    scaled = scaler.transform(values)
    return scaled[-TIME_STEP:]


def predict_and_plot(ticker, steps, do_plot=False):
    big_df = load_all_csv(DATA_FOLDER)
    big_df = fill_and_check_columns(big_df)
    scaler, feature_cols = fit_scaler(big_df)
    model = load_model(MODEL_FILENAME)

    df_t = big_df[big_df['Ticker'] == ticker]
    if df_t.empty:
        raise ValueError(f"No data found for ticker {ticker}")

    seq = get_last_sequence(big_df, ticker, scaler)
    num_features = seq.shape[1]

    preds_norm = []
    current_seq = seq.copy()
    print(f"Generating {steps}-step predictions for {ticker}...")
    for i in range(steps):
        p = model.predict(current_seq[np.newaxis, ...], verbose=0)[0]
        preds_norm.append(p)
        print(f"Step {i+1}/{steps}: normalized preds = {p}")
        current_seq = np.vstack([current_seq[1:], p])

    preds_real = scaler.inverse_transform(np.array(preds_norm))
    last_date = df_t.index[-1]
    future_index = pd.date_range(start=last_date + pd.Timedelta(days=1), periods=steps, freq='D')
    df_preds = pd.DataFrame(preds_real, columns=feature_cols, index=future_index)

    # Print predictions
    pd.set_option('display.float_format', '{:.2f}'.format)
    print("\nPredictions (original scale):")
    print(df_preds)

    # Save predictions to data/pred/
    pred_dir = os.path.join(DATA_FOLDER, 'pred')
    os.makedirs(pred_dir, exist_ok=True)
    out_path = os.path.join(pred_dir, f"{ticker}_predictions.csv")
    df_preds.to_csv(out_path)
    print(f"Predictions saved to {out_path}")

    if do_plot:
        plt.figure(figsize=(12, 6))
        plt.plot(df_t.index, df_t['Close'], label='Hist Close')
        plt.plot(df_preds.index, df_preds['Close'], label='Pred Close', linestyle='--', marker='o')
        plt.title(f"Close Price Forecast for {ticker}")
        plt.xlabel("Date")
        plt.ylabel("Price")
        plt.legend()
        plt.grid(True)
        plt.tight_layout()
        plt.show()


def main():
    parser = argparse.ArgumentParser(
        description="Forecast next steps for all indicators using pretrained LSTM"
    )
    parser.add_argument("ticker", type=str, help="Ticker symbol (e.g. AAPL)")
    parser.add_argument("--steps", type=int, default=1, help="Number of days to predict")
    parser.add_argument("--plot", action="store_true", help="Plot predicted vs historical Close price")
    args = parser.parse_args()

    predict_and_plot(args.ticker.upper(), args.steps, do_plot=args.plot)

if __name__ == "__main__":
    main()
