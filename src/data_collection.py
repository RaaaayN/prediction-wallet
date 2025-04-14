#!.venv\Scripts\python.exe
"""
Ce script permet de collecter des données financières via l'API Yahoo Finance pour
les 50 plus grandes actions (ou toute autre liste de tickers). 
Pour chaque ticker, le script :
  - Télécharge l'historique des prix journaliers entre une date de début et une date de fin.
  - Sauvegarde les données brutes dans un fichier CSV.
  - Enregistre les données dans une base de données SQLite.
  - Ajoute plusieurs indicateurs techniques (SMA20, EMA20, RSI14, Bollinger Bands, MACD et MACD_Signal),
    puis sauvegarde les données enrichies dans un autre fichier CSV.
Le ticker et la période sont définis dans le script (modifiable).
"""

import argparse
import os
import yfinance as yf
import pandas as pd
import sqlite3
import time

# --- Fonctions existantes ---

def collect_financial_data(ticker, start_date, end_date):
    """
    Récupère les données historiques d'un ticker spécifié entre deux dates.
    :param ticker: Le symbole boursier (ex : "AAPL", "BTC-USD")
    :param start_date: Date de début (format "YYYY-MM-DD")
    :param end_date: Date de fin (format "YYYY-MM-DD")
    :return: Un DataFrame contenant les données historiques
    """
    print(f"\nRécupération des données pour {ticker} de {start_date} à {end_date} ...")
    data = yf.download(ticker, start=start_date, end=end_date, interval='1d')
    if data.empty:
        print(f"Aucune donnée récupérée pour {ticker}. Vérifiez le ticker ou les dates.")
    else:
        print(f"Données pour {ticker} récupérées avec succès !")
    return data

def save_to_csv(data, filename):
    """
    Sauvegarde un DataFrame dans un fichier CSV.
    :param data: Le DataFrame contenant les données.
    :param filename: Nom du fichier CSV de destination.
    """
    directory = os.path.dirname(filename)
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)
        print(f"Le répertoire '{directory}' a été créé.")
    data.to_csv(filename)
    print(f"Données sauvegardées dans le fichier CSV : {filename}")

def save_to_sqlite(data, db_filename, table_name):
    """
    Sauvegarde un DataFrame dans une table d'une base de données SQLite.
    :param data: Le DataFrame.
    :param db_filename: Nom du fichier de la base SQLite.
    :param table_name: Nom de la table pour insérer les données.
    """
    conn = sqlite3.connect(db_filename)
    data.to_sql(table_name, conn, if_exists='replace', index=True)
    conn.close()
    print(f"Données sauvegardées dans la base SQLite : {db_filename}, table : {table_name}")

def add_technical_indicators(data):
    """
    Ajoute plusieurs indicateurs techniques aux données financières.
    Les indicateurs ajoutés sont :
      - SMA20 : Moyenne Mobile Simple sur 20 jours.
      - EMA20 : Moyenne Mobile Exponentielle sur 20 jours.
      - RSI14 : Relative Strength Index sur 14 jours.
      - Bollinger Bands : Bande supérieure et inférieure sur 20 jours (SMA20 ± 2 sigma).
      - MACD et MACD_Signal : MACD (12-EMA moins 26-EMA) et ligne de signal (9 jours EMA du MACD).
    :param data: Le DataFrame contenant au moins la colonne 'Close'.
    :return: Le DataFrame enrichi.
    """
    # Aplatir les colonnes si MultiIndex
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    
    data['SMA20'] = data['Close'].rolling(window=20).mean()
    data['EMA20'] = data['Close'].ewm(span=20, adjust=False).mean()
    
    # Calcul du RSI sur 14 jours
    delta = data['Close'].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=14).mean()
    avg_loss = loss.rolling(window=14).mean()
    rs = avg_gain / avg_loss
    data['RSI14'] = 100 - (100 / (1 + rs))
    
    # Bollinger Bands sur 20 jours
    rolling_std = data['Close'].rolling(window=20).std()
    data.loc[:, 'Bollinger_Upper'] = data['SMA20'] + 2 * rolling_std
    data.loc[:, 'Bollinger_Lower'] = data['SMA20'] - 2 * rolling_std
    
    # MACD
    ema12 = data['Close'].ewm(span=12, adjust=False).mean()
    ema26 = data['Close'].ewm(span=26, adjust=False).mean()
    data['MACD'] = ema12 - ema26
    data['MACD_Signal'] = data['MACD'].ewm(span=9, adjust=False).mean()
    
    print("Indicateurs techniques ajoutés aux données pour", data.index.name if data.index.name else "l'actif")
    return data

# --- Script Principal ---
def main():
    # Définition des dates de début et de fin (modifiables)
    start_date = "2018-01-01"
    end_date = "2025-01-01"
    
    # Liste des 50 tickers (les plus grandes actions, ici exemple pour des actions US)
    tickers = [
        "AAPL", "MSFT", "AMZN", "GOOGL", "META", "TSLA", "BRK-B", "NVDA", "JPM", "JNJ",
        "V", "UNH", "HD", "PG", "MA", "DIS", "BAC", "VZ", "ADBE", "NFLX",
        "CMCSA", "XOM", "KO", "PFE", "MRK", "PEP", "T", "ABT", "ORCL", "NKE",
        "CRM", "LLY", "WMT", "MCD", "INTC", "CVX", "ACN", "HON", "IBM", "QCOM",
        "TMO", "MDT", "COST", "NEE", "LIN", "UPS", "PM", "SBUX", "LOW", "BLK"
    ]
    
    # Nom de la base de données pour stocker tous les tickers
    db_filename = "financial_data.db"
    
    # Parcourir tous les tickers et traiter chacun d'eux
    for ticker in tickers:
        print("\n============================")
        print(f"Traitement de : {ticker}")
        
        # Télécharger les données
        df = collect_financial_data(ticker, start_date, end_date)
        if df.empty:
            print(f"Pas de données pour {ticker}, passage au suivant.")
            continue
        
        # Sauvegarder les données brutes dans data/brut/
        csv_brut = f"data/brut/{ticker}_data_brut.csv"
        save_to_csv(df, csv_brut)
        
        # Sauvegarder les données dans la base SQLite (chaque ticker dans sa propre table)
        save_to_sqlite(df, db_filename, ticker)
        
        # Ajouter les indicateurs techniques aux données
        df_ind = add_technical_indicators(df)
        
        # Sauvegarder les données enrichies dans data/
        csv_enriched = f"data/{ticker}_data.csv"
        save_to_csv(df_ind, csv_enriched)
        
        # Pause pour éviter d'éventuelles restrictions (optionnel)
        time.sleep(1)

if __name__ == "__main__":
    main()
