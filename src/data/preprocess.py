import pandas as pd
import numpy as np
from sklearn.preprocessing import MinMaxScaler
import os

class DataPreprocessor:
    def __init__(self, data_dir='data/raw'):
        """
        Initialise le prétraitement des données
        
        Args:
            data_dir (str): Répertoire contenant les données brutes
        """
        self.data_dir = data_dir
        self.scaler = MinMaxScaler()
        
    def load_data(self, symbol):
        """
        Charge les données pour un symbole donné
        
        Args:
            symbol (str): Symbole de l'actif
            
        Returns:
            pd.DataFrame: Données chargées
        """
        filename = os.path.join(self.data_dir, f"{symbol}.csv")
        return pd.read_csv(filename, index_col=0, parse_dates=True)
    
    def calculate_returns(self, df):
        """
        Calcule les rendements journaliers
        
        Args:
            df (pd.DataFrame): Données de prix
            
        Returns:
            pd.DataFrame: Rendements journaliers
        """
        return df['Close'].pct_change().dropna()
    
    def calculate_volatility(self, returns, window=20):
        """
        Calcule la volatilité mobile
        
        Args:
            returns (pd.Series): Rendements journaliers
            window (int): Taille de la fenêtre mobile
            
        Returns:
            pd.Series: Volatilité mobile
        """
        return returns.rolling(window=window).std()
    
    def preprocess_data(self, symbol):
        """
        Prétraite les données pour un symbole donné
        
        Args:
            symbol (str): Symbole de l'actif
            
        Returns:
            dict: Données prétraitées
        """
        # Chargement des données
        df = self.load_data(symbol)
        
        # Calcul des rendements
        returns = self.calculate_returns(df)
        
        # Calcul de la volatilité
        volatility = self.calculate_volatility(returns)
        
        # Normalisation des données
        features = pd.DataFrame({
            'returns': returns,
            'volatility': volatility
        }).dropna()
        
        normalized_features = pd.DataFrame(
            self.scaler.fit_transform(features),
            columns=features.columns,
            index=features.index
        )
        
        return {
            'raw_data': df,
            'returns': returns,
            'volatility': volatility,
            'normalized_features': normalized_features
        }
    
    def save_processed_data(self, processed_data, symbol, output_dir='data/processed'):
        """
        Sauvegarde les données prétraitées
        
        Args:
            processed_data (dict): Données prétraitées
            symbol (str): Symbole de l'actif
            output_dir (str): Répertoire de sortie
        """
        os.makedirs(output_dir, exist_ok=True)
        
        for key, df in processed_data.items():
            if isinstance(df, pd.DataFrame) or isinstance(df, pd.Series):
                filename = os.path.join(output_dir, f"{symbol}_{key}.csv")
                df.to_csv(filename)
                print(f"Données {key} sauvegardées dans {filename}")

def main():
    # Exemple d'utilisation
    preprocessor = DataPreprocessor()
    symbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META']
    
    for symbol in symbols:
        processed_data = preprocessor.preprocess_data(symbol)
        preprocessor.save_processed_data(processed_data, symbol)

if __name__ == "__main__":
    main() 