"""
NetGanesh Publishing - Personalized Portfolio & Global Macro Matrix Engine
Author: Rajen B. Choudhari
Description: 
    Upgraded script generating a 12-month landscape matrix incorporating personal 
    portfolio valuations from Excel, two-column day cells, watermarked dates, 
    up/down arrows, and a 2x2 analytical chart grid (Portfolio, NASDAQ, Gold, 
    and Comparative %-Change Bar Chart).
"""

import os
import calendar
from datetime import datetime
import math
import holidays
import pandas as pd
import yfinance as yf

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Flowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.graphics.shapes import Drawing, String, Rect
from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics.charts.barcharts import VerticalBarChart

# ==========================================
# 1. CONFIGURATION & PORTFOLIO SETUP
# ==========================================
PDF_FILENAME = "NetGanesh_Personal_Portfolio_Matrix_2026.pdf"
EXCEL_FILENAME = "portfolio.xlsx"

MACRO_INDICES = {"S&P": "^GSPC", "DOW": "^DJI", "NASDAQ": "^IXIC", "10Y": "^TNX"}
COMMODITIES_CURRENCIES = {"Gold": "GC=F", "Oil": "CL=F", "USD/INR": "INR=X", "USD/JPY": "JPY=X"}

class WatermarkedCell(Flowable):
    """
    Custom Flowable that renders a giant faint background date watermark 
    and draws the inner table/text padded from the left border and anchored at the top.
    """
    def __init__(self, day_num, inner_flowable, width, height):
        super().__init__()
        self.day_num = str(day_num)
        self.inner = inner_flowable
        self.width = width
        self.height = height
        self._inner_w = 0
        self._inner_h = 0
        
    def wrap(self, availWidth, availHeight):
        if self.inner:
            self._inner_w, self._inner_h = self.inner.wrap(self.width - 6, self.height - 6)
        return self.width, self.height
        
    def draw(self):
        self.canv.saveState()
        self.canv.setFont("Helvetica-Bold", 42)
        self.canv.setFillColor(colors.HexColor('#F1F5F9'))
        self.canv.drawCentredString(self.width / 2.0, 16, self.day_num)
        self.canv.restoreState()
        
        if self.inner:
            self.inner.drawOn(self.canv, 3, self.height - self._inner_h - 3)


def load_portfolio_holdings():
    if os.path.exists(EXCEL_FILENAME):
        df_port = pd.read_excel(EXCEL_FILENAME)
        return dict(zip(df_port['Ticker'].astype(str).str.strip(), df_port['Quantity'].astype(float)))
    return {"AAPL": 10, "MSFT": 5, "NVDA": 15, "SPY": 8}


def fetch_yearly_market_and_portfolio_data(year):
    portfolio_holdings = load_portfolio_holdings()
    all_market_tickers = {**MACRO_INDICES, **COMMODITIES_CURRENCIES}
    all_tickers = list(portfolio_holdings.keys()) + list(all_market_tickers.values())
    
    print(f"Fetching yearly market & portfolio actuals for {year} via yfinance...")
    
    data = yf.download(all_tickers, start=f"{year}-01-01", end=f"{year}-12-31", progress=False)
    
    if isinstance(data.columns, pd.MultiIndex):
        prices = data['Close']
    else:
        prices = data[['Close']]

    prices = prices.ffill().bfill()

    # Compute Total Portfolio Value Series
    portfolio_value_series = pd.Series(0.0, index=prices.index)
    for ticker, qty in portfolio_holdings.items():
        if ticker in prices.columns:
            portfolio_value_series += prices[ticker] * qty
            
    prices['PORTFOLIO'] = portfolio_value_series
    prices['PORTFOLIO_Prev'] = prices['PORTFOLIO'].shift(1)
    prices['PORTFOLIO_Change'] = prices['PORTFOLIO'] - prices['PORTFOLIO_Prev']

    yearly_data = {}
    weekly_closes = {asset: [] for asset in list(all_market_tickers.keys()) + ["PORTFOLIO"]}
    
    for date_val, row in prices.iterrows():
        m, d = date_val.month, date_val.day
        if m not in yearly_data:
            yearly_data[m] = {}
        if d not in yearly_data[m]:
            yearly_data[m][d] = {}
            
        p_val = row['PORTFOLIO']
        p_change = row['PORTFOLIO_Change']
        p_is_up = True if (not math.isnan(p_change) and p_change >= 0) else False
        yearly_data[m][d]["PORTFOLIO"] = {
            "val": f"${p_val:,.0f}", 
            "color": "GREEN" if p_is_up else "RED",
            "raw": float(p_val)
        }
        
        for label, symbol in all_market_tickers.items():
            if symbol in prices.columns:
                close_val = row[symbol]
                prev_val = prices[symbol].shift(1).loc[date_val] if date_val in prices.index else close_val
                change_val = close_val - prev_val
                is_up = True if (not math.isnan(change_val) and change_val >= 0) else False
                color = "GREEN" if is_up else "RED"
                
                if "Yield" in label or "10Y" in label:
                    val_str = f"{close_val:.2f}%"
                elif label in ["Gold"]:
                    val_str = f"${close_val:,.0f}"
                elif label in ["Oil"]:
                    val_str = f"${close_val:.2f}"
                elif "/" in label:
                    val_str = f"{close_val:.2f}"
                else:
                    val_str = f"{close_val:,.0f}"
                    
                yearly_data[m][d][label] = {"val": val_str, "color": color, "raw": float(close_val)}

    for label in weekly_closes.keys():
        sym = "PORTFOLIO" if label == "PORTFOLIO" else all_market_tickers.get(label)
        if sym in prices.columns:
            s = prices[sym].resample('W').last()
            w_points = []
            for dt, val in s.items():
                if not math.isnan(val):
                    w_points.append({'month': dt.month, 'val': float(val)})
            weekly_closes[label] = w_points

    return yearly_data, weekly_closes, prices


