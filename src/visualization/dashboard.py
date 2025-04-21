import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta
from technical_indicators import TechnicalAnalyzer

class Dashboard:
    def __init__(self, data_dir='data/processed', results_dir='results'):
        self.data_dir = data_dir
        self.results_dir = results_dir
        self.app = dash.Dash(__name__)
        self.analyzer = TechnicalAnalyzer()
        
    def load_data(self, symbol):
        filename = os.path.join(self.data_dir, f"{symbol}_raw_data.csv")
        df = pd.read_csv(filename, index_col=0, parse_dates=True)
        
        # Entraîner le modèle si les données sont chargées
        if not df.empty:
            self.analyzer.train_model(df)
            
        return df
    
    def load_portfolio_results(self):
        weights = pd.read_csv(os.path.join(self.results_dir, 'optimal_weights.csv'))
        metrics = pd.read_csv(os.path.join(self.results_dir, 'portfolio_metrics.csv'))
        return weights, metrics
    
    def create_price_chart(self, symbol):
        df = self.load_data(symbol)
        indicators = self.analyzer.calculate_indicators(df)
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df.index, y=df['Close'], name='Prix de clôture'))
        fig.add_trace(go.Scatter(x=df.index, y=indicators['SMA'], name='SMA'))
        fig.add_trace(go.Scatter(x=df.index, y=indicators['EMA'], name='EMA'))
        fig.add_trace(go.Scatter(x=df.index, y=indicators['BB_Upper'], name='BB Sup', line=dict(dash='dash')))
        fig.add_trace(go.Scatter(x=df.index, y=indicators['BB_Lower'], name='BB Inf', line=dict(dash='dash')))
        
        fig.update_layout(
            title=f'Évolution du prix de {symbol} avec indicateurs',
            xaxis_title='Date',
            yaxis_title='Prix ($)'
        )
        return fig
    
    def create_indicators_chart(self, symbol):
        df = self.load_data(symbol)
        indicators = self.analyzer.calculate_indicators(df)
        return self.analyzer.get_indicators_plot(df, indicators)
    
    def create_prediction_card(self, symbol):
        df = self.load_data(symbol)
        prediction = self.analyzer.predict(df)
        
        # Déterminer la couleur en fonction de la direction
        color = 'green' if prediction['direction'] == 'Hausse' else 'red'
        
        return html.Div([
            html.H3('Prévision pour les 3 prochains jours'),
            html.Div([
                html.H4(f'Direction: {prediction["direction"]}', 
                       style={'color': color}),
                html.P(f'Probabilité: {prediction["probability"]:.2%}'),
                html.P(f'Confiance: {prediction["confidence"]}')
            ], style={
                'border': f'2px solid {color}',
                'padding': '10px',
                'border-radius': '5px',
                'margin': '10px'
            })
        ])
    
    def create_portfolio_pie(self):
        weights, _ = self.load_portfolio_results()
        fig = px.pie(
            weights,
            values='weight',
            names=weights.index,
            title='Répartition du portefeuille optimal'
        )
        return fig
    
    def create_metrics_table(self):
        _, metrics = self.load_portfolio_results()
        fig = go.Figure(data=[go.Table(
            header=dict(values=['Métrique', 'Valeur']),
            cells=dict(values=[metrics.index, metrics.values])
        )])
        fig.update_layout(title='Métriques du portefeuille')
        return fig
    
    def setup_layout(self):
        symbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META']
        
        self.app.layout = html.Div([
            html.H1('Dashboard d\'Analyse et Prédiction de Portefeuille'),
            
            html.Div([
                html.H2('Sélection des actifs'),
                dcc.Dropdown(
                    id='symbol-dropdown',
                    options=[{'label': s, 'value': s} for s in symbols],
                    value=symbols[0]
                )
            ]),
            
            html.Div([
                html.H2('Prévision'),
                html.Div(id='prediction-card')
            ]),
            
            html.Div([
                html.H2('Graphiques des prix et indicateurs'),
                dcc.Graph(id='price-chart'),
                dcc.Graph(id='indicators-chart')
            ]),
            
            html.Div([
                html.H2('Portefeuille optimal'),
                dcc.Graph(id='portfolio-pie'),
                dcc.Graph(id='metrics-table')
            ])
        ])
        
        @self.app.callback(
            [Output('price-chart', 'figure'),
             Output('indicators-chart', 'figure'),
             Output('prediction-card', 'children')],
            [Input('symbol-dropdown', 'value')]
        )
        def update_charts(symbol):
            return (self.create_price_chart(symbol),
                    self.create_indicators_chart(symbol),
                    self.create_prediction_card(symbol))
        
        @self.app.callback(
            [Output('portfolio-pie', 'figure'),
             Output('metrics-table', 'figure')],
            [Input('symbol-dropdown', 'value')]
        )
        def update_portfolio(_):
            return self.create_portfolio_pie(), self.create_metrics_table()
    
    def run(self, debug=True):
        self.setup_layout()
        self.app.run(debug=debug)

def main():
    dashboard = Dashboard()
    dashboard.run()

if __name__ == "__main__":
    main() 