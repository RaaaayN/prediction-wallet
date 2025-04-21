# Prediction Wallet - Optimisation de Portefeuille

Ce projet vise à créer un système de prédiction des cours boursiers et d'optimisation de portefeuille d'investissement.

## Objectifs

- Prédire les cours futurs des actifs financiers
- Optimiser la composition d'un portefeuille d'investissement
- Créer un dashboard interactif pour visualiser les résultats

## Structure du Projet

```
prediction-wallet/
├── data/                  # Données brutes et prétraitées
├── notebooks/             # Notebooks Jupyter pour l'analyse
├── src/
│   ├── data/             # Scripts de collecte et prétraitement
│   ├── models/           # Modèles de prédiction
│   ├── optimization/     # Optimisation de portefeuille
│   └── visualization/    # Visualisation et dashboard
├── tests/                # Tests unitaires
├── requirements.txt      # Dépendances Python
└── README.md            # Documentation
```

## Installation

1. Cloner le repository
2. Créer un environnement virtuel Python
3. Installer les dépendances :
```bash
pip install -r requirements.txt
```

## Utilisation

1. Collecter les données :
```bash
python src/data/collect_data.py
```

2. Entraîner les modèles :
```bash
python src/models/train_models.py
```

3. Lancer le dashboard :
```bash
python src/visualization/dashboard.py
```

## Fonctionnalités

- Collecte de données financières via Yahoo Finance
- Prétraitement et analyse exploratoire des données
- Modèles de prédiction (ARIMA, LSTM, Prophet)
- Optimisation de portefeuille (ratio de Sharpe, variance minimale)
- Dashboard interactif avec Plotly et Dash

## Tests

```bash
pytest tests/
```

## Licence

MIT
