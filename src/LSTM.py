#!.venv\Scripts\python.exe

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.preprocessing import MinMaxScaler
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense
from tqdm import tqdm  # pour afficher la barre de progression

# Charger les données historiques
data = pd.read_csv('data/AAPL_data.csv', index_col=0, parse_dates=True)
closing_data = data['Close'].values.reshape(-1, 1)

# Normalisation des données
scaler = MinMaxScaler(feature_range=(0, 1))
scaled_data = scaler.fit_transform(closing_data)

# Fonction pour créer des séquences temporelles
def create_dataset(dataset, time_step=50):
    X, y = [], []
    for i in range(len(dataset) - time_step):
        a = dataset[i:(i + time_step), 0]  # séquence d'entrée
        X.append(a)
        y.append(dataset[i + time_step, 0])  # valeur à prédire
    return np.array(X), np.array(y)

time_step = 50  # taille de la fenêtre
X, y = create_dataset(scaled_data, time_step)
X = X.reshape(X.shape[0], X.shape[1], 1)  # reshape pour le modèle LSTM

# Définition du modèle LSTM
model = Sequential()
model.add(LSTM(50, return_sequences=True, input_shape=(time_step, 1)))
model.add(LSTM(50, return_sequences=False))
model.add(Dense(25))
model.add(Dense(1))
model.compile(optimizer='adam', loss='mean_squared_error')

# Entraînement du modèle
model.fit(X, y, batch_size=32, epochs=10)

# Prédiction in-sample pour comparer avec l'historique
predictions_in_sample = model.predict(X, verbose=0)
predictions_in_sample = scaler.inverse_transform(predictions_in_sample)

plt.figure(figsize=(10,5))
plt.plot(data.index[time_step:], data['Close'][time_step:], label='Historique')
plt.plot(data.index[time_step:], predictions_in_sample, label='Prévision LSTM (in-sample)', color='red')
plt.title("Prévision LSTM in-sample")
plt.xlabel("Date")
plt.ylabel("Prix de clôture")
plt.legend()
plt.show()

# -----------------------------
# Prédiction itérative jusqu'au 31 décembre 2026

# Définir le dernier jour connu et la date cible
last_date = data.index[-1]
target_date = pd.to_datetime('2026-12-31')

# Générer une plage de dates futures (jours ouvrables)
future_dates = pd.bdate_range(start=last_date + pd.Timedelta(days=1), end=target_date)
n_future = len(future_dates)
print("Nombre de jours futurs (ouvrables):", n_future)

# Initialiser la séquence avec les dernières observations
current_sequence = scaled_data[-time_step:].copy()
forecast_list = []

# Prédiction itérative avec une barre de progression
for i in tqdm(range(n_future), desc="Prévision itérative"):
    pred = model.predict(current_sequence.reshape(1, time_step, 1), verbose=0)
    forecast_value = pred[0, 0]
    forecast_list.append(forecast_value)
    # Mettre à jour la séquence : retirer la première valeur et ajouter la prédiction
    current_sequence = np.append(current_sequence[1:], [[forecast_value]], axis=0)

# Inverser la normalisation pour les prévisions
forecast_predictions = scaler.inverse_transform(np.array(forecast_list).reshape(-1, 1))

# Créer un DataFrame pour les prévisions, indexé par les jours futurs
forecast_df = pd.DataFrame(data=forecast_predictions, index=future_dates, columns=['Forecast'])

# Tracer la courbe complète (historique + prévisions)
plt.figure(figsize=(14,7))
plt.plot(data.index, data['Close'], label='Historique')
plt.plot(forecast_df.index, forecast_df['Forecast'], label='Prévision LSTM jusqu’en 2026', color='red')
plt.title("Prévision LSTM jusqu’en 2026")
plt.xlabel("Date")
plt.ylabel("Prix de clôture")
plt.legend()
plt.tight_layout()
plt.show()
