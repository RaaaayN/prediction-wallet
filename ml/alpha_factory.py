"""
Gradient Boosting Alpha Template
"""
from sklearn.ensemble import GradientBoostingClassifier

def compute_alpha_features(df):
    df['mom_fast'] = df['Close'].pct_change(3)
    df['mom_slow'] = df['Close'].pct_change(15)
    return df

def compute_target_label(df):
    df['Target'] = (df['Close'].shift(-1) > df['Close']).astype(int)
    return df

def get_feature_list():
    return ['mom_fast', 'mom_slow', 'RSI14']

def get_model():
    return GradientBoostingClassifier(n_estimators=50, learning_rate=0.1)
