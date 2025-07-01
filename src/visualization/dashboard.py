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
        
        # Configuration du thème
        self.app.layout = html.Div([
            # Contenu principal
            html.Div([
                # En-tête
                html.Div([
                    html.H1('🚀 Dashboard d\'Analyse et Prédiction de Portefeuille'),
                    html.P('Système intelligent de gestion de portefeuille avec IA', 
                           style={'color': '#7f8c8d', 'font-size': '1.1em', 'margin': '10px 0 0 0'})
                ], className='header'),
                
                # Onglets principaux
                html.Div([
                    html.Div([
                        html.Div('💼 Gestion des Wallets', className='tab active', id='tab-wallets'),
                        html.Div('📊 Analyse Technique', className='tab', id='tab-analysis'),
                        html.Div('🎯 Optimisation', className='tab', id='tab-optimization')
                    ], className='tabs'),
                    
                    # Contenu des onglets
                    html.Div(id='tab-content')
                ], className='card')
            ], className='main-container')
        ])
        
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
        """Crée la section de gestion des wallets avec un design moderne"""
        wallets = self.wallet_manager.list_wallets()
        
        return html.Div([
            # Métriques rapides
            html.Div([
                html.Div([
                    html.Div([
                        html.Div(f"{len(wallets)}", className='metric-value'),
                        html.Div('Wallets Actifs', className='metric-label')
                    ], className='metric-card'),
                    html.Div([
                        html.Div(f"${sum(w.get('current_capital', 0) for w in wallets):,.0f}", className='metric-value'),
                        html.Div('Capital Total', className='metric-label')
                    ], className='metric-card'),
                    html.Div([
                        html.Div(f"{sum(len(self.wallet_manager.get_wallet_positions(w['name'])) for w in wallets)}", className='metric-value'),
                        html.Div('Positions', className='metric-label')
                    ], className='metric-card')
                ], className='grid-container'),
                
                # Création de wallet
                html.Div([
                    html.H3('➕ Créer un nouveau wallet'),
                    html.Div([
                        html.Div([
                            html.Label('Nom du wallet'),
                            dcc.Input(id='new-wallet-name', type='text', placeholder='Mon Wallet')
                        ], className='input-field'),
                        html.Div([
                            html.Label('Capital initial ($)'),
                            dcc.Input(id='new-wallet-capital', type='number', placeholder='10000', value=10000)
                        ], className='input-field'),
                        html.Div([
                            html.Label('Profil de risque'),
                            dcc.Dropdown(
                                id='risk-profile-dropdown',
                                options=[
                                    {'label': '🛡️ Conservateur', 'value': 'conservative'},
                                    {'label': '⚖️ Modéré', 'value': 'moderate'},
                                    {'label': '🚀 Agressif', 'value': 'aggressive'}
                                ],
                                value='moderate'
                            )
                        ], className='input-field'),
                        html.Button('Créer Wallet', id='create-wallet-button', className='btn btn-primary')
                    ], className='input-group'),
                    html.Div(id='create-wallet-output')
                ], className='card'),
                
                # Sélection et gestion
                html.Div([
                    html.H3('📋 Gestion des positions'),
                    html.Div([
                        html.Div([
                            html.Label('Sélectionner un wallet'),
                            dcc.Dropdown(
                                id='wallet-dropdown',
                                options=[{'label': f"💰 {w['name']} (${w.get('current_capital', 0):,.0f})", 'value': w['name']} for w in wallets],
                                value=wallets[0]['name'] if wallets else None
                            )
                        ], className='input-field'),
                        html.Div([
                            html.Label('Symbole'),
                            dcc.Input(id='position-symbol', type='text', placeholder='AAPL')
                        ], className='input-field'),
                        html.Div([
                            html.Label('Type d\'ordre'),
                            html.Div([
                                html.Div([
                                    dcc.RadioItems(
                                        id='position-type',
                                        options=[
                                            {'label': '📈 Quantité d\'actions', 'value': 'quantity'},
                                            {'label': '💵 Montant en dollars', 'value': 'amount'}
                                        ],
                                        value='quantity'
                                    )
                                ], className='radio-group')
                            ])
                        ], className='input-field'),
                        html.Div([
                            html.Label('Valeur'),
                            dcc.Input(id='position-value', type='number', placeholder='100')
                        ], className='input-field'),
                        html.Div([
                            html.Button('🟢 Acheter', id='buy-button', className='btn btn-success'),
                            html.Button('🔴 Vendre', id='sell-button', className='btn btn-danger')
                        ], style={'display': 'flex', 'gap': '10px'})
                    ], className='input-group'),
                    html.Div(id='current-price-display'),
                    html.Div(id='position-output'),
                    
                    # Gestion automatique
                    html.Div([
                        html.H4('🤖 Gestion automatique'),
                        html.Div([
                            html.Div([
                                html.Label('Mode de gestion'),
                                dcc.RadioItems(
                                    id='auto-trading-mode',
                                    options=[
                                        {'label': '⏸️ Désactivé', 'value': 'off'},
                                        {'label': '🔄 Gestion partielle', 'value': 'partial'},
                                        {'label': '🚀 Gestion complète', 'value': 'full'}
                                    ],
                                    value='off'
                                )
                            ], className='radio-group'),
                            html.Button('Activer la gestion automatique', id='activate-auto-trading', className='btn btn-warning')
                        ]),
                        html.Div(id='auto-trading-status'),
                        dcc.Interval(
                            id='auto-trading-interval',
                            interval=5*60*1000,
                            n_intervals=0
                        )
                    ], style={'margin-top': '30px', 'padding': '20px', 'background': 'rgba(52, 152, 219, 0.1)', 'border-radius': '10px'}),
                    
                    # Alertes de risque
                    html.Div([
                        html.H4('⚠️ Alertes de risque'),
                        html.Div(id='risk-alerts')
                    ], style={'margin-top': '20px'}),
                    
                    # Affichage du wallet
                    html.Div(id='wallet-display')
                ], className='card')
            ])
        ])
    
    def create_analysis_section(self):
        """Crée la section d'analyse technique"""
        symbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'TSLA', 'NVDA', 'JPM', 'V', 'WMT']
        
        return html.Div([
            html.Div([
                html.H3('📈 Analyse technique'),
                html.Div([
                    html.Div([
                        html.Label('Sélectionner un actif'),
                        dcc.Dropdown(
                            id='symbol-dropdown',
                            options=[{'label': s, 'value': s} for s in symbols],
                            value=symbols[0]
                        )
                    ], className='input-field'),
                    html.Button('🔄 Actualiser', id='refresh-analysis', className='btn btn-primary')
                ], className='input-group'),
                
                # Prédiction
                html.Div(id='prediction-card'),
                
                # Graphiques
                html.Div([
                    dcc.Graph(id='price-chart'),
                    dcc.Graph(id='indicators-chart')
                ])
            ], className='card')
        ])
    
    def create_optimization_section(self):
        """Crée la section d'optimisation"""
        return html.Div([
            html.H3('🎯 Optimisation du portefeuille'),
            html.Div([
                dcc.Graph(id='portfolio-pie'),
                dcc.Graph(id='metrics-table')
            ])
        ], className='card')
    
    def create_wallet_display(self, wallet_name):
        """Crée l'affichage détaillé d'un wallet avec un design moderne"""
        if not wallet_name:
            return html.Div("Sélectionnez un wallet", className='alert alert-warning')
            
        wallet = self.wallet_manager.load_wallet(wallet_name)
        if not wallet:
            return html.Div("Wallet non trouvé", className='alert alert-danger')
            
        performance = self.wallet_manager.get_wallet_performance(wallet_name)
        positions = self.wallet_manager.get_wallet_positions(wallet_name)
        history = self.wallet_manager.get_wallet_history(wallet_name)
        
        # Métriques de performance
        performance_metrics = html.Div([
            html.Div([
                html.Div([
                    html.Div(f"{performance['total_return']:.2%}", className='metric-value'),
                    html.Div('Rendement Total', className='metric-label')
                ], className='metric-card'),
                html.Div([
                    html.Div(f"{performance['volatility']:.2%}", className='metric-value'),
                    html.Div('Volatilité', className='metric-label')
                ], className='metric-card'),
                html.Div([
                    html.Div(f"{performance['sharpe_ratio']:.2f}", className='metric-value'),
                    html.Div('Ratio de Sharpe', className='metric-label')
                ], className='metric-card')
            ], className='grid-container'),
            
            # Informations du wallet
            html.Div([
                html.H4(f"📊 Détails du wallet: {wallet_name}"),
                html.Div([
                    html.P(f"🕒 Créé le: {wallet['created_at']}"),
                    html.P(f"🎯 Profil de risque: {wallet['risk_profile']}"),
                    html.P(f"💰 Capital initial: ${wallet['initial_capital']:,.2f}"),
                    html.P(f"💵 Capital actuel: ${wallet['current_capital']:,.2f}")
                ], style={'background': 'rgba(52, 152, 219, 0.1)', 'padding': '15px', 'border-radius': '10px'})
            ])
        ])
        
        # Graphique de performance
        daily_values = pd.DataFrame(history['daily_values'])
        if not daily_values.empty:
            daily_values['date'] = pd.to_datetime(daily_values['date'])
            daily_values.set_index('date', inplace=True)
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=daily_values.index,
                y=daily_values['value'],
                name='Valeur du wallet',
                line=dict(color='#3498db', width=3)
            ))
            fig.update_layout(
                title='📈 Évolution de la valeur du wallet',
                xaxis_title='Date',
                yaxis_title='Valeur ($)',
                template='plotly_white',
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)'
            )
        else:
            fig = go.Figure()
        
        # Tableau des positions avec style moderne
        positions_table = go.Figure(data=[go.Table(
            header=dict(
                values=['Symbole', 'Secteur', 'Quantité', 'Prix d\'entrée', 'Prix actuel', 'Valeur', 'P&L', 'P&L %', 'Stop Loss', 'Take Profit'],
                fill_color='#3498db',
                font=dict(color='white', size=12),
                align='center'
            ),
            cells=dict(
                values=[
                    [p['symbol'] for p in positions],
                    [p['sector'] for p in positions],
                    [f"{p['quantity']:.2f}" for p in positions],
                    [f"${p['entry_price']:.2f}" for p in positions],
                    [f"${p['current_price']:.2f}" for p in positions],
                    [f"${p['position_value']:.2f}" for p in positions],
                    [f"${p['unrealized_pnl']:.2f}" for p in positions],
                    [f"{p['unrealized_pnl_pct']:.2%}" for p in positions],
                    [f"${p['stop_loss']:.2f}" for p in positions],
                    [f"${p['take_profit']:.2f}" for p in positions]
                ],
                fill_color='white',
                font=dict(size=11),
                align='center'
            )
        )])
        positions_table.update_layout(
            title='📋 Positions actuelles',
            template='plotly_white'
        )
        
        return html.Div([
            performance_metrics,
            dcc.Graph(figure=fig),
            dcc.Graph(figure=positions_table),
            
            # Historique des transactions
            html.Div([
                html.H4('📜 Historique des transactions'),
                html.Div([
                    html.Table([
                        html.Tr([
                            html.Th('Date'),
                            html.Th('Action'),
                            html.Th('Symbole'),
                            html.Th('Quantité'),
                            html.Th('Prix'),
                            html.Th('Total'),
                            html.Th('Profil de risque')
                        ], style={'background': '#3498db', 'color': 'white'})
                    ] + [
                        html.Tr([
                            html.Td(t['date']),
                            html.Td(t['action']),
                            html.Td(t['symbol']),
                            html.Td(f"{t['quantity']:.2f}"),
                            html.Td(f"${t['price']:.2f}"),
                            html.Td(f"${t['total']:.2f}"),
                            html.Td(t['risk_profile'])
                        ], style={'border-bottom': '1px solid #e0e6ed'}) for t in reversed(history['transactions'])
                    ], style={'width': '100%', 'border-collapse': 'collapse'})
                ], style={'max-height': '300px', 'overflow-y': 'auto'})
            ], className='card')
        ])
    
    def setup_layout(self):
        # Callbacks pour les onglets
        @self.app.callback(
            Output('tab-content', 'children'),
            [Input('tab-wallets', 'n_clicks'),
             Input('tab-analysis', 'n_clicks'),
             Input('tab-optimization', 'n_clicks')]
        )
        def switch_tab(wallets_clicks, analysis_clicks, optimization_clicks):
            ctx = dash.callback_context
            if not ctx.triggered:
                return self.create_wallet_management_section()
            
            button_id = ctx.triggered[0]['prop_id'].split('.')[0]
            
            if button_id == 'tab-wallets':
                return self.create_wallet_management_section()
            elif button_id == 'tab-analysis':
                return self.create_analysis_section()
            elif button_id == 'tab-optimization':
                return self.create_optimization_section()
            
            return self.create_wallet_management_section()
        
        # Callbacks existants avec améliorations visuelles
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
                    return html.Div(f"✅ Wallet {name} créé avec succès!", className='alert alert-success')
                except Exception as e:
                    return html.Div(f"❌ Erreur: {str(e)}", className='alert alert-danger')
            return ""
        
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
                    html.Span(f"💵 Prix actuel de {symbol}: ", style={'font-weight': 'bold'}),
                    html.Span(f"${current_price:.2f}", style={'color': '#27ae60', 'font-size': '1.2em'})
                ], className='alert alert-success')
            except Exception as e:
                return html.Div(f"❌ Erreur: {str(e)}", className='alert alert-danger')
        
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
                return html.Div("⚠️ Veuillez remplir tous les champs", className='alert alert-warning')
                
            ctx = dash.callback_context
            if not ctx.triggered:
                return ""
                
            button_id = ctx.triggered[0]['prop_id'].split('.')[0]
            
            try:
                current_price = self.wallet_manager.get_current_price(symbol)
                
                if position_type == 'amount':
                    quantity = value / current_price
                else:
                    quantity = value
                    
                if button_id == 'buy-button':
                    self.wallet_manager.add_position(wallet_name, symbol, quantity, current_price)
                    return html.Div(f"🟢 Achat de {quantity:.2f} {symbol} au prix de ${current_price:.2f}", className='alert alert-success')
                elif button_id == 'sell-button':
                    self.wallet_manager.remove_position(wallet_name, symbol, quantity)
                    return html.Div(f"🔴 Vente de {quantity:.2f} {symbol} au prix de ${current_price:.2f}", className='alert alert-success')
            except Exception as e:
                return html.Div(f"❌ Erreur: {str(e)}", className='alert alert-danger')
        
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
                return html.Div("⚠️ Sélectionnez un wallet", className='alert alert-warning'), True
                
            ctx = dash.callback_context
            if not ctx.triggered:
                return html.Div("⏸️ Gestion automatique désactivée", className='status-indicator status-inactive'), True
                
            trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
            
            if trigger_id == 'activate-auto-trading':
                if mode == 'off':
                    return html.Div("⏸️ Gestion automatique désactivée", className='status-indicator status-inactive'), True
                else:
                    return html.Div(f"🟢 Gestion automatique activée ({mode})", className='status-indicator status-active'), False
            elif trigger_id == 'auto-trading-interval':
                try:
                    if mode == 'partial':
                        self.wallet_manager.optimize_existing_positions(wallet_name)
                    elif mode == 'full':
                        self.wallet_manager.optimize_full_portfolio(wallet_name)
                    return html.Div(f"🔄 Dernière mise à jour: {datetime.now().strftime('%H:%M:%S')}", className='alert alert-success'), False
                except Exception as e:
                    return html.Div(f"❌ Erreur lors de la mise à jour: {str(e)}", className='alert alert-danger'), False
                
            return html.Div("⏸️ Gestion automatique désactivée", className='status-indicator status-inactive'), True
        
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
                return html.Div("⚠️ Sélectionnez un wallet", className='alert alert-warning')
            
            alerts = self.wallet_manager.check_risk_alerts(wallet_name)
            if not alerts:
                return html.Div("✅ Aucune alerte de risque", className='alert alert-success')
            
            return html.Div([
                html.H4('⚠️ Alertes actives:'),
                html.Div([
                    html.Div([
                        html.Strong(f"{alert['type']} - {alert['symbol']}"),
                        html.Br(),
                        f"Prix actuel: ${alert['current_price']:.2f}",
                        html.Br(),
                        f"{'Stop Loss' if alert['type'] == 'STOP_LOSS' else 'Take Profit'}: ${alert['stop_loss'] if alert['type'] == 'STOP_LOSS' else alert['take_profit']:.2f}"
                    ], className='alert alert-danger') for alert in alerts
                ])
            ])
    
    def run(self, debug=True):
        self.setup_layout()
        self.app.run(debug=debug)

def main():
    dashboard = Dashboard()
    dashboard.run()

if __name__ == "__main__":
    main() 