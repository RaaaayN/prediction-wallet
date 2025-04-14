#!.venv\Scripts\python.exe
"""
Script pour entraîner un modèle LSTM multivarié avec toutes les données de multiples CSV.
Chaque CSV contient les colonnes suivantes :
  Date, Close, High, Low, Open, Volume, SMA20, EMA20, RSI14, 
  Bollinger_Upper, Bollinger_Lower, MACD, MACD_Signal.
Les indicateurs sont ainsi pris en compte.
On entraîne un seul modèle sur les données concaténées de tous les tickers.
Ensuite, on effectue une prévision itérative jusqu'au 31 décembre 2026.
"""

import os
import glob
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import tensorflow as tf
from tensorflow.keras.models import Sequential, load_model
from tensorflow.keras.layers import LSTM, Dense
from sklearn.preprocessing import MinMaxScaler
from tqdm import tqdm

# ----------------------------
# Paramètres utilisateur
DATA_FOLDER = "data"  # Répertoire contenant les CSV (ex: AAPL_data.csv, ABT_data.csv, etc.)
MODEL_FILENAME = "lstm_multivar_alltickers.h5"
TIME_STEP = 50
BATCH_SIZE = 64
EPOCHS = 10
TARGET_DATE = "2026-12-31"
# ----------------------------

def load_all_csv(data_folder):
    """
    Charge et concatène tous les CSV du dossier data_folder dont le nom se termine par '_data.csv'.
    Chaque CSV doit contenir les colonnes obligatoires (Close, High, Low, etc.).
    On ajoute une colonne Ticker extraite du nom du fichier pour information.
    Retourne un DataFrame global contenant toutes les données.
    """
    all_files = glob.glob(os.path.join(data_folder, "*_data.csv"))
    df_list = []

    for filepath in all_files:
        # Extraire le ticker du nom du fichier, ex: "AAPL_data.csv" -> "AAPL"
        filename = os.path.basename(filepath)
        ticker = filename.split("_data.csv")[0]

        df = pd.read_csv(filepath, parse_dates=["Date"], index_col="Date")
        df["Ticker"] = ticker  # Ajout d'une colonne Ticker
        df_list.append(df)

    if not df_list:
        raise FileNotFoundError(f"Aucun fichier CSV trouvé dans le dossier {data_folder}")

    # Concaténer verticalement toutes les DataFrames
    # On n'aligne pas sur l'index temporel, car chaque ticker a ses propres dates
    big_df = pd.concat(df_list, axis=0)
    # Tri par ticker puis par Date pour s'assurer d'un ordre temporel cohérent
    big_df.sort_values(by=["Ticker", "Date"], inplace=True)
    return big_df

def fill_and_check_columns(big_df):
    """
    Vérifie les colonnes minimales attendues.
    Remplit les valeurs manquantes si besoin.
    """
    required_cols = [
        "Close", "High", "Low", "Open", "Volume", 
        "SMA20", "EMA20", "RSI14", "Bollinger_Upper", 
        "Bollinger_Lower", "MACD", "MACD_Signal", "Ticker"
    ]
    for col in required_cols:
        if col not in big_df.columns:
            raise ValueError(f"La colonne {col} est manquante dans les CSV.")

    # Remplissage des NaN éventuels
    big_df = big_df.groupby("Ticker").apply(lambda x: x.fillna(method='ffill').fillna(method='bfill'))
    # On enlève le niveau supplémentaire ajouté par groupby.apply
    big_df.reset_index(level=0, drop=True, inplace=True)

    return big_df

