import pandas as pd
import numpy as np
from sklearn.preprocessing import MinMaxScaler
from sklearn.ensemble import RandomForestClassifier
from ta.trend import SMAIndicator, EMAIndicator, MACD
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.volatility import BollingerBands

class TechnicalAnalyzer:
    def __init__(self, window_size=14):
        self.window_size = window_size
        self.scaler = MinMaxScaler()
        self.model = RandomForestClassifier(n_estimators=100, random_state=42)
        
    def calculate_indicators(self, df):
        """Calcule les indicateurs techniques"""
        # Moyennes mobiles
        sma = SMAIndicator(close=df['Close'], window=self.window_size)
        ema = EMAIndicator(close=df['Close'], window=self.window_size)
        
        # MACD
        macd = MACD(close=df['Close'])
        
        # RSI
        rsi = RSIIndicator(close=df['Close'], window=self.window_size)
        
        # Stochastique
        stoch = StochasticOscillator(high=df['High'], low=df['Low'], close=df['Close'], window=self.window_size)
        
        # Bollinger Bands
        bb = BollingerBands(close=df['Close'], window=self.window_size)
        
        # Création du DataFrame des indicateurs
        indicators = pd.DataFrame({
            'SMA': sma.sma_indicator(),
            'EMA': ema.ema_indicator(),
            'MACD': macd.macd(),
            'MACD_Signal': macd.macd_signal(),
            'RSI': rsi.rsi(),
            'Stoch_K': stoch.stoch(),
            'Stoch_D': stoch.stoch_signal(),
            'BB_Upper': bb.bollinger_hband(),
            'BB_Lower': bb.bollinger_lband(),
            'BB_Middle': bb.bollinger_mavg()
        })
        
        return indicators
    
    def prepare_features(self, df, indicators):
        """Prépare les features pour la prédiction"""
        # Combiner les données de prix et les indicateurs
        features = pd.concat([
            df[['Close']].pct_change(),
            indicators
        ], axis=1)
        
        # Supprimer les NaN
        features = features.dropna()
        
        # Normaliser les features
        features_scaled = pd.DataFrame(
            self.scaler.fit_transform(features),
            columns=features.columns,
            index=features.index
        )
        
        return features_scaled
    
    def create_target(self, df, horizon=3):
        """Crée la variable cible (1 si le prix monte, 0 sinon)"""
        # Calculer les rendements futurs
        future_returns = df['Close'].pct_change(horizon).shift(-horizon)
        
        # Créer la target (1 si hausse, 0 si baisse)
        target = (future_returns > 0).astype(int)
        
        # Supprimer les NaN
        target = target.dropna()
        
        return target
    
    def train_model(self, df):
        """Entraîne le modèle de prédiction"""
        # Calculer les indicateurs
        indicators = self.calculate_indicators(df)
        
        # Préparer les features
        features = self.prepare_features(df, indicators)
        
        # Créer la variable cible
        target = self.create_target(df)
        
        # Aligner les features et la target
        common_index = features.index.intersection(target.index)
        features = features.loc[common_index]
        target = target.loc[common_index]
        
        # Vérifier que les données sont valides
        if len(features) == 0 or len(target) == 0:
            raise ValueError("Pas assez de données pour l'entraînement")
        
        # Entraîner le modèle
        self.model.fit(features, target)
        
        return self.model
    
    def predict(self, df):
        """Fait une prédiction pour les 3 prochains jours"""
        try:
            # Calculer les indicateurs
            indicators = self.calculate_indicators(df)
            
            # Préparer les features
            features = self.prepare_features(df, indicators)
            
            # Faire la prédiction sur les dernières données
            last_features = features.iloc[-1:]
            
            # Faire la prédiction
            prediction = self.model.predict(last_features)
            probability = self.model.predict_proba(last_features)
            
            return {
                'direction': 'Hausse' if prediction[0] == 1 else 'Baisse',
                'probability': probability[0][1] if prediction[0] == 1 else probability[0][0],
                'confidence': 'Élevée' if max(probability[0]) > 0.7 else 'Moyenne' if max(probability[0]) > 0.6 else 'Faible'
            }
        except Exception as e:
            print(f"Erreur lors de la prédiction: {str(e)}")
            return {
                'direction': 'Indéterminé',
                'probability': 0.5,
                'confidence': 'Faible'
            }
    
    def get_indicators_plot(self, df, indicators):
        """Crée un graphique des indicateurs techniques"""
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
        
        # Créer un subplot avec 3 rangées
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True,
                           vertical_spacing=0.05,
                           subplot_titles=('Prix et Moyennes Mobiles', 'MACD', 'RSI et Stochastique'))
        
        # Prix et moyennes mobiles
        fig.add_trace(go.Scatter(x=df.index, y=df['Close'], name='Prix'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=indicators['SMA'], name='SMA'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=indicators['EMA'], name='EMA'), row=1, col=1)
        
        # MACD
        fig.add_trace(go.Scatter(x=df.index, y=indicators['MACD'], name='MACD'), row=2, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=indicators['MACD_Signal'], name='Signal'), row=2, col=1)
        
        # RSI et Stochastique
        fig.add_trace(go.Scatter(x=df.index, y=indicators['RSI'], name='RSI'), row=3, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=indicators['Stoch_K'], name='Stoch %K'), row=3, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=indicators['Stoch_D'], name='Stoch %D'), row=3, col=1)
        
        # Mise à jour du layout
        fig.update_layout(height=900, title_text="Indicateurs Techniques")
        
        return fig