# ==========================================
# 2. ANALYTICAL CHART BUILDERS (2x2 GRID)
# ==========================================
def create_single_asset_trend_drawing(weekly_data_list, asset_name, current_month_limit, title_text, width=370, height=130):
    d = Drawing(width, height)
    d.add(Rect(0, 0, width, height, fillColor=colors.HexColor('#FAFCFC'), strokeColor=colors.HexColor('#CBD5E0'), strokeWidth=0.5, rx=4, ry=4))
    
    month_names_abbr = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    
    points = []
    active_labels = []
    last_seen_month = -1
    
    for p in weekly_data_list:
        if p['month'] <= current_month_limit:
            points.append(p['val'])
            m = p['month']
            if m != last_seen_month:
                active_labels.append(month_names_abbr[m - 1])
                last_seen_month = m
            else:
                active_labels.append("")
            
    if len(points) < 2:
        d.add(String(width / 2, height / 2, f"Insufficient Data for {asset_name}", fontName="Helvetica", fontSize=8, textAnchor="middle", fillColor=colors.HexColor('#A0AEC0')))
        d.add(String(width / 2, height - 15, title_text, fontName="Helvetica-Bold", fontSize=9, textAnchor="middle", fillColor=colors.HexColor('#2D3748')))
        return d

    chart = HorizontalLineChart()
    chart.x = 40
    chart.y = 20
    chart.width = width - 50
    chart.height = height - 40
    
    chart.data = [points]
    chart.categoryAxis.categoryNames = active_labels
    chart.categoryAxis.labels.fontSize = 5
    chart.categoryAxis.labels.dy = -8
    
    chart.valueAxis.valueMin = min(points) * 0.95
    chart.valueAxis.valueMax = max(points) * 1.05
    chart.valueAxis.labels.fontSize = 5
    
    stroke_clr = colors.HexColor('#0369A1') if asset_name == "PORTFOLIO" else (colors.HexColor('#2B6CB0') if asset_name == "NASDAQ" else colors.HexColor('#B7791F'))
    chart.lines[0].strokeColor = stroke_clr
    chart.lines[0].strokeWidth = 1.2
    
    d.add(chart)
    d.add(String(width / 2, height - 12, title_text, fontName="Helvetica-Bold", fontSize=9, textAnchor="middle", fillColor=colors.HexColor('#2D3748')))
    return d


def create_comparative_barchart(prices_df, current_month_limit, title_text, width=370, height=130):
    d = Drawing(width, height)
    d.add(Rect(0, 0, width, height, fillColor=colors.HexColor('#FAFCFC'), strokeColor=colors.HexColor('#CBD5E0'), strokeWidth=0.5, rx=4, ry=4))
    
    # Filter prices up to current month limit
    filtered_df = prices_df[prices_df.index.month <= current_month_limit]
    if filtered_df.empty:
        return d
        
    start_row = filtered_df.iloc[0]
    end_row = filtered_df.iloc[-1]
    
    assets = [
        ("Portfolio", "PORTFOLIO"),
        ("Gold", "GC=F"),
        ("Oil", "CL=F"),
        ("NASDAQ", "^IXIC"),
        ("Bond Yield", "^TNX")
    ]
    
    pct_changes = []
    category_names = []
    
    for label, col in assets:
        if col in filtered_df.columns:
            start_val = start_row[col]
            end_val = end_row[col]
            if start_val and not math.isnan(start_val) and start_val != 0:
                pct = ((end_val - start_val) / start_val) * 100.0
                pct_changes.append(round(pct, 2))
                category_names.append(label)
                
    if not pct_changes:
        return d

    bc = VerticalBarChart()
    bc.x = 35
    bc.y = 20
    bc.width = width - 45
    bc.height = height - 40
    bc.data = [pct_changes]
    bc.categoryAxis.categoryNames = category_names
    bc.categoryAxis.labels.fontSize = 6
    bc.categoryAxis.labels.dy = -8
    bc.valueAxis.labels.fontSize = 5
    bc.bars[0].fillColor = colors.HexColor('#0284C7')
    
    d.add(bc)
    d.add(String(width / 2, height - 12, title_text, fontName="Helvetica-Bold", fontSize=9, textAnchor="middle", fillColor=colors.HexColor('#2D3748')))
    return d