def create_sequences_for_all_tickers(big_df, time_step=50):
    """
    Pour chaque ticker, on crée des séquences temporelles multivariées de longueur `time_step`.
    Les features utilisées sont toutes les colonnes numériques sauf "Ticker".
    La cible (y) correspond à la valeur normalisée de "Close" (qui est supposée être la première colonne après suppression de "Ticker").
    On retourne X, y, ainsi que le scaler global sur toutes les features et un scaler pour la cible.
    """

    # Vérifier que la colonne "Ticker" existe
    if "Ticker" not in big_df.columns:
        raise ValueError("La colonne 'Ticker' est absente du DataFrame.")

    # Conserver une copie des données numériques en excluant la colonne Ticker pour le scaling global
    df_numeric = big_df.drop(columns=["Ticker"])
    # Liste des features en conservant l'ordre des colonnes tel quel
    final_cols = df_numeric.columns.tolist()
    print("Colonnes finales pour l'entraînement :", final_cols)

    # Créer et fitter les scalers sur l'ensemble des données de tous les tickers
    scaler_global = MinMaxScaler(feature_range=(0, 1))
    all_features = df_numeric.values  # toutes les colonnes
    scaler_global.fit(all_features)

    target_scaler = MinMaxScaler(feature_range=(0, 1))
    # On suppose que la première colonne de df_numeric est "Close"
    all_close = df_numeric.iloc[:, 0].values.reshape(-1, 1)
    target_scaler.fit(all_close)

    X_list, y_list = [], []

    # Grouper par ticker en utilisant la colonne "Ticker"
    for ticker, group_df in big_df.groupby("Ticker"):
        # Pour ce ticker, on retire la colonne "Ticker" avant de créer les séquences
        group_df_numeric = group_df.drop(columns=["Ticker"])
        group_values = group_df_numeric.values  # shape (n_samples, num_features)
        
        # Normaliser les données de ce ticker avec le scaler_global déjà ajusté
        group_scaled = scaler_global.transform(group_values)

        # Créer des séquences pour ce ticker
        for i in range(len(group_scaled) - time_step):
            X_seq = group_scaled[i : i + time_step, :]   # séquence multivariée, shape (time_step, num_features)
            y_val = group_scaled[i + time_step, 0]         # cible : colonne "Close"
            X_list.append(X_seq)
            y_list.append(y_val)

    X = np.array(X_list)
    y = np.array(y_list)
    print(f"Nombre total de séquences = {len(X_list)}")
    return X, y, scaler_global, target_scaler, final_cols



