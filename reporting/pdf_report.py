"""PDF audit report generation using reportlab."""

import os

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from config import INITIAL_CAPITAL, REPORTS_DIR, TARGET_ALLOCATION
from utils.time import utc_now


class PDFReporter:
    """Generate audit-grade PDF reports for rebalancing cycles."""

    def __init__(self, reports_dir: str = REPORTS_DIR):
        self.reports_dir = reports_dir
        os.makedirs(reports_dir, exist_ok=True)
        self.styles = getSampleStyleSheet()
        self._add_custom_styles()

    def _add_custom_styles(self):
        self.styles.add(ParagraphStyle(name="SectionHeader", fontSize=13, fontName="Helvetica-Bold", spaceAfter=6, textColor=colors.HexColor("#1a365d")))
        self.styles.add(ParagraphStyle(name="SubHeader", fontSize=10, fontName="Helvetica-Bold", spaceAfter=4, textColor=colors.HexColor("#2d3748")))
        self.styles.add(ParagraphStyle(name="Body", fontSize=9, fontName="Helvetica", leading=14))
        self.styles.add(ParagraphStyle(name="Alert", fontSize=9, fontName="Helvetica-Bold", textColor=colors.HexColor("#c53030")))

    def generate(self, portfolio: dict, prices: dict, trades: list[dict], market_data: dict, cycle_id: str) -> str:
        filename = os.path.join(self.reports_dir, f"report_{cycle_id}.pdf")
        doc = SimpleDocTemplate(filename, pagesize=A4, rightMargin=2 * cm, leftMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm)
        story = []
        story.extend(self._build_header(cycle_id))
        story.extend(self._build_executive_summary(portfolio, prices))
        story.extend(self._build_allocation(portfolio, prices))
        story.extend(self._build_decision_log(trades))
        story.extend(self._build_risk_metrics(market_data))
        story.extend(self._build_performance_attribution(portfolio, trades))
        story.extend(self._build_anomaly_flags(trades, market_data))
        doc.build(story)
        return filename

    def _build_header(self, cycle_id: str) -> list:
        return [
            Paragraph("Prediction Wallet - Audit Report", self.styles["Title"]),
            Paragraph(f"Generated: {utc_now().strftime('%Y-%m-%d %H:%M UTC')} | Cycle: {cycle_id}", self.styles["Body"]),
            HRFlowable(width="100%", thickness=1, color=colors.HexColor("#1a365d")),
            Spacer(1, 0.4 * cm),
        ]

    def _build_executive_summary(self, portfolio: dict, prices: dict) -> list:
        positions = portfolio.get("positions", {})
        cash = portfolio.get("cash", 0.0)
        peak = portfolio.get("peak_value", INITIAL_CAPITAL)
        market_value = sum(qty * prices.get(t, 0) for t, qty in positions.items())
        total = market_value + cash
        pnl = total - INITIAL_CAPITAL
        pnl_pct = pnl / INITIAL_CAPITAL if INITIAL_CAPITAL > 0 else 0
        drawdown = (total - peak) / peak if peak > 0 else 0
        data = [
            ["Metric", "Value"],
            ["Total Portfolio Value", f"${total:,.2f}"],
            ["Cash", f"${cash:,.2f}"],
            ["Market Value", f"${market_value:,.2f}"],
            ["Initial Capital", f"${INITIAL_CAPITAL:,.2f}"],
            ["Total P&L", f"${pnl:+,.2f} ({pnl_pct:+.1%})"],
            ["Peak Value", f"${peak:,.2f}"],
            ["Drawdown from Peak", f"{drawdown:.2%}"],
        ]
        table = Table(data, colWidths=[7 * cm, 7 * cm])
        table.setStyle(self._summary_table_style())
        return [Paragraph("1. Executive Summary", self.styles["SectionHeader"]), table, Spacer(1, 0.5 * cm)]

    def _build_allocation(self, portfolio: dict, prices: dict) -> list:
        positions = portfolio.get("positions", {})
        cash = portfolio.get("cash", 0.0)
        total = cash + sum(qty * prices.get(t, 0) for t, qty in positions.items())
        data = [["Ticker", "Qty", "Price", "Value", "Current %", "Target %", "Drift"]]
        for ticker, target_wt in TARGET_ALLOCATION.items():
            qty = positions.get(ticker, 0)
            price = prices.get(ticker, 0)
            value = qty * price
            current_wt = value / total if total > 0 else 0
            data.append([ticker, f"{qty:.4f}", f"${price:.2f}", f"${value:,.0f}", f"{current_wt:.1%}", f"{target_wt:.1%}", f"{current_wt - target_wt:+.1%}"])
        table = Table(data, colWidths=[2 * cm, 2 * cm, 2.5 * cm, 2.5 * cm, 2 * cm, 2 * cm, 2 * cm])
        table.setStyle(self._data_table_style())
        return [Paragraph("2. Current vs Target Allocation", self.styles["SectionHeader"]), table, Spacer(1, 0.5 * cm)]

    def _build_decision_log(self, trades: list[dict]) -> list:
        if not trades:
            return [Paragraph("3. Decision Log", self.styles["SectionHeader"]), Paragraph("No trades executed this cycle.", self.styles["Body"]), Spacer(1, 0.3 * cm)]
        recent = [t for t in trades if "trade_id" in t][-50:]
        data = [["Time", "Ticker", "Action", "Qty", "Fill Price", "Cost", "Reason"]]
        for trade in recent:
            data.append([
                trade.get("timestamp", "")[:16],
                trade.get("ticker", ""),
                trade.get("action", "").upper(),
                f"{trade.get('quantity', 0):.4f}",
                f"${trade.get('fill_price', 0):.2f}",
                f"${abs(trade.get('cost', 0)):,.0f}",
                trade.get("reason", "")[:60],
            ])
        table = Table(data, colWidths=[2.5 * cm, 1.8 * cm, 1.5 * cm, 1.8 * cm, 2.2 * cm, 2 * cm, 5.2 * cm])
        table.setStyle(self._data_table_style())
        return [Paragraph("3. Decision Log", self.styles["SectionHeader"]), table, Spacer(1, 0.5 * cm)]

    def _build_risk_metrics(self, market_data: dict) -> list:
        if not market_data:
            return [Paragraph("4. Risk Metrics", self.styles["SectionHeader"]), Paragraph("No market data available.", self.styles["Body"]), Spacer(1, 0.3 * cm)]
        data = [["Ticker", "Last Price", "Vol 30d", "YTD Return", "Sharpe"]]
        for ticker, metrics in market_data.items():
            if not metrics or "error" in metrics:
                continue
            data.append([ticker, f"${metrics.get('last_price', 0):.2f}", f"{metrics.get('volatility_30d', 0):.1%}", f"{metrics.get('ytd_return', 0):+.1%}", f"{metrics.get('sharpe', 0):.2f}"])
        table = Table(data, colWidths=[3 * cm, 3 * cm, 3 * cm, 3 * cm, 3 * cm])
        table.setStyle(self._data_table_style())
        return [Paragraph("4. Risk Metrics", self.styles["SectionHeader"]), table, Spacer(1, 0.5 * cm)]

    def _build_performance_attribution(self, portfolio: dict, trades: list[dict]) -> list:
        history = portfolio.get("history", [])
        if not history or len(history) < 2:
            return [Paragraph("5. Performance Attribution", self.styles["SectionHeader"]), Paragraph("Insufficient history for performance attribution.", self.styles["Body"]), Spacer(1, 0.3 * cm)]
        try:
            import pandas as pd
            from engine.performance import annualized_return, cumulative_return, max_drawdown, sharpe_ratio, transaction_costs_total, turnover

            hist_list = [{"date": h.get("date", ""), "total_value": h["total_value"]} for h in history]
            values = pd.Series([h["total_value"] for h in history])
            daily_returns = values.pct_change().dropna()
            cum_ret_gross = cumulative_return(hist_list)
            costs = transaction_costs_total(trades)
            net_final = history[-1]["total_value"] - costs
            net_start = history[0]["total_value"]
            cum_ret_net = (net_final - net_start) / net_start if net_start > 0 else 0.0
            table = Table(
                [
                    ["Metric", "Gross", "Net"],
                    ["Cumulative Return", f"{cum_ret_gross:+.2%}", f"{cum_ret_net:+.2%}"],
                    ["Annualized Return", f"{annualized_return(hist_list):+.2%}", "-"],
                    ["Sharpe Ratio", f"{sharpe_ratio(daily_returns):.2f}", "-"],
                    ["Max Drawdown", f"{max_drawdown(hist_list):.2%}", "-"],
                    ["Annualized Turnover", f"{turnover(trades, float(values.mean())):.2%}", "-"],
                    ["Transaction Costs", "-", f"${costs:,.2f}"],
                    ["Cost Drag", "-", f"{cum_ret_gross - cum_ret_net:.2%}"],
                ],
                colWidths=[7 * cm, 4 * cm, 4 * cm],
            )
            table.setStyle(self._data_table_style())
            return [Paragraph("5. Performance Attribution", self.styles["SectionHeader"]), table, Spacer(1, 0.5 * cm)]
        except Exception as exc:
            return [Paragraph("5. Performance Attribution", self.styles["SectionHeader"]), Paragraph(f"Could not compute attribution: {exc}", self.styles["Body"]), Spacer(1, 0.5 * cm)]

    def _build_anomaly_flags(self, trades: list[dict], market_data: dict) -> list:
        flags = []
        for ticker, metrics in market_data.items():
            vol = metrics.get("volatility_30d", 0)
            if vol > 0.4:
                flags.append(f"{ticker}: high volatility {vol:.1%} (>40% annualized)")
        for trade in trades:
            if abs(trade.get("cost", 0)) > 10_000:
                flags.append(f"Large trade: {trade.get('action', '').upper()} {trade.get('ticker')} ${abs(trade.get('cost', 0)):,.0f}")
        elements = [Paragraph("6. Anomaly Flags", self.styles["SectionHeader"])]
        if flags:
            for flag in flags:
                elements.append(Paragraph(flag, self.styles["Alert"]))
                elements.append(Spacer(1, 0.15 * cm))
        else:
            elements.append(Paragraph("No anomalies detected.", self.styles["Body"]))
        elements.append(Spacer(1, 0.3 * cm))
        return elements

    def _summary_table_style(self) -> TableStyle:
        return TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a365d")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#ebf8ff")]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#bee3f8")),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ])

    def _data_table_style(self) -> TableStyle:
        return TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2d3748")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7fafc")]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("WORDWRAP", (0, 0), (-1, -1), True),
        ])
