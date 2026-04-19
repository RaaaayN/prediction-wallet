"""
Gradient Boosting Alpha Template
"""
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression

from market.fetcher import add_technical_indicators

SUPPORTED_MODELS = {
    "gradient_boosting": GradientBoostingClassifier,
    "random_forest": RandomForestClassifier,
    "logistic_regression": LogisticRegression,
}

def compute_alpha_features(df):
    df['mom_fast'] = df['Close'].pct_change(3)
    df['mom_slow'] = df['Close'].pct_change(15)
    return df


def compute_model_features(df):
    df = add_technical_indicators(df.copy())
    df = compute_alpha_features(df)
    df['mean_reversion'] = (df['Close'] - df['SMA20']) / df['SMA20']
    df['factor_momentum'] = df['Close'].pct_change(10)
    df['factor_volatility'] = df['Close'].pct_change().rolling(20).std()
    df['factor_mr'] = df['mean_reversion']
    df['factor_rsi_trend'] = df['RSI14'].diff()
    df['vol_scaler'] = df['Close'].pct_change().rolling(20).std()
    df['trend_strength'] = df['MACD'] - df['MACD_Signal']
    return df

def compute_target_label(df):
    df['Target'] = (df['Close'].shift(-1) > df['Close']).astype(int)
    return df

def get_feature_list():
    return ['mom_fast', 'mom_slow', 'RSI14']

def get_model(model_type: str = "gradient_boosting", **params):
    cls = SUPPORTED_MODELS.get(model_type, GradientBoostingClassifier)
    try:
        return cls(**params)
    except TypeError:
        return cls()
