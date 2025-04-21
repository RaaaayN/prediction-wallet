import yfinance as yf
import pandas as pd
import os
from datetime import datetime, timedelta

class DataCollector:
    def __init__(self, symbols, start_date=None, end_date=None):
        """
        Initialise le collecteur de données
        
        Args:
            symbols (list): Liste des symboles d'actifs à collecter
            start_date (str): Date de début au format 'YYYY-MM-DD'
            end_date (str): Date de fin au format 'YYYY-MM-DD'
        """
        self.symbols = symbols
        self.start_date = start_date or (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
        self.end_date = end_date or datetime.now().strftime('%Y-%m-%d')
        
    def collect_data(self):
        """
        Collecte les données historiques pour tous les symboles
        """
        data = {}
        for symbol in self.symbols:
            try:
                ticker = yf.Ticker(symbol)
                df = ticker.history(start=self.start_date, end=self.end_date)
                data[symbol] = df
                print(f"Données collectées pour {symbol}")
            except Exception as e:
                print(f"Erreur lors de la collecte des données pour {symbol}: {str(e)}")
        
        return data
    
    def save_data(self, data, output_dir='data/raw'):
        """
        Sauvegarde les données dans des fichiers CSV
        
        Args:
            data (dict): Données collectées
            output_dir (str): Répertoire de sortie
        """
        os.makedirs(output_dir, exist_ok=True)
        
        for symbol, df in data.items():
            filename = os.path.join(output_dir, f"{symbol}.csv")
            df.to_csv(filename)
            print(f"Données sauvegardées dans {filename}")

def main():
    # Exemple d'utilisation
    symbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META']
    collector = DataCollector(symbols)
    data = collector.collect_data()
    collector.save_data(data)

if __name__ == "__main__":
    main() 