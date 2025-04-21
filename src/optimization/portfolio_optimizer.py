import numpy as np
import pandas as pd
from pypfopt import EfficientFrontier
from pypfopt import risk_models
from pypfopt import expected_returns
from pypfopt import objective_functions
import cvxpy as cp
import os
import warnings

class PortfolioOptimizer:
    def __init__(self, data_dir='data/processed'):
        self.data_dir = data_dir
        
    def load_returns(self, symbols):
        returns = {}
        for symbol in symbols:
            filename = os.path.join(self.data_dir, f"{symbol}_returns.csv")
            try:
                df = pd.read_csv(filename, index_col=0, parse_dates=True)
                # Nettoyer les données
                df = df.replace([np.inf, -np.inf], np.nan)
                df = df.fillna(method='ffill').fillna(method='bfill').fillna(0)
                if not df.empty and df.notna().all().all():
                    returns[symbol] = df
                else:
                    print(f"Données invalides pour {symbol}, ignoré")
            except Exception as e:
                print(f"Erreur lors du chargement des données pour {symbol}: {str(e)}")
        
        if not returns:
            raise ValueError("Aucune donnée valide n'a pu être chargée")
            
        return pd.concat(returns, axis=1)
    
    def clean_returns(self, returns):
        # Supprimer les colonnes avec des valeurs manquantes
        returns = returns.dropna(axis=1, how='any')
        
        # Remplacer les valeurs infinies par des NaN
        returns = returns.replace([np.inf, -np.inf], np.nan)
        
        # Remplir les valeurs manquantes
        returns = returns.fillna(method='ffill').fillna(method='bfill').fillna(0)
        
        # Supprimer les colonnes avec des valeurs constantes
        returns = returns.loc[:, returns.std() > 0]
        
        # Vérifier qu'il reste des données valides
        if returns.empty:
            raise ValueError("Aucune donnée valide après nettoyage")
            
        return returns
    
    def calculate_covariance_matrix(self, returns):
        # Utiliser une estimation robuste de la covariance
        try:
            return risk_models.CovarianceShrinkage(returns).ledoit_wolf()
        except Exception as e:
            print(f"Erreur lors du calcul de la covariance: {str(e)}")
            print("Utilisation de la covariance empirique comme fallback")
            return returns.cov()
    
    def calculate_expected_returns(self, returns):
        # Utiliser une estimation robuste des rendements attendus
        try:
            return expected_returns.ema_historical_return(returns)
        except Exception as e:
            print(f"Erreur lors du calcul des rendements attendus: {str(e)}")
            print("Utilisation de la moyenne comme fallback")
            return returns.mean()
    
    def optimize_sharpe_ratio(self, returns, risk_free_rate=0.02):
        """
        Optimise le portefeuille en maximisant le ratio de Sharpe
        
        Args:
            returns (pd.DataFrame): Matrice des rendements
            risk_free_rate (float): Taux sans risque
            
        Returns:
            dict: Poids optimaux et métriques
        """
        # Nettoyer les données
        returns = self.clean_returns(returns)
        
        # Calculer les rendements attendus et la matrice de covariance
        mu = self.calculate_expected_returns(returns)
        S = self.calculate_covariance_matrix(returns)
        
        # Créer la frontière efficiente
        ef = EfficientFrontier(mu, S)
        
        # Ajouter une régularisation L2 pour stabiliser l'optimisation
        ef.add_objective(objective_functions.L2_reg, gamma=0.1)
        
        # Maximiser le ratio de Sharpe
        try:
            weights = ef.max_sharpe(risk_free_rate=risk_free_rate)
            performance = ef.portfolio_performance(risk_free_rate=risk_free_rate)
            
            return {
                'weights': weights,
                'expected_return': performance[0],
                'volatility': performance[1],
                'sharpe_ratio': performance[2]
            }
        except Exception as e:
            print(f"Erreur lors de l'optimisation du ratio de Sharpe: {str(e)}")
            # Retourner une solution par défaut
            return self.optimize_min_variance(returns)
    
    def optimize_min_variance(self, returns):
        """
        Optimise le portefeuille en minimisant la variance
        
        Args:
            returns (pd.DataFrame): Matrice des rendements
            
        Returns:
            dict: Poids optimaux et métriques
        """
        # Nettoyer les données
        returns = self.clean_returns(returns)
        
        # Calculer la matrice de covariance
        S = self.calculate_covariance_matrix(returns)
        
        # Créer la frontière efficiente
        ef = EfficientFrontier(None, S)
        
        # Ajouter une régularisation L2 pour stabiliser l'optimisation
        ef.add_objective(objective_functions.L2_reg, gamma=0.1)
        
        # Minimiser la variance
        weights = ef.min_volatility()
        performance = ef.portfolio_performance()
        
        return {
            'weights': weights,
            'expected_return': performance[0],
            'volatility': performance[1],
            'sharpe_ratio': performance[2]
        }
    
    def optimize_custom(self, returns, target_return=None, max_volatility=None):
        """
        Optimise le portefeuille avec des contraintes personnalisées
        
        Args:
            returns (pd.DataFrame): Matrice des rendements
            target_return (float): Rendement cible
            max_volatility (float): Volatilité maximale
            
        Returns:
            dict: Poids optimaux et métriques
        """
        # Nettoyer les données
        returns = self.clean_returns(returns)
        
        # Calculer les rendements attendus et la matrice de covariance
        mu = self.calculate_expected_returns(returns)
        S = self.calculate_covariance_matrix(returns)
        
        # Créer la frontière efficiente
        ef = EfficientFrontier(mu, S)
        
        # Ajouter une régularisation L2 pour stabiliser l'optimisation
        ef.add_objective(objective_functions.L2_reg, gamma=0.1)
        
        try:
            if target_return is not None:
                ef.efficient_return(target_return)
            elif max_volatility is not None:
                ef.efficient_risk(max_volatility)
            else:
                ef.max_sharpe()
                
            weights = ef.clean_weights()
            performance = ef.portfolio_performance()
            
            return {
                'weights': weights,
                'expected_return': performance[0],
                'volatility': performance[1],
                'sharpe_ratio': performance[2]
            }
        except Exception as e:
            print(f"Erreur lors de l'optimisation personnalisée: {str(e)}")
            # Retourner une solution par défaut
            return self.optimize_min_variance(returns)
    
    def save_results(self, results, output_dir='results'):
        """
        Sauvegarde les résultats de l'optimisation
        
        Args:
            results (dict): Résultats de l'optimisation
            output_dir (str): Répertoire de sortie
        """
        os.makedirs(output_dir, exist_ok=True)
        
        # Sauvegarde des poids
        weights_df = pd.DataFrame.from_dict(results['weights'], orient='index', columns=['weight'])
        weights_df.to_csv(os.path.join(output_dir, 'optimal_weights.csv'))
        
        # Sauvegarde des métriques
        metrics = {
            'Expected Return': results['expected_return'],
            'Volatility': results['volatility'],
            'Sharpe Ratio': results['sharpe_ratio']
        }
        pd.Series(metrics).to_csv(os.path.join(output_dir, 'portfolio_metrics.csv'))

def main():
    # Supprimer les avertissements
    warnings.filterwarnings('ignore')
    
    # Exemple d'utilisation
    symbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META']
    optimizer = PortfolioOptimizer()
    
    try:
        # Chargement des données
        print("Chargement des données...")
        returns = optimizer.load_returns(symbols)
        
        # Optimisation avec différentes méthodes
        print("\nOptimisation du ratio de Sharpe...")
        sharpe_results = optimizer.optimize_sharpe_ratio(returns)
        
        print("\nOptimisation de la variance minimale...")
        min_var_results = optimizer.optimize_min_variance(returns)
        
        print("\nOptimisation personnalisée...")
        custom_results = optimizer.optimize_custom(returns, target_return=0.15)
        
        # Sauvegarde des résultats
        optimizer.save_results(sharpe_results)
        print("\nRésultats sauvegardés dans le dossier 'results'")
        
    except Exception as e:
        print(f"Erreur lors de l'exécution: {str(e)}")

if __name__ == "__main__":
    main() 