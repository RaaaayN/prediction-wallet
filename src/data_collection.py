#!.venv\Scripts\python.exe
"""
Ce script permet de collecter des données financières via l'API Yahoo Finance en utilisant la bibliothèque yfinance.
Il récupère l'historique des prix journaliers pour un actif donné (action/ETF/Crypto), sauvegarde les données dans un fichier CSV,
les enregistre dans une base de données SQLite et ajoute un indicateur technique (Moyenne Mobile Simple sur 20 jours).
Le ticker et éventuellement les dates de début et de fin peuvent être précisés en argument.
"""

import argparse
import os
import yfinance as yf
import pandas as pd
import sqlite3

def collect_financial_data(ticker, start_date, end_date):
    """
    Récupère les données historiques d'un ticker spécifié entre deux dates.
    
    :param ticker: Le symbole boursier (ex : "AAPL", "BTC-USD")
    :param start_date: Date de début au format "YYYY-MM-DD"
    :param end_date: Date de fin au format "YYYY-MM-DD"
    :return: Un DataFrame contenant les données historiques
    """
    print(f"Récupération des données pour {ticker} de {start_date} à {end_date}...")
    data = yf.download(ticker, start=start_date, end=end_date, interval='1d')
    if data.empty:
        print("Aucune donnée récupérée. Vérifiez le ticker et les dates.")
    else:
        print("Données récupérées avec succès !")
    return data

def save_to_csv(data, filename):
    """
    Sauvegarde un DataFrame dans un fichier CSV.
    
    :param data: Le DataFrame contenant les données financières.
    :param filename: Nom du fichier CSV de destination.
    """
    # Vérifie que le répertoire existe, sinon le crée
    directory = os.path.dirname(filename)
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)
        print(f"Le répertoire '{directory}' a été créé.")
    data.to_csv(filename)
    print(f"Données sauvegardées dans le fichier CSV : {filename}")

def save_to_sqlite(data, db_filename, table_name):
    """
    Sauvegarde un DataFrame dans une table d'une base de données SQLite.
    
    :param data: Le DataFrame contenant les données financières.
    :param db_filename: Nom du fichier de la base de données SQLite.
    :param table_name: Nom de la table dans laquelle insérer les données.
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
    
    :param data: Le DataFrame original avec la colonne 'Close'.
    :return: Le DataFrame enrichi avec les indicateurs techniques.
    """

    # Moyenne Mobile Simple sur 20 jours
    data['SMA20'] = data['Close'].rolling(window=20).mean()

    # Moyenne Mobile Exponentielle sur 20 jours
    data['EMA20'] = data['Close'].ewm(span=20, adjust=False).mean()

    # Calcul du RSI sur 14 jours
    delta = data['Close'].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=14).mean()
    avg_loss = loss.rolling(window=14).mean()
    rs = avg_gain / avg_loss
    data['RSI14'] = 100 - (100 / (1 + rs))

    # Calcul des Bollinger Bands sur 20 jours (SMA20 ± 2 écart-types)
    rolling_std = data['Close'].rolling(window=20).std()
    data['Bollinger_Upper'] = data['SMA20'] + 2 * rolling_std
    data['Bollinger_Lower'] = data['SMA20'] - 2 * rolling_std

    # Calcul du MACD
    # 12-EMA et 26-EMA
    ema12 = data['Close'].ewm(span=12, adjust=False).mean()
    ema26 = data['Close'].ewm(span=26, adjust=False).mean()
    data['MACD'] = ema12 - ema26

    # Ligne de signal MACD (9 jours EMA du MACD)
    data['MACD_Signal'] = data['MACD'].ewm(span=9, adjust=False).mean()

    print("Indicateurs techniques ajoutés aux données : SMA20, EMA20, RSI14, Bollinger Bands, MACD et MACD_Signal.")
    return data


def main():
    # Définition des arguments en ligne de commande
    parser = argparse.ArgumentParser(
        description="Collecte des données financières pour un actif donné (action, ETF ou crypto)."
    )
    parser.add_argument("ticker", type=str, help="Le symbole de l'actif (ex: AAPL, BTC-USD)")
    parser.add_argument("--start", type=str, default="2018-01-01", help="Date de début (format YYYY-MM-DD)")
    parser.add_argument("--end", type=str, default="2023-01-01", help="Date de fin (format YYYY-MM-DD)")
    
    args = parser.parse_args()
    
    ticker = args.ticker
    start_date = args.start
    end_date = args.end
    
    # 1. Récupérer les données
    data = collect_financial_data(ticker, start_date, end_date)
    
    if data.empty:
        return  # Arrête le script en cas d'échec de récupération
    
    # 2. Sauvegarder les données brutes en CSV dans le dossier ../data/
    csv_filename = f"data/brut/{ticker}_data_brut.csv"
    save_to_csv(data, csv_filename)
    
    # 3. Sauvegarder les données dans une base SQLite
    db_filename = "financial_data.db"
    save_to_sqlite(data, db_filename, ticker)
    
    # 4. Ajouter un indicateur technique (Moyenne Mobile sur 20 jours)
    data_with_indicators = add_technical_indicators(data)
    
    # 5. Sauvegarder les données enrichies avec indicateurs en CSV dans le dossier ../data/
    csv_with_indicators = f"data/{ticker}_data.csv"
    save_to_csv(data_with_indicators, csv_with_indicators)

if __name__ == "__main__":
    main()
