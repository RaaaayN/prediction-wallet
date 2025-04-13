#!.venv\Scripts\python.exe
"""
Ce script effectue le prétraitement et l'analyse exploratoire (EDA) des données financières.
Il nettoie les données (valeurs manquantes, outliers, format des dates), puis visualise :
- La courbe des prix de clôture.
- Les rendements journaliers.
- La volatilité sur 20 jours.
Il propose également de créer une heatmap de corrélation si plusieurs actifs sont disponibles.
"""

import os
import glob
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

def load_csv(filepath):
    """
    Charge un fichier CSV en s'assurant de parser l'index comme dates.
    """
    data = pd.read_csv(filepath, parse_dates=True, index_col=0)
    # Convertir l'index en datetime si ce n'est pas déjà le cas
    data.index = pd.to_datetime(data.index)
    return data

def clean_data(data):
    """
    Nettoie les données :
      - Remplit les valeurs manquantes en utilisant forward fill puis backward fill.
      - Supprime les outliers dans la colonne 'Close' en ne conservant que les valeurs comprises
        entre le 1er et le 99ème percentile.
    """
    # Remplir les valeurs manquantes
    data_clean = data.fillna(method='ffill').fillna(method='bfill')
    
    # Filtrer les outliers sur la colonne 'Close'
    lower_bound = data_clean['Close'].quantile(0.01)
    upper_bound = data_clean['Close'].quantile(0.99)
    data_clean = data_clean[(data_clean['Close'] >= lower_bound) & (data_clean['Close'] <= upper_bound)]
    
    return data_clean

def plot_price_curve(data, ticker):
    """
    Trace la courbe des prix de clôture pour un actif donné.
    """
    plt.figure(figsize=(12, 6))
    plt.plot(data.index, data['Close'], label=f'{ticker} Close Price')
    plt.xlabel("Date")
    plt.ylabel("Prix de clôture")
    plt.title(f"Courbe des prix de clôture pour {ticker}")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()

def calculate_daily_returns(data):
    """
    Calcule les rendements journaliers à partir des cours de clôture.
    """
    returns = data['Close'].pct_change().dropna()
    return returns

def plot_daily_returns(returns, ticker):
    """
    Affiche la courbe des rendements journaliers.
    """
    plt.figure(figsize=(12, 6))
    plt.plot(returns.index, returns, label=f'{ticker} Rendements Quotidiens')
    plt.xlabel("Date")
    plt.ylabel("Rendement journalier")
    plt.title(f"Rendements journaliers pour {ticker}")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()

def plot_volatility(returns, ticker):
    """
    Calcule la volatilité (écart-type des rendements sur une fenêtre glissante de 20 jours) et la trace.
    """
    volatility = returns.rolling(window=20).std()
    plt.figure(figsize=(12, 6))
    plt.plot(volatility.index, volatility, label=f'{ticker} Volatilité (20 jours)')
    plt.xlabel("Date")
    plt.ylabel("Volatilité")
    plt.title(f"Volatilité sur 20 jours pour {ticker}")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()

def plot_correlation_heatmap(data_dict):
    """
    Combine les colonnes 'Close' de plusieurs actifs pour calculer leurs rendements journaliers,
    puis trace une heatmap de la matrice de corrélation.
    
    data_dict : dictionnaire où la clé est le ticker et la valeur est le DataFrame correspondant.
    """
    merged_data = pd.DataFrame()
    for ticker, df in data_dict.items():
        merged_data[ticker] = df['Close']
    
    # Calculer les rendements journaliers
    returns = merged_data.pct_change().dropna()
    
    # Calcul de la matrice de corrélation
    corr = returns.corr()
    
    plt.figure(figsize=(8, 6))
    sns.heatmap(corr, annot=True, cmap='coolwarm', fmt=".2f")
    plt.title("Matrice de corrélation des rendements quotidiens")
    plt.tight_layout()
    plt.show()

def main():
    # Exemple de traitement pour un seul actif : AAPL
    ticker = "AAPL"
    filepath = f"data/{ticker}_data.csv"
    
    # Charger et nettoyer les données
    data = load_csv(filepath)
    data_clean = clean_data(data)
    
    # Visualisation des prix
    plot_price_curve(data_clean, ticker)
    
    # Calcul et visualisation des rendements journaliers
    returns = calculate_daily_returns(data_clean)
    plot_daily_returns(returns, ticker)
    
    # Visualisation de la volatilité sur 20 jours
    plot_volatility(returns, ticker)
    
    # Optionnel : Analyse de corrélation si plusieurs actifs existent
    tickers = ["AAPL", "MSFT", "GOOG"]  # Exemple d'un ensemble d'actifs
    data_dict = {}
    for t in tickers:
        path = f"data/brut/{t}_data_brut.csv"
        if os.path.exists(path):
            df = load_csv(path)
            df_clean = clean_data(df)
            data_dict[t] = df_clean
    if len(data_dict) > 1:
        plot_correlation_heatmap(data_dict)
    else:
        print("Données insuffisantes pour une analyse de corrélation multi-actifs.")

if __name__ == "__main__":
    main()
