import pandas as pd
import numpy as np
import os
import json
from datetime import datetime
import yfinance as yf
from scipy.optimize import minimize

class WalletManager:
    def __init__(self, data_dir='data/processed', wallets_dir='data/wallets'):
        self.data_dir = data_dir
        self.wallets_dir = wallets_dir
        os.makedirs(wallets_dir, exist_ok=True)
        
    def create_wallet(self, name, initial_capital=10000, risk_profile='moderate'):
        """Crée un nouveau wallet avec un profil de risque"""
        wallet = {
            'name': name,
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'initial_capital': initial_capital,
            'current_capital': initial_capital,
            'risk_profile': risk_profile,
            'positions': {},
            'history': [],
            'daily_values': [],  # Pour suivre l'évolution dans le temps
            'risk_limits': self._get_risk_limits(risk_profile)
        }
        
        # Initialiser le suivi quotidien
        self._update_daily_value(wallet)
        
        # Sauvegarder le wallet
        self.save_wallet(wallet)
        return wallet
    
    def _get_risk_limits(self, risk_profile):
        """Définit les limites selon le profil de risque"""
        limits = {
            'conservative': {
                'max_position_size': 0.2,  # 20% du capital par position
                'max_sector_exposure': 0.3,  # 30% par secteur
                'stop_loss': 0.05,  # 5% de stop loss
                'take_profit': 0.1,  # 10% de take profit
                'max_leverage': 1.0  # Pas de levier
            },
            'moderate': {
                'max_position_size': 0.3,
                'max_sector_exposure': 0.4,
                'stop_loss': 0.08,
                'take_profit': 0.15,
                'max_leverage': 1.5
            },
            'aggressive': {
                'max_position_size': 0.4,
                'max_sector_exposure': 0.5,
                'stop_loss': 0.1,
                'take_profit': 0.2,
                'max_leverage': 2.0
            }
        }
        return limits.get(risk_profile, limits['moderate'])
    
    def _update_daily_value(self, wallet):
        """Met à jour la valeur quotidienne du wallet"""
        current_value = self.get_wallet_value(wallet['name'])
        wallet['daily_values'].append({
            'date': datetime.now().strftime('%Y-%m-%d'),
            'value': current_value,
            'positions': {symbol: pos['quantity'] for symbol, pos in wallet['positions'].items()}
        })
    
    def save_wallet(self, wallet):
        """Sauvegarde un wallet dans un fichier JSON"""
        filename = os.path.join(self.wallets_dir, f"{wallet['name']}.json")
        with open(filename, 'w') as f:
            json.dump(wallet, f, indent=4)
    
    def load_wallet(self, name):
        """Charge un wallet depuis un fichier JSON"""
        filename = os.path.join(self.wallets_dir, f"{name}.json")
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                return json.load(f)
        return None
    
    def list_wallets(self):
        """Liste tous les wallets disponibles"""
        wallets = []
        for file in os.listdir(self.wallets_dir):
            if file.endswith('.json'):
                name = file[:-5]
                wallet = self.load_wallet(name)
                if wallet:
                    wallets.append(wallet)
        return wallets
    
    def _check_risk_limits(self, wallet, symbol, quantity, price):
        """Vérifie les limites de risque"""
        cost = quantity * price
        position_size = cost / wallet['current_capital']
        
        # Vérifier la taille de la position
        if position_size > wallet['risk_limits']['max_position_size']:
            raise ValueError(f"Taille de position trop grande (max: {wallet['risk_limits']['max_position_size']*100}%)")
            
        # Vérifier l'exposition sectorielle
        sector = self._get_sector(symbol)
        sector_exposure = sum(
            pos['quantity'] * pos['price'] 
            for sym, pos in wallet['positions'].items() 
            if self._get_sector(sym) == sector
        ) / wallet['current_capital']
        
        if sector_exposure > wallet['risk_limits']['max_sector_exposure']:
            raise ValueError(f"Exposition sectorielle trop élevée (max: {wallet['risk_limits']['max_sector_exposure']*100}%)")
    
    def _get_sector(self, symbol):
        """Récupère le secteur d'un actif"""
        try:
            stock = yf.Ticker(symbol)
            return stock.info.get('sector', 'Unknown')
        except:
            return 'Unknown'
    
    def add_position(self, wallet_name, symbol, quantity, price):
        """Ajoute une position à un wallet avec vérification des risques"""
        wallet = self.load_wallet(wallet_name)
        if not wallet:
            raise ValueError(f"Wallet {wallet_name} non trouvé")
            
        # Vérifier les limites de risque
        self._check_risk_limits(wallet, symbol, quantity, price)
        
        # Calculer le coût total
        cost = quantity * price
        
        # Vérifier si on a assez de capital
        if cost > wallet['current_capital']:
            raise ValueError("Capital insuffisant")
            
        # Mettre à jour la position
        if symbol in wallet['positions']:
            old_position = wallet['positions'][symbol]
            total_quantity = old_position['quantity'] + quantity
            avg_price = ((old_position['quantity'] * old_position['price']) + cost) / total_quantity
            wallet['positions'][symbol] = {
                'quantity': total_quantity,
                'price': avg_price,
                'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'stop_loss': avg_price * (1 - wallet['risk_limits']['stop_loss']),
                'take_profit': avg_price * (1 + wallet['risk_limits']['take_profit'])
            }
        else:
            wallet['positions'][symbol] = {
                'quantity': quantity,
                'price': price,
                'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'stop_loss': price * (1 - wallet['risk_limits']['stop_loss']),
                'take_profit': price * (1 + wallet['risk_limits']['take_profit'])
            }
            
        # Mettre à jour le capital
        wallet['current_capital'] -= cost
        
        # Ajouter à l'historique
        wallet['history'].append({
            'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'action': 'BUY',
            'symbol': symbol,
            'quantity': quantity,
            'price': price,
            'total': cost,
            'risk_profile': wallet['risk_profile']
        })
        
        # Mettre à jour la valeur quotidienne
        self._update_daily_value(wallet)
        
        # Sauvegarder les modifications
        self.save_wallet(wallet)
        return wallet
    
    def remove_position(self, wallet_name, symbol, quantity=None):
        """Retire une position d'un wallet"""
        wallet = self.load_wallet(wallet_name)
        if not wallet:
            raise ValueError(f"Wallet {wallet_name} non trouvé")
            
        if symbol not in wallet['positions']:
            raise ValueError(f"Position {symbol} non trouvée")
            
        position = wallet['positions'][symbol]
        
        if quantity is None:
            quantity = position['quantity']
            
        if quantity > position['quantity']:
            raise ValueError("Quantité à vendre supérieure à la position")
            
        sale_amount = quantity * position['price']
        
        if quantity == position['quantity']:
            del wallet['positions'][symbol]
        else:
            position['quantity'] -= quantity
            position['last_update'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
        wallet['current_capital'] += sale_amount
        
        wallet['history'].append({
            'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'action': 'SELL',
            'symbol': symbol,
            'quantity': quantity,
            'price': position['price'],
            'total': sale_amount,
            'risk_profile': wallet['risk_profile']
        })
        
        # Mettre à jour la valeur quotidienne
        self._update_daily_value(wallet)
        
        self.save_wallet(wallet)
        return wallet
    
    def get_wallet_value(self, wallet_name):
        """Calcule la valeur actuelle du wallet"""
        wallet = self.load_wallet(wallet_name)
        if not wallet:
            raise ValueError(f"Wallet {wallet_name} non trouvé")
            
        total_value = wallet['current_capital']
        
        for symbol, position in wallet['positions'].items():
            filename = os.path.join(self.data_dir, f"{symbol}_raw_data.csv")
            if os.path.exists(filename):
                df = pd.read_csv(filename, index_col=0, parse_dates=True)
                current_price = df['Close'].iloc[-1]
                position_value = position['quantity'] * current_price
                total_value += position_value
                
        return total_value
    
    def get_wallet_performance(self, wallet_name):
        """Calcule la performance du wallet"""
        wallet = self.load_wallet(wallet_name)
        if not wallet:
            raise ValueError(f"Wallet {wallet_name} non trouvé")
            
        current_value = self.get_wallet_value(wallet_name)
        initial_capital = wallet['initial_capital']
        
        # Calculer les métriques de performance
        daily_returns = []
        for i in range(1, len(wallet['daily_values'])):
            prev_value = wallet['daily_values'][i-1]['value']
            curr_value = wallet['daily_values'][i]['value']
            daily_returns.append((curr_value - prev_value) / prev_value)
            
        daily_returns = np.array(daily_returns)
        
        return {
            'total_return': (current_value - initial_capital) / initial_capital,
            'current_value': current_value,
            'initial_capital': initial_capital,
            'daily_returns': daily_returns.tolist(),
            'volatility': np.std(daily_returns) * np.sqrt(252) if len(daily_returns) > 0 else 0,
            'sharpe_ratio': (np.mean(daily_returns) * 252) / (np.std(daily_returns) * np.sqrt(252)) if len(daily_returns) > 0 else 0
        }
    
    def get_wallet_positions(self, wallet_name):
        """Récupère les positions actuelles avec leurs valeurs"""
        wallet = self.load_wallet(wallet_name)
        if not wallet:
            raise ValueError(f"Wallet {wallet_name} non trouvé")
            
        positions = []
        for symbol, position in wallet['positions'].items():
            filename = os.path.join(self.data_dir, f"{symbol}_raw_data.csv")
            if os.path.exists(filename):
                df = pd.read_csv(filename, index_col=0, parse_dates=True)
                current_price = df['Close'].iloc[-1]
                position_value = position['quantity'] * current_price
                unrealized_pnl = (current_price - position['price']) * position['quantity']
                
                positions.append({
                    'symbol': symbol,
                    'quantity': position['quantity'],
                    'entry_price': position['price'],
                    'current_price': current_price,
                    'position_value': position_value,
                    'unrealized_pnl': unrealized_pnl,
                    'unrealized_pnl_pct': unrealized_pnl / (position['quantity'] * position['price']),
                    'stop_loss': position['stop_loss'],
                    'take_profit': position['take_profit'],
                    'sector': self._get_sector(symbol)
                })
                
        return positions
    
    def get_wallet_history(self, wallet_name):
        """Récupère l'historique complet du wallet"""
        wallet = self.load_wallet(wallet_name)
        if not wallet:
            raise ValueError(f"Wallet {wallet_name} non trouvé")
            
        return {
            'transactions': wallet['history'],
            'daily_values': wallet['daily_values'],
            'performance': self.get_wallet_performance(wallet_name)
        }
    
    def check_risk_alerts(self, wallet_name):
        """Vérifie les alertes de risque"""
        wallet = self.load_wallet(wallet_name)
        if not wallet:
            raise ValueError(f"Wallet {wallet_name} non trouvé")
            
        alerts = []
        positions = self.get_wallet_positions(wallet_name)
        
        for position in positions:
            # Vérifier les stop loss
            if position['current_price'] <= position['stop_loss']:
                alerts.append({
                    'type': 'STOP_LOSS',
                    'symbol': position['symbol'],
                    'current_price': position['current_price'],
                    'stop_loss': position['stop_loss']
                })
                
            # Vérifier les take profit
            if position['current_price'] >= position['take_profit']:
                alerts.append({
                    'type': 'TAKE_PROFIT',
                    'symbol': position['symbol'],
                    'current_price': position['current_price'],
                    'take_profit': position['take_profit']
                })
                
        return alerts

    def get_current_price(self, symbol):
        """Récupère le prix actuel d'un actif"""
        try:
            stock = yf.Ticker(symbol)
            current_price = stock.history(period='1d')['Close'].iloc[-1]
            return current_price
        except Exception as e:
            raise ValueError(f"Impossible de récupérer le prix de {symbol}: {str(e)}")

    def optimize_existing_positions(self, wallet_name):
        """Optimise les positions existantes d'un wallet"""
        wallet = self.load_wallet(wallet_name)
        if not wallet:
            raise ValueError(f"Wallet {wallet_name} non trouvé")
        
        # Récupérer les positions actuelles
        positions = self.get_wallet_positions(wallet_name)
        if not positions:
            return
        
        # Calculer les poids actuels
        total_value = sum(p['position_value'] for p in positions)
        current_weights = {p['symbol']: p['position_value'] / total_value for p in positions}
        
        # Obtenir les poids optimaux
        optimal_weights = self.get_optimal_weights([p['symbol'] for p in positions])
        
        # Ajuster les positions pour se rapprocher des poids optimaux
        for position in positions:
            symbol = position['symbol']
            current_weight = current_weights[symbol]
            optimal_weight = optimal_weights[symbol]
            
            if abs(current_weight - optimal_weight) > 0.01:  # Seuil de 1%
                current_price = self.get_current_price(symbol)
                target_value = total_value * optimal_weight
                current_value = position['position_value']
                
                if target_value > current_value:
                    # Acheter plus
                    additional_value = target_value - current_value
                    quantity = additional_value / current_price
                    self.add_position(wallet_name, symbol, quantity, current_price)
                else:
                    # Vendre une partie
                    sell_value = current_value - target_value
                    quantity = sell_value / current_price
                    self.remove_position(wallet_name, symbol, quantity)

    def optimize_full_portfolio(self, wallet_name):
        """Optimise complètement le portefeuille"""
        wallet = self.load_wallet(wallet_name)
        if not wallet:
            raise ValueError(f"Wallet {wallet_name} non trouvé")
        
        # Récupérer les actifs disponibles
        available_symbols = self.get_available_symbols()
        
        # Obtenir les poids optimaux
        optimal_weights = self.get_optimal_weights(available_symbols)
        
        # Vendre toutes les positions existantes
        positions = self.get_wallet_positions(wallet_name)
        for position in positions:
            self.remove_position(wallet_name, position['symbol'])
        
        # Investir selon les poids optimaux
        total_capital = wallet['current_capital']
        for symbol, weight in optimal_weights.items():
            if weight > 0.01:  # Ignorer les poids trop faibles
                investment_amount = total_capital * weight
                current_price = self.get_current_price(symbol)
                quantity = investment_amount / current_price
                self.add_position(wallet_name, symbol, quantity, current_price)

    def get_available_symbols(self):
        """Récupère la liste des actifs disponibles"""
        # Pour l'instant, on utilise un ensemble fixe d'actifs
        # TODO: Implémenter une méthode plus sophistiquée pour sélectionner les actifs
        return ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'TSLA', 'NVDA', 'JPM', 'V', 'WMT']

    def get_optimal_weights(self, symbols):
        """Calcule les poids optimaux pour un ensemble d'actifs"""
        try:
            # Récupérer les données historiques
            returns = []
            for symbol in symbols:
                stock = yf.Ticker(symbol)
                hist = stock.history(period='1y')
                returns.append(hist['Close'].pct_change().dropna())
            
            # Créer la matrice de rendements
            returns_df = pd.DataFrame(returns, index=symbols).T
            
            # Calculer la matrice de covariance
            cov_matrix = returns_df.cov()
            
            # Calculer les rendements attendus
            expected_returns = returns_df.mean()
            
            # Optimiser les poids
            n_assets = len(symbols)
            weights = np.random.random(n_assets)
            weights /= np.sum(weights)
            
            # Fonction objectif: maximiser le ratio de Sharpe
            def objective(weights):
                portfolio_return = np.sum(weights * expected_returns)
                portfolio_volatility = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
                return -portfolio_return / portfolio_volatility  # On minimise l'opposé du ratio de Sharpe
            
            # Contraintes
            constraints = ({'type': 'eq', 'fun': lambda x: np.sum(x) - 1})  # Somme des poids = 1
            bounds = [(0, 1) for _ in range(n_assets)]  # Poids entre 0 et 1
            
            # Optimisation
            result = minimize(objective, weights, method='SLSQP', bounds=bounds, constraints=constraints)
            
            # Retourner les poids optimaux
            return {symbol: weight for symbol, weight in zip(symbols, result.x)}
            
        except Exception as e:
            # En cas d'erreur, retourner des poids égaux
            return {symbol: 1/len(symbols) for symbol in symbols} 