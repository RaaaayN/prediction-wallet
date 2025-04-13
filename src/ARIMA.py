#!.venv\Scripts\python.exe
import pandas as pd
import matplotlib.pyplot as plt
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.graphics.tsaplots import plot_acf, plot_pacf

# Charger les données journalières
data = pd.read_csv('data/AAPL_data.csv', index_col=0, parse_dates=True)
series_daily = data['Close']

# Resampler les données en hebdomadaire en prenant la moyenne par semaine
series_weekly = series_daily.resample('W').mean()

# Affichage des graphiques ACF et PACF sur la série hebdomadaire différenciée
plt.figure(figsize=(12,5))
plt.subplot(121)
plot_acf(series_weekly.diff().dropna(), ax=plt.gca(), lags=20)
plt.title("ACF de la série hebdomadaire différenciée")
plt.subplot(122)
plot_pacf(series_weekly.diff().dropna(), ax=plt.gca(), lags=20)
plt.title("PACF de la série hebdomadaire différenciée")
plt.tight_layout()
plt.show()

# Création et entraînement du modèle ARIMA sur la série hebdomadaire
# Par exemple, on peut essayer ARIMA(1,1,1) pour ces données
model = ARIMA(series_weekly, order=(1,1,1))
model_fit = model.fit()
print(model_fit.summary())

# Prévision sur les 30 prochaines semaines
forecast = model_fit.forecast(steps=30)

# Affichage des prévisions par rapport aux données historiques hebdomadaires
plt.figure(figsize=(10,5))
plt.plot(series_weekly, label='Historique hebdomadaire')
plt.plot(forecast, label='Prévision ARIMA hebdomadaire', color='red')
plt.title("Prévision ARIMA hebdomadaire sur 30 semaines")
plt.xlabel("Date")
plt.ylabel("Prix de clôture")
plt.legend()
plt.show()
