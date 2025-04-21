import dash
from dash import dcc, html
from dash.dependencies import Input, Output, State
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta
from technical_indicators import TechnicalAnalyzer
from wallet_manager import WalletManager

class Dashboard:
    def __init__(self, data_dir='data/processed', results_dir='results'):
        self.data_dir = data_dir
        self.results_dir = results_dir
        self.app = dash.Dash(__name__)
        self.analyzer = TechnicalAnalyzer()
        self.wallet_manager = WalletManager()
        
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
        color = 'green' if prediction['direction'] == 'Hausse' else 'red' if prediction['direction'] == 'Baisse' else 'gray'
        
        return html.Div([
            html.H3('Prévision pour les 3 prochains jours'),
            html.Div([
                html.H4(f'Direction: {prediction["direction"]}', 
                       style={'color': color}),
                html.P(f'Probabilité: {prediction["probability"]:.2%}'),
                html.P(f'Confiance: {prediction["confidence"]}'),
                html.P(f'Date de la prédiction: {prediction["prediction_date"]}'),
                html.P(f'Période de prévision: {prediction["forecast_period"]}')
            ], style={
                'border': f'2px solid {color}',
                'padding': '10px',
                'border-radius': '5px',
                'margin': '10px',
                'background-color': f'{color}10'
            }),
            
            html.Div([
                html.H4('Test de prédiction'),
                html.Button('Tester la prédiction sur les 3 derniers jours', 
                          id='test-prediction-button',
                          n_clicks=0,
                          style={'margin': '10px'}),
                html.Div(id='test-results')
            ])
        ])
    
    def create_test_results(self, symbol):
        df = self.load_data(symbol)
        test_results = self.analyzer.test_prediction(df)
        
        if test_results is None:
            return html.Div("Erreur lors du test de prédiction")
            
        # Couleurs pour l'affichage
        pred_color = 'green' if test_results['prediction']['direction'] == 'Hausse' else 'red'
        actual_color = 'green' if test_results['actual']['direction'] == 'Hausse' else 'red'
        result_color = 'green' if test_results['correct'] else 'red'
        
        return html.Div([
            html.H4('Résultats du test', style={'margin-top': '20px'}),
            html.Div([
                html.H5('Prévision faite le:'),
                html.P(test_results['prediction']['date']),
                html.P(f"Période testée: {test_results['prediction']['period']}"),
                html.P(f"Direction prédite: {test_results['prediction']['direction']}", 
                      style={'color': pred_color}),
                html.P(f"Probabilité: {test_results['prediction']['probability']:.2%}"),
                html.P(f"Confiance: {test_results['prediction']['confidence']}")
            ], style={
                'border': f'2px solid {pred_color}',
                'padding': '10px',
                'border-radius': '5px',
                'margin': '10px',
                'background-color': f'{pred_color}10'
            }),
            
            html.Div([
                html.H5('Résultat réel:'),
                html.P(f"Direction réelle: {test_results['actual']['direction']}", 
                      style={'color': actual_color}),
                html.P(f"Rendement: {test_results['actual']['return']:.2%}"),
                html.P(f"Période: {test_results['actual']['period']}")
            ], style={
                'border': f'2px solid {actual_color}',
                'padding': '10px',
                'border-radius': '5px',
                'margin': '10px',
                'background-color': f'{actual_color}10'
            }),
            
            html.Div([
                html.H5('Résultat du test:'),
                html.P(f"Prédiction {'correcte' if test_results['correct'] else 'incorrecte'}", 
                      style={'color': result_color, 'font-weight': 'bold'})
            ], style={
                'border': f'2px solid {result_color}',
                'padding': '10px',
                'border-radius': '5px',
                'margin': '10px',
                'background-color': f'{result_color}10'
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
    
    def create_wallet_management_section(self):
        """Crée la section de gestion des wallets"""
        wallets = self.wallet_manager.list_wallets()
        
        return html.Div([
            html.H2('Gestion des Wallets'),
            
            # Création de wallet
            html.Div([
                html.H3('Créer un nouveau wallet'),
                dcc.Input(id='new-wallet-name', type='text', placeholder='Nom du wallet'),
                dcc.Input(id='new-wallet-capital', type='number', placeholder='Capital initial', value=10000),
                dcc.Dropdown(
                    id='risk-profile-dropdown',
                    options=[
                        {'label': 'Conservateur', 'value': 'conservative'},
                        {'label': 'Modéré', 'value': 'moderate'},
                        {'label': 'Agressif', 'value': 'aggressive'}
                    ],
                    value='moderate'
                ),
                html.Button('Créer', id='create-wallet-button'),
                html.Div(id='create-wallet-output')
            ], style={'margin': '10px', 'padding': '10px', 'border': '1px solid #ddd'}),
            
            # Sélection de wallet
            html.Div([
                html.H3('Sélectionner un wallet'),
                dcc.Dropdown(
                    id='wallet-dropdown',
                    options=[{'label': w['name'], 'value': w['name']} for w in wallets],
                    value=wallets[0]['name'] if wallets else None
                )
            ], style={'margin': '10px', 'padding': '10px', 'border': '1px solid #ddd'}),
            
            # Gestion des positions
            html.Div([
                html.H3('Gérer les positions'),
                html.Div([
                    dcc.Input(id='position-symbol', type='text', placeholder='Symbole'),
                    dcc.RadioItems(
                        id='position-type',
                        options=[
                            {'label': 'Quantité d\'actions', 'value': 'quantity'},
                            {'label': 'Montant en dollars', 'value': 'amount'}
                        ],
                        value='quantity'
                    ),
                    dcc.Input(id='position-value', type='number', placeholder='Quantité ou montant'),
                    html.Button('Acheter', id='buy-button'),
                    html.Button('Vendre', id='sell-button'),
                    html.Div(id='current-price-display'),
                    html.Div(id='position-output')
                ]),
                
                # Gestion automatique
                html.Div([
                    html.H4('Gestion automatique'),
                    dcc.RadioItems(
                        id='auto-trading-mode',
                        options=[
                            {'label': 'Désactivé', 'value': 'off'},
                            {'label': 'Gestion partielle', 'value': 'partial'},
                            {'label': 'Gestion complète', 'value': 'full'}
                        ],
                        value='off'
                    ),
                    html.Button('Activer la gestion automatique', id='activate-auto-trading'),
                    html.Div(id='auto-trading-status'),
                    dcc.Interval(
                        id='auto-trading-interval',
                        interval=5*60*1000,  # 5 minutes
                        n_intervals=0
                    )
                ], style={'margin-top': '20px', 'padding': '10px', 'border': '1px solid #ddd'})
            ], style={'margin': '10px', 'padding': '10px', 'border': '1px solid #ddd'}),
            
            # Alertes de risque
            html.Div([
                html.H3('Alertes de risque'),
                html.Div(id='risk-alerts')
            ], style={'margin': '10px', 'padding': '10px', 'border': '1px solid #ddd'}),
            
            # Affichage du wallet
            html.Div(id='wallet-display')
        ])
    
    def create_wallet_display(self, wallet_name):
        """Crée l'affichage détaillé d'un wallet"""
        if not wallet_name:
            return html.Div("Sélectionnez un wallet")
            
        wallet = self.wallet_manager.load_wallet(wallet_name)
        if not wallet:
            return html.Div("Wallet non trouvé")
            
        performance = self.wallet_manager.get_wallet_performance(wallet_name)
        positions = self.wallet_manager.get_wallet_positions(wallet_name)
        history = self.wallet_manager.get_wallet_history(wallet_name)
        
        # Créer le graphique de performance
        daily_values = pd.DataFrame(history['daily_values'])
        if not daily_values.empty:
            daily_values['date'] = pd.to_datetime(daily_values['date'])
            daily_values.set_index('date', inplace=True)
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=daily_values.index,
                y=daily_values['value'],
                name='Valeur du wallet'
            ))
            fig.update_layout(
                title='Évolution de la valeur du wallet',
                xaxis_title='Date',
                yaxis_title='Valeur ($)'
            )
        else:
            fig = go.Figure()
        
        # Créer le tableau des positions
        positions_table = go.Figure(data=[go.Table(
            header=dict(values=['Symbole', 'Secteur', 'Quantité', 'Prix d\'entrée', 'Prix actuel', 'Valeur', 'P&L', 'P&L %', 'Stop Loss', 'Take Profit']),
            cells=dict(values=[
                [p['symbol'] for p in positions],
                [p['sector'] for p in positions],
                [p['quantity'] for p in positions],
                [f"${p['entry_price']:.2f}" for p in positions],
                [f"${p['current_price']:.2f}" for p in positions],
                [f"${p['position_value']:.2f}" for p in positions],
                [f"${p['unrealized_pnl']:.2f}" for p in positions],
                [f"{p['unrealized_pnl_pct']:.2%}" for p in positions],
                [f"${p['stop_loss']:.2f}" for p in positions],
                [f"${p['take_profit']:.2f}" for p in positions]
            ])
        )])
        
        # Créer le tableau des métriques de performance
        metrics_table = go.Figure(data=[go.Table(
            header=dict(values=['Métrique', 'Valeur']),
            cells=dict(values=[
                ['Rendement total', 'Volatilité', 'Ratio de Sharpe'],
                [
                    f"{performance['total_return']:.2%}",
                    f"{performance['volatility']:.2%}",
                    f"{performance['sharpe_ratio']:.2f}"
                ]
            ])
        )])
        
        return html.Div([
            html.H3(f"Wallet: {wallet_name}"),
            html.P(f"Créé le: {wallet['created_at']}"),
            html.P(f"Profil de risque: {wallet['risk_profile']}"),
            html.P(f"Capital initial: ${wallet['initial_capital']:.2f}"),
            html.P(f"Capital actuel: ${wallet['current_capital']:.2f}"),
            html.P(f"Performance totale: {performance['total_return']:.2%}"),
            
            dcc.Graph(figure=fig),
            dcc.Graph(figure=metrics_table),
            dcc.Graph(figure=positions_table),
            
            html.H4('Historique des transactions'),
            html.Table([
                html.Tr([
                    html.Th('Date'),
                    html.Th('Action'),
                    html.Th('Symbole'),
                    html.Th('Quantité'),
                    html.Th('Prix'),
                    html.Th('Total'),
                    html.Th('Profil de risque')
                ])
            ] + [
                html.Tr([
                    html.Td(t['date']),
                    html.Td(t['action']),
                    html.Td(t['symbol']),
                    html.Td(t['quantity']),
                    html.Td(f"${t['price']:.2f}"),
                    html.Td(f"${t['total']:.2f}"),
                    html.Td(t['risk_profile'])
                ]) for t in reversed(history['transactions'])
            ])
        ])
    
    def setup_layout(self):
        symbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META']
        
        self.app.layout = html.Div([
            html.H1('Dashboard d\'Analyse et Prédiction de Portefeuille'),
            
            # Section de gestion des wallets
            self.create_wallet_management_section(),
            
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
        
        # Callbacks pour la gestion des wallets
        @self.app.callback(
            Output('create-wallet-output', 'children'),
            [Input('create-wallet-button', 'n_clicks')],
            [State('new-wallet-name', 'value'),
             State('new-wallet-capital', 'value'),
             State('risk-profile-dropdown', 'value')]
        )
        def create_wallet(n_clicks, name, capital, risk_profile):
            if n_clicks and name:
                try:
                    self.wallet_manager.create_wallet(name, capital, risk_profile)
                    return f"Wallet {name} créé avec succès!"
                except Exception as e:
                    return f"Erreur: {str(e)}"
            return ""
            
        # Callbacks pour la gestion des positions
        @self.app.callback(
            Output('current-price-display', 'children'),
            [Input('position-symbol', 'value')]
        )
        def update_current_price(symbol):
            if not symbol:
                return ""
            try:
                current_price = self.wallet_manager.get_current_price(symbol)
                return html.Div([
                    html.Strong(f"Prix actuel de {symbol}: "),
                    f"${current_price:.2f}"
                ])
            except Exception as e:
                return html.Div(f"Erreur: {str(e)}")
        
        @self.app.callback(
            Output('position-output', 'children'),
            [Input('buy-button', 'n_clicks'),
             Input('sell-button', 'n_clicks')],
            [State('wallet-dropdown', 'value'),
             State('position-symbol', 'value'),
             State('position-type', 'value'),
             State('position-value', 'value')]
        )
        def manage_position(buy_clicks, sell_clicks, wallet_name, symbol, position_type, value):
            if not wallet_name or not symbol or not value:
                return "Veuillez remplir tous les champs"
                
            ctx = dash.callback_context
            if not ctx.triggered:
                return ""
                
            button_id = ctx.triggered[0]['prop_id'].split('.')[0]
            
            try:
                current_price = self.wallet_manager.get_current_price(symbol)
                
                if position_type == 'amount':
                    # Convertir le montant en nombre d'actions
                    quantity = value / current_price
                else:
                    quantity = value
                    
                if button_id == 'buy-button':
                    self.wallet_manager.add_position(wallet_name, symbol, quantity, current_price)
                    return f"Achat de {quantity:.2f} {symbol} au prix de ${current_price:.2f}"
                elif button_id == 'sell-button':
                    self.wallet_manager.remove_position(wallet_name, symbol, quantity)
                    return f"Vente de {quantity:.2f} {symbol} au prix de ${current_price:.2f}"
            except Exception as e:
                return f"Erreur: {str(e)}"
        
        @self.app.callback(
            [Output('auto-trading-status', 'children'),
             Output('auto-trading-interval', 'disabled')],
            [Input('activate-auto-trading', 'n_clicks'),
             Input('auto-trading-interval', 'n_intervals')],
            [State('wallet-dropdown', 'value'),
             State('auto-trading-mode', 'value')]
        )
        def manage_auto_trading(n_clicks, n_intervals, wallet_name, mode):
            if not wallet_name:
                return "Sélectionnez un wallet", True
                
            ctx = dash.callback_context
            if not ctx.triggered:
                return "Gestion automatique désactivée", True
                
            trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
            
            if trigger_id == 'activate-auto-trading':
                if mode == 'off':
                    return "Gestion automatique désactivée", True
                else:
                    return f"Gestion automatique activée ({mode})", False
            elif trigger_id == 'auto-trading-interval':
                try:
                    if mode == 'partial':
                        # Gestion partielle: ajuste les positions existantes
                        self.wallet_manager.optimize_existing_positions(wallet_name)
                    elif mode == 'full':
                        # Gestion complète: peut vendre tout et réinvestir
                        self.wallet_manager.optimize_full_portfolio(wallet_name)
                    return f"Dernière mise à jour: {datetime.now().strftime('%H:%M:%S')}", False
                except Exception as e:
                    return f"Erreur lors de la mise à jour: {str(e)}", False
                
            return "Gestion automatique désactivée", True
        
        @self.app.callback(
            Output('wallet-display', 'children'),
            [Input('wallet-dropdown', 'value')]
        )
        def update_wallet_display(wallet_name):
            return self.create_wallet_display(wallet_name)
        
        @self.app.callback(
            Output('risk-alerts', 'children'),
            [Input('wallet-dropdown', 'value')]
        )
        def update_risk_alerts(wallet_name):
            if not wallet_name:
                return "Sélectionnez un wallet"
            
            alerts = self.wallet_manager.check_risk_alerts(wallet_name)
            if not alerts:
                return "Aucune alerte de risque"
            
            return html.Div([
                html.H4('Alertes actives:'),
                html.Ul([
                    html.Li([
                        html.Strong(f"{alert['type']} - {alert['symbol']}"),
                        html.Br(),
                        f"Prix actuel: ${alert['current_price']:.2f}",
                        html.Br(),
                        f"{'Stop Loss' if alert['type'] == 'STOP_LOSS' else 'Take Profit'}: ${alert['stop_loss'] if alert['type'] == 'STOP_LOSS' else alert['take_profit']:.2f}"
                    ]) for alert in alerts
                ])
            ])
        
        # Callbacks existants pour les graphiques et prédictions
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
            
        @self.app.callback(
            Output('test-results', 'children'),
            [Input('test-prediction-button', 'n_clicks'),
             Input('symbol-dropdown', 'value')]
        )
        def update_test_results(n_clicks, symbol):
            if n_clicks > 0:
                return self.create_test_results(symbol)
            return None
    
    def run(self, debug=True):
        self.setup_layout()
        self.app.run(debug=debug)

def main():
    dashboard = Dashboard()
    dashboard.run()

if __name__ == "__main__":
    main() 