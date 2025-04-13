#!.venv\Scripts\python.exe
"""
Ce script effectue le prétraitement et l'analyse exploratoire (EDA) des données financières.
Il nettoie les données (valeurs manquantes, outliers, format des dates) et affiche :
- La courbe des prix de clôture
- Les rendements journaliers
- La volatilité sur 20 jours
- Une heatmap de la corrélation des rendements si plusieurs actifs sont disponibles
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
    data = pd.read_csv(filepath, header=0, index_col=0)
    # Convertir l'index en datetime (en précisant le format si besoin, par exemple format="%Y-%m-%d")
    data.index = pd.to_datetime(data.index, errors='coerce')
    # Supprimer les lignes dont l'index est NaT (non converti en date)
    data = data[~data.index.isna()]
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

def calculate_daily_returns(data):
    """
    Calcule les rendements journaliers à partir des cours de clôture.
    """
    returns = data['Close'].pct_change().dropna()
    return returns

def plot_all_for_asset(data, ticker):
    """
    Combine et affiche dans une seule figure :
      - La courbe des prix de clôture
      - Les rendements journaliers
      - La volatilité calculée sur 20 jours (écart-type des rendements)
    """
    returns = calculate_daily_returns(data)
    volatility = returns.rolling(window=20).std()

    # Création d'une figure avec 3 sous-graphes (subplots)
    fig, axs = plt.subplots(3, 1, figsize=(14, 18), sharex=True)
    
    # Courbe des prix de clôture
    axs[0].plot(data.index, data['Close'], label=f'{ticker} Prix de clôture', color='blue')
    axs[0].set_ylabel("Prix")
    axs[0].set_title(f"Courbe des prix de clôture pour {ticker}")
    axs[0].legend()
    axs[0].grid(True)
    
    # Rendements journaliers
    axs[1].plot(returns.index, returns, label=f'{ticker} Rendements Quotidiens', color='green')
    axs[1].set_ylabel("Rendement")
    axs[1].set_title(f"Rendements journaliers pour {ticker}")
    axs[1].legend()
    axs[1].grid(True)
    
    # Volatilité (écart-type sur 20 jours)
    axs[2].plot(volatility.index, volatility, label=f'{ticker} Volatilité (20 jours)', color='red')
    axs[2].set_xlabel("Date")
    axs[2].set_ylabel("Volatilité")
    axs[2].set_title(f"Volatilité sur 20 jours pour {ticker}")
    axs[2].legend()
    axs[2].grid(True)
    
    plt.tight_layout()
    plt.show()

def plot_correlation_heatmap(data_dict):
    """
    Combine les colonnes 'Close' de plusieurs actifs, calcule leurs rendements journaliers,
    puis affiche une heatmap de la matrice de corrélation.
    
    :param data_dict: dictionnaire où la clé est le ticker et la valeur est le DataFrame correspondant.
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
    # Traitement pour un seul actif : AAPL
    ticker = "AAPL"
    filepath = f"data/{ticker}_data.csv"  # Adaptez ce chemin selon vos fichiers
    data = load_csv(filepath)
    data_clean = clean_data(data)
    
    # Afficher tous les graphiques pour l'actif dans une seule figure
    plot_all_for_asset(data_clean, ticker)
    
    # Optionnel : Analyse de corrélation si plusieurs actifs existent
    tickers = ["AAPL", "MSFT", "GOOG"]  # Exemple d'un ensemble d'actifs
    data_dict = {}
    for t in tickers:
        path = f"data/brut/{t}_data_brut.csv"  # Ajustez le chemin selon l'organisation de vos fichiers
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
