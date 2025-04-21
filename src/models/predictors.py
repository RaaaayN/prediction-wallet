import numpy as np
import pandas as pd
from statsmodels.tsa.arima.model import ARIMA
from prophet import Prophet
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout
from sklearn.metrics import mean_squared_error, mean_absolute_error
import joblib
import os
from sklearn.preprocessing import MinMaxScaler

class BasePredictor:
    def __init__(self, data_dir='data/processed'):
        self.data_dir = data_dir
        
    def load_data(self, symbol):
        filename = os.path.join(self.data_dir, f"{symbol}_normalized_features.csv")
        df = pd.read_csv(filename, index_col=0)
        # Convertir l'index en datetime et supprimer les informations de fuseau horaire
        df.index = pd.to_datetime(df.index, utc=True).tz_localize(None)
        return df
    
    def prepare_data(self, data, sequence_length=60):
        X, y = [], []
        for i in range(len(data) - sequence_length):
            X.append(data[i:(i + sequence_length)])
            y.append(data[i + sequence_length])
        return np.array(X), np.array(y)
    
    def evaluate(self, y_true, y_pred):
        mse = mean_squared_error(y_true, y_pred)
        mae = mean_absolute_error(y_true, y_pred)
        return {'MSE': mse, 'MAE': mae}

class ARIMAPredictor(BasePredictor):
    def __init__(self, order=(5,1,0)):
        super().__init__()
        self.order = order
        
    def fit(self, symbol):
        data = self.load_data(symbol)
        # Convertir les données en série temporelle avec un index numérique
        ts_data = data['returns'].values
        self.model = ARIMA(ts_data, order=self.order)
        self.model_fit = self.model.fit()
        return self
        
    def predict(self, steps=30):
        forecast = self.model_fit.forecast(steps=steps)
        return forecast
    
    def save_model(self, symbol, output_dir='models'):
        os.makedirs(output_dir, exist_ok=True)
        filename = os.path.join(output_dir, f"{symbol}_arima.joblib")
        joblib.dump(self.model_fit, filename)

class ProphetPredictor(BasePredictor):
    def __init__(self):
        super().__init__()
        
    def fit(self, symbol):
        data = self.load_data(symbol)
        # Préparer les données pour Prophet
        df = pd.DataFrame({
            'ds': data.index,
            'y': data['returns']
        })
        # S'assurer que les dates sont au bon format
        df['ds'] = pd.to_datetime(df['ds'])
        self.model = Prophet()
        self.model.fit(df)
        return self
        
    def predict(self, steps=30):
        future = self.model.make_future_dataframe(periods=steps)
        forecast = self.model.predict(future)
        return forecast['yhat'][-steps:].values
    
    def save_model(self, symbol, output_dir='models'):
        os.makedirs(output_dir, exist_ok=True)
        filename = os.path.join(output_dir, f"{symbol}_prophet.joblib")
        joblib.dump(self.model, filename)

class LSTMPredictor(BasePredictor):
    def __init__(self, sequence_length=60, units=50, dropout=0.2):
        super().__init__()
        self.sequence_length = sequence_length
        self.units = units
        self.dropout = dropout
        
    def build_model(self, input_shape):
        model = Sequential([
            LSTM(self.units, return_sequences=True, input_shape=input_shape),
            Dropout(self.dropout),
            LSTM(self.units),
            Dropout(self.dropout),
            Dense(1)
        ])
        model.compile(optimizer='adam', loss='mse')
        return model
        
    def fit(self, symbol, epochs=50, batch_size=32):
        data = self.load_data(symbol)
        # Normaliser les données
        self.scaler = MinMaxScaler()
        scaled_data = self.scaler.fit_transform(data[['returns']].values)
        X, y = self.prepare_data(scaled_data, self.sequence_length)
        
        # Reshape pour LSTM [samples, time steps, features]
        X = X.reshape((X.shape[0], X.shape[1], 1))
        
        self.model = self.build_model((X.shape[1], X.shape[2]))
        self.model.fit(X, y, epochs=epochs, batch_size=batch_size, verbose=0)
        return self
        
    def predict(self, data, steps=30):
        # Normaliser les données
        scaled_data = self.scaler.transform(data.reshape(-1, 1))
        predictions = []
        current_sequence = scaled_data[-self.sequence_length:]
        
        for _ in range(steps):
            x = current_sequence.reshape(1, self.sequence_length, 1)
            pred = self.model.predict(x, verbose=0)[0][0]
            predictions.append(pred)
            current_sequence = np.append(current_sequence[1:], pred)
            
        # Dénormaliser les prédictions
        predictions = self.scaler.inverse_transform(np.array(predictions).reshape(-1, 1))
        return predictions.flatten()
    
    def save_model(self, symbol, output_dir='models'):
        os.makedirs(output_dir, exist_ok=True)
        filename = os.path.join(output_dir, f"{symbol}_lstm.h5")
        self.model.save(filename)

def main():
    # Exemple d'utilisation
    symbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META']
    
    for symbol in symbols:
        print(f"\nEntraînement des modèles pour {symbol}")
        
        # ARIMA
        print("Entraînement ARIMA...")
        arima = ARIMAPredictor()
        arima.fit(symbol)
        arima_pred = arima.predict()
        arima.save_model(symbol)
        
        # Prophet
        print("Entraînement Prophet...")
        prophet = ProphetPredictor()
        prophet.fit(symbol)
        prophet_pred = prophet.predict()
        prophet.save_model(symbol)
        
        # LSTM
        print("Entraînement LSTM...")
        lstm = LSTMPredictor()
        lstm.fit(symbol)
        data = lstm.load_data(symbol)
        lstm_pred = lstm.predict(data['returns'].values)
        lstm.save_model(symbol)
        
        print(f"Prédictions terminées pour {symbol}")

if __name__ == "__main__":
    main() 