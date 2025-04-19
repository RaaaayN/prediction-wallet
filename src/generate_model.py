#!/usr/bin/env python3
"""
Script pour entraîner un modèle LSTM multivarié sur plusieurs tickers,
prédire le cours ainsi que tous les indicateurs.
"""
import os
import glob
import pandas as pd
import numpy as np
import tensorflow as tf
from tensorflow.keras.models import Sequential, load_model
from tensorflow.keras.layers import LSTM, Dense
from sklearn.preprocessing import MinMaxScaler

# Paramètres utilisateur
data_folder = "data"  # répertoire des CSV nommés *_data.csv
model_filename = "lstm_multivar_alltickers.h5"
time_step = 50
batch_size = 64
epochs = 10
target_date = "2026-12-31"


def load_all_csv(data_folder):
    """
    Charge et concatène tous les CSV du dossier data_folder.
    Chaque fichier *_data.csv doit contenir les colonnes:
    Date, Close, High, Low, Open, Volume, SMA20, EMA20, RSI14,
    Bollinger_Upper, Bollinger_Lower, MACD, MACD_Signal.
    Retourne un DataFrame global trié par Ticker et Date.
    """
    paths = glob.glob(os.path.join(data_folder, "*_data.csv"))
    if not paths:
        raise FileNotFoundError(f"Aucun fichier CSV trouvé dans {data_folder}")

    dfs = []
    for p in paths:
        ticker = os.path.basename(p).split("_data.csv")[0]
        df = pd.read_csv(p, parse_dates=["Date"], index_col="Date")
        df["Ticker"] = ticker
        dfs.append(df)

    big_df = pd.concat(dfs, axis=0)
    big_df.sort_values(by=["Ticker", "Date"], inplace=True)
    return big_df


def fill_and_check_columns(big_df):
    """
    Vérifie la présence de toutes les colonnes, puis remplit les NaN par forward/backfill.
    """
    required = ["Close","High","Low","Open","Volume",
                "SMA20","EMA20","RSI14","Bollinger_Upper",
                "Bollinger_Lower","MACD","MACD_Signal","Ticker"]
    for col in required:
        if col not in big_df.columns:
            raise ValueError(f"Colonne manquante: {col}")

    # forward then backward fill par ticker
    big_df = big_df.groupby("Ticker", group_keys=False).apply(lambda x: x.ffill().bfill())
    return big_df


def create_sequences_for_all_tickers(big_df, time_step=50):
    """
    Crée X (séquences multivariées) et y (vecteurs multivariés) pour tous les tickers.
    Retourne X, y, le scaler global, et la liste des noms de features.
    """
    df_num = big_df.drop(columns=["Ticker"])
    feature_names = df_num.columns.tolist()

    scaler = MinMaxScaler((0,1))
    scaler.fit(df_num.values)

    X_list, y_list = [], []
    for _, grp in big_df.groupby("Ticker"):
        vals = scaler.transform(grp.drop(columns=["Ticker"]).values)
        for i in range(len(vals) - time_step):
            X_list.append(vals[i:i+time_step])
            y_list.append(vals[i+time_step])

    X = np.array(X_list)  # (n_samples, time_step, n_features)
    y = np.array(y_list)  # (n_samples, n_features)
    return X, y, scaler, feature_names


def build_multivar_model(num_features):
    """
    Construit un LSTM multivarié dont la couche de sortie est Dense(num_features).
    """
    model = Sequential([
        LSTM(50, return_sequences=True, input_shape=(time_step, num_features)),
        LSTM(50, return_sequences=False),
        Dense(25),
        Dense(num_features)
    ])
    model.compile(optimizer='adam', loss='mean_squared_error')
    return model


def main():
    # 1) Chargement et pré-traitement
    big_df = load_all_csv(data_folder)
    big_df = fill_and_check_columns(big_df)

    # 2) Création des séquences
    X, y, scaler_global, feature_names = create_sequences_for_all_tickers(big_df, time_step)
    num_features = X.shape[2]

    # 3) Préparation du dataset TensorFlow
    dataset = tf.data.Dataset.from_tensor_slices((X, y)) \
                 .shuffle(buffer_size=10000) \
                 .batch(batch_size) \
                 .prefetch(tf.data.AUTOTUNE)

    # 4) Chargement ou réentraînement du modèle
    retrain = True
    if os.path.exists(model_filename):
        model = load_model(model_filename)
        if model.output_shape[-1] == num_features:
            retrain = False
            print("Modèle existant chargé (sorties multivariées).")
        else:
            print(f"Ancien modèle à {model.output_shape[-1]} sorties supprimé (attendu {num_features}).")
            os.remove(model_filename)

    if retrain:
        model = build_multivar_model(num_features)
        model.fit(dataset, epochs=epochs)
        model.save(model_filename)
        print("Nouveau modèle entraîné et sauvegardé.")

    # 5) Prévision itérative jusqu'à target_date
    last_date = big_df.index.max()
    target_steps = (pd.to_datetime(target_date) - last_date).days
    current_seq = X[-1].copy()
    preds = []

    for _ in range(target_steps):
        p = model.predict(current_seq[np.newaxis, ...])[0]  # (n_features,)
        preds.append(p)
        current_seq = np.vstack([current_seq[1:], p])     # glissement de fenêtre

    # 6) Inversion de l'échelle et création du DataFrame de prédictions
    preds_real = scaler_global.inverse_transform(np.array(preds))
    index = pd.date_range(start=last_date + pd.Timedelta(days=1), periods=target_steps, freq='D')
    df_preds = pd.DataFrame(preds_real, columns=feature_names, index=index)

    print(df_preds.head())

if __name__ == "__main__":
    main()
