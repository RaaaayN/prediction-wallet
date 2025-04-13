# Projet de Collecte des Données Financières

Ce projet a pour but de collecter et traiter des données financières via l'API Yahoo Finance, en utilisant la bibliothèque `yfinance` en Python. Les données récupérées incluent l'historique des prix journaliers ainsi que divers indicateurs techniques (tels que SMA, EMA, RSI, Bollinger Bands, MACD, etc.). Les données sont ensuite sauvegardées sous forme de fichiers CSV et dans une base de données SQLite, ce qui permet une réutilisation et une analyse ultérieure facile.

## Prérequis

- **Python 3.x**
- **Bibliothèques Python :**
  - `yfinance`
  - `pandas`
  - `sqlite3` (fourni par défaut avec Python)

## Installation et Configuration de l'Environnement

Il est recommandé d'utiliser un environnement virtuel (venv) pour isoler les dépendances du projet.

### Création et Activation du venv

1. **Création de l'environnement virtuel**  
   Depuis le répertoire racine du projet, exécutez :
   ```bash
   python -m venv venv
