#!.venv\Scripts\python.exe

import pandas as pd
from prophet import Prophet
import matplotlib.pyplot as plt

# Charger les données en précisant qu'il faut parser la colonne 'Date'
data = pd.read_csv('data/AAPL_data.csv', parse_dates=['Date'])

# Renommer les colonnes pour correspondre aux exigences de Prophet :
#   - "ds" pour la date et "y" pour la valeur à prévoir
data.rename(columns={'Date': 'ds', 'Close': 'y'}, inplace=True)

# Vérifier l'aperçu des données
print(data.head())

# Initialisation et entraînement du modèle Prophet
model = Prophet()
model.fit(data)

# Création du DataFrame futur pour 30 jours de prévisions
future = model.make_future_dataframe(periods=30)
forecast = model.predict(future)

# Visualisation de la prévision
fig1 = model.plot(forecast)
plt.title("Prévision avec Prophet")
plt.xlabel("Date")
plt.ylabel("Prix de clôture")
plt.show()

# Affichage des composantes de la prévision (tendance, saisonnalité, etc.)
fig2 = model.plot_components(forecast)
plt.show()