# ==========================================
# 3. MAIN PDF GENERATOR ENGINE
# ==========================================
def build_netganesh_portfolio_matrix(year=2026, filename=PDF_FILENAME):
    doc = SimpleDocTemplate(
        filename,
        pagesize=landscape(letter),
        rightMargin=14, leftMargin=14, topMargin=14, bottomMargin=14
    )
    
    story = []
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('MatrixTitle', parent=styles['Heading1'], fontSize=13, leading=16, alignment=1, textColor=colors.HexColor('#0F172A'))
    subtitle_style = ParagraphStyle('MatrixSub', parent=styles['Normal'], fontSize=8, leading=10, alignment=1, textColor=colors.HexColor('#475569'))
    cell_text_style = ParagraphStyle('CellText', parent=styles['Normal'], fontSize=4.4, leading=5.6, alignment=0)
    footer_style = ParagraphStyle('MatrixFooter', parent=styles['Italic'], fontSize=7, leading=9, alignment=1, textColor=colors.HexColor('#64748B'))

    yearly_market_data, weekly_closes, prices_df = fetch_yearly_market_and_portfolio_data(year)
    holiday_list = holidays.country_holidays('US', years=year)
    
    cal = calendar.Calendar(firstweekday=6)
    index_keys = list(MACRO_INDICES.keys())
    cc_keys = list(COMMODITIES_CURRENCIES.keys())
    
    for month in range(1, 13):
        month_name = calendar.month_name[month]
        print(f"Building portfolio & macro pages for {month_name} {year}...")
        
        # ----------------------------------------------------
        # PAGE 1: CALENDAR MATRIX GRID WITH PORTFOLIO VALUES
        # ----------------------------------------------------
        story.append(Paragraph(f"<b>{month_name} {year} | NetGanesh Personal Wealth & Macro Matrix</b>", title_style))
        story.append(Paragraph(f"Left Column: Portfolio & Key Equities ({', '.join(index_keys)}) | Right Column: Commodities & Currencies ({', '.join(cc_keys)})", subtitle_style))
        story.append(Spacer(1, 4))
        
        month_market = yearly_market_data.get(month, {})
        table_data = [["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]]
        month_weeks = cal.monthdayscalendar(year, month)
        bg_styles = []
        
        for row_idx, week in enumerate(month_weeks, start=1):
            row_cells = []
            for col_idx, day in enumerate(week):
                if day == 0:
                    row_cells.append("")
                else:
                    date_obj = datetime(year, month, day)
                    is_weekend = col_idx in [0, 6]
                    is_holiday = date_obj in holiday_list
                    
                    cell_content = None
                    
                    if is_holiday:
                        h_name = holiday_list.get(date_obj)
                        cell_content = Paragraph(f"<font color='#C53030'><b>[CLOSED]</b></font><br/><font color='#718096'><b>{h_name}</b></font>", cell_text_style)
                        bg_styles.append(('BACKGROUND', (col_idx, row_idx), (col_idx, row_idx), colors.HexColor('#EDF2F7')))
                    elif day in month_market:
                        d_metrics = month_market[day]
                        left_lines, right_lines = [], []
                        
                        if "PORTFOLIO" in d_metrics:
                            p_info = d_metrics["PORTFOLIO"]
                            p_arrow = "▲" if p_info["color"] == "GREEN" else "▼"
                            p_color = "#0369A1" if p_info["color"] == "GREEN" else "#991B1B"
                            left_lines.append(f"<b>PORT: <font color='{p_color}'>{p_info['val']} {p_arrow}</font></b>")
                        
                        for asset in index_keys:
                            if asset in d_metrics:
                                info = d_metrics[asset]
                                v, c = info["val"], info["color"]
                                arrow = "▲" if c == "GREEN" else "▼"
                                color_code = "#22543D" if c == "GREEN" else "#742A2A"
                                left_lines.append(f"{asset}: <font color='{color_code}'><b>{v} {arrow}</b></font>")
                                
                        for asset in cc_keys:
                            if asset in d_metrics:
                                info = d_metrics[asset]
                                v, c = info["val"], info["color"]
                                arrow = "▲" if c == "GREEN" else "▼"
                                color_code = "#22543D" if c == "GREEN" else "#742A2A"
                                right_lines.append(f"{asset}: <font color='{color_code}'><b>{v} {arrow}</b></font>")
                        
                        inner_table = Table([[
                            Paragraph("<br/>".join(left_lines), cell_text_style),
                            Paragraph("<br/>".join(right_lines), cell_text_style)
                        ]], colWidths=[58, 54])
                        
                        inner_table.setStyle(TableStyle([
                            ('VALIGN', (0,0), (-1,-1), 'TOP'),
                            ('LEFTPADDING', (0,0), (-1,-1), 0),
                            ('RIGHTPADDING', (0,0), (-1,-1), 0),
                            ('TOPPADDING', (0,0), (-1,-1), 0),
                            ('BOTTOMPADDING', (0,0), (-1,-1), 0),
                        ]))
                        cell_content = inner_table
                        
                        if "PORTFOLIO" in d_metrics:
                            if d_metrics["PORTFOLIO"]["color"] == "GREEN":
                                bg_styles.append(('BACKGROUND', (col_idx, row_idx), (col_idx, row_idx), colors.HexColor('#F0FFF4')))
                            else:
                                bg_styles.append(('BACKGROUND', (col_idx, row_idx), (col_idx, row_idx), colors.HexColor('#FFF5F5')))
                    else:
                        if is_weekend:
                            bg_styles.append(('BACKGROUND', (col_idx, row_idx), (col_idx, row_idx), colors.HexColor('#F7FAFC')))
                    
                    wrapped_cell = WatermarkedCell(day, cell_content, 122, 68)
                    row_cells.append(wrapped_cell)
                        
            table_data.append(row_cells)
            
        col_widths = [56, 122, 122, 122, 122, 122, 56]
        row_height = 78
        row_heights = [16] + [row_height] * len(month_weeks)
        
        cal_table = Table(table_data, colWidths=col_widths, rowHeights=row_heights)
        base_table_style = [
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E293B')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E0')),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#94A3B8')),
        ]
        cal_table.setStyle(TableStyle(base_table_style + bg_styles))
        
        story.append(cal_table)
        story.append(Spacer(1, 3))
        story.append(Paragraph(f"NetGanesh Publishing | Personal Wealth Matrix | Page {(month * 2) - 1} of 24", footer_style))
        story.append(PageBreak())
        
        # ----------------------------------------------------
        # PAGE 2: 2x2 ANALYTICAL CHART GRID (4 CHARTS)
        # ----------------------------------------------------
        story.append(Paragraph(f"<b>{month_name} {year} | Portfolio & Macro Performance Analytics</b>", title_style))
        story.append(Paragraph(f"Comprehensive YTD multi-asset trajectory tracking and relative percentage performance benchmarks.", subtitle_style))
        story.append(Spacer(1, 6))
        
        portfolio_weekly = weekly_closes.get("PORTFOLIO", [])
        nasdaq_weekly = weekly_closes.get("NASDAQ", [])
        gold_weekly = weekly_closes.get("Gold", [])

        chart_portfolio = create_single_asset_trend_drawing(portfolio_weekly, "PORTFOLIO", month, f"Portfolio Trajectory — {month_name} {year}", width=375, height=135)
        chart_nasdaq = create_single_asset_trend_drawing(nasdaq_weekly, "NASDAQ", month, f"NASDAQ YTD Trend — {month_name} {year}", width=375, height=135)
        chart_gold = create_single_asset_trend_drawing(gold_weekly, "Gold", month, f"Gold YTD Trend — {month_name} {year}", width=375, height=135)
        chart_barplot = create_comparative_barchart(prices_df, month, f"YTD % Change: Portfolio vs. Assets — {month_name} {year}", width=375, height=135)
        
        analytics_table = Table([
            [chart_portfolio, chart_nasdaq],
            [chart_gold, chart_barplot]
        ], colWidths=[382, 382])
        
        analytics_table.setStyle(TableStyle([
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('LEFTPADDING', (0,0), (-1,-1), 1),
            ('RIGHTPADDING', (0,0), (-1,-1), 1),
            ('TOPPADDING', (0,0), (-1,-1), 2),
            ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ]))
        
        story.append(analytics_table)
        story.append(Spacer(1, 8))
        story.append(Paragraph(f"Curated & Published by <b>NetGanesh Publishing</b> (Toronto, Ontario) | Page {month * 2} of 24", footer_style))
        
        if month < 12:
            story.append(PageBreak())
            
    doc.build(story)
    print(f"Successfully generated 24-page portfolio matrix with 2x2 analytics charts: {filename}")

if __name__ == "__main__":
    build_netganesh_portfolio_matrix(year=2026, filename=PDF_FILENAME)