# ---------- Script Principal ----------
def main():
    # 1) Charger et concaténer tous les CSV
    big_df = load_all_csv(DATA_FOLDER)
    print(f"Nombre total de lignes après concaténation : {len(big_df)}")

    # 2) Vérifier et remplir les colonnes manquantes
    big_df = fill_and_check_columns(big_df)

    # 3) Créer les séquences multivariées pour tous les tickers
    X, y, scaler_global, target_scaler, final_cols = create_sequences_for_all_tickers(big_df, time_step=TIME_STEP)
    print("Forme de X :", X.shape, "Forme de y :", y.shape)

    # Création du Dataset tf.data
    dataset_tf = tf.data.Dataset.from_tensor_slices((X, y))
    dataset_tf = dataset_tf.shuffle(buffer_size=10000).batch(BATCH_SIZE).prefetch(tf.data.AUTOTUNE)

    num_features = X.shape[2]

    # 4) Charger ou entraîner le modèle LSTM
    if os.path.exists(MODEL_FILENAME):
        print("Chargement du modèle sauvegardé depuis", MODEL_FILENAME)
        model = load_model(MODEL_FILENAME)
    else:
        print("Aucun modèle sauvegardé trouvé. Entraînement du modèle...")
        model = Sequential([
            LSTM(50, return_sequences=True, input_shape=(TIME_STEP, num_features)),
            LSTM(50, return_sequences=False),
            Dense(25),
            Dense(1)
        ])
        model.compile(optimizer='adam', loss='mean_squared_error')
        model.fit(dataset_tf, epochs=EPOCHS)
        model.save(MODEL_FILENAME)
        print("Modèle sauvegardé dans", MODEL_FILENAME)

    # 5) Prévision in-sample (on compare la prédiction sur le dataset d'entraînement)
    #    On prédit sur X en l'état (toutes les séquences)
    y_pred_norm = model.predict(X, verbose=0)  # forme (nb_sequences, 1)
    y_pred = target_scaler.inverse_transform(y_pred_norm)    # shape (nb_sequences, 1)

    #  Pour tracer la courbe in-sample, on va se concentrer sur un ticker, 
    #  ou afficher un ticker en particulier, ou un segment du dataset.
    #  Ici, on ne fait qu'un plot global pour illustration.
    #  -> Optionnel : vous pouvez sélectionner un ticker particulier et retracer 
    #     la série "Close" et la prédiction correspondante.

    plt.figure(figsize=(10,5))
    plt.title("Prévision in-sample (tous tickers confondus)")
    plt.plot(y_pred, label='Prévision LSTM (in-sample)', color='red')
    plt.legend()
    plt.show()

    # 6) Prévision itérative jusqu'au 31/12/2026 (hypothèse simplifiée)
    #    Il faut faire une boucle par ticker pour générer des prévisions futures.
    #    Chaque ticker aura sa séquence finale mise à jour itérativement.
    
    # On se base sur la dernière séquence du dataset pour chaque ticker.
    # L'hypothèse : on ne modifie que la colonne "Close" (col index=0) 
    # pour la prédiction future. Les autres colonnes (indicateurs) 
    # restent celles de la dernière observation, ce qui est simpliste.
    
    last_date_global = big_df.groupby("Ticker").apply(lambda df: df.index[-1])
    
    # Dictionnaire pour stocker DataFrame de prévisions par ticker
    forecast_dict = {}

    for ticker, group_df in big_df.groupby("Ticker"):
        # Récupérer la dernière séquence scaled
        group_values = group_df.values
        group_scaled = scaler_global.transform(group_values)
        
        # La dernière séquence
        if len(group_scaled) < TIME_STEP:
            # Pas assez de données pour faire une séquence
            continue
        last_seq = group_scaled[-TIME_STEP:]  # shape (time_step, num_features)
        
        # Dates futures (business days)
        last_date = group_df.index[-1]
        future_dates = pd.bdate_range(start=last_date + pd.Timedelta(days=1), end=TARGET_DATE)
        n_future = len(future_dates)
        if n_future == 0:
            continue
        print(f"\nTicker: {ticker}, last date = {last_date}, nb futurs = {n_future}")

        current_seq = last_seq.copy()
        forecast_list = []
        for _ in tqdm(range(n_future), desc=f"Prévisions {ticker}"):
            pred = model.predict(current_seq.reshape(1, TIME_STEP, num_features), verbose=0)
            forecast_value = pred[0, 0]  # normalisé
            # Mettre à jour la séquence
            new_row = current_seq[-1].copy()
            new_row[0] = forecast_value  # On met à jour "Close"
            current_seq = np.append(current_seq[1:], [new_row], axis=0)
            forecast_list.append(forecast_value)
        
        forecast_list = np.array(forecast_list).reshape(-1,1)
        forecast_original = target_scaler.inverse_transform(forecast_list)
        df_fc = pd.DataFrame(forecast_original, index=future_dates, columns=["Forecast"])
        forecast_dict[ticker] = df_fc

    # 7) Affichage d'un ticker en particulier
    #    Par exemple, on affiche AAPL
    TICKER_TO_PLOT = "AAPL"
    if TICKER_TO_PLOT in forecast_dict:
        fc_df = forecast_dict[TICKER_TO_PLOT]
        # On trace l'historique "Close" + la prévision
        ticker_data = big_df[big_df["Ticker"] == TICKER_TO_PLOT]
        plt.figure(figsize=(12,6))
        plt.plot(ticker_data.index, ticker_data["Close"], label=f"Historique {TICKER_TO_PLOT}")
        plt.plot(fc_df.index, fc_df["Forecast"], label=f"Prévisions {TICKER_TO_PLOT}", color="red")
        plt.title(f"Prévisions LSTM multivariées jusqu'au {TARGET_DATE} pour {TICKER_TO_PLOT}")
        plt.xlabel("Date")
        plt.ylabel("Prix de clôture")
        plt.legend()
        plt.tight_layout()
        plt.show()
    else:
        print(f"Aucune prévision disponible pour {TICKER_TO_PLOT}")

if __name__ == "__main__":
    main()
