"""
NetGanesh Publishing - Global Macro & Multi-Asset Investor Matrix Engine
Author: Rajen B. Choudhari
Description: 
    Fully corrected Python script generating a 12-month landscape macro matrix 
    with perfectly padded/top-aligned cell text and weekly-sampled (52 points) 
    YTD charts for NASDAQ and Gold.
"""

import calendar
from datetime import datetime
import math
import holidays
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Flowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.graphics.shapes import Drawing, String, Rect
from reportlab.graphics.charts.linecharts import HorizontalLineChart
import yfinance as yf

# ==========================================
# 1. CONFIGURATION & REGIONAL PROFILES
# ==========================================
MARKET_CONFIGS = {
    "USA": {
        "name": "United States (Global Macro Matrix)",
        "indices": {"S&P": "^GSPC", "DOW": "^DJI", "NASDAQ": "^IXIC", "10Y": "^TNX"},
        "commodities_currencies": {"Gold": "GC=F", "Oil": "CL=F", "USD/INR": "INR=X", "USD/JPY": "JPY=X"},
        "holiday_country": "US"
    }
}

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
            # Allow 6pt total horizontal padding (3pt left margin) and 6pt vertical margin
            self._inner_w, self._inner_h = self.inner.wrap(self.width - 6, self.height - 6)
        return self.width, self.height
        
    def draw(self):
        self.canv.saveState()
        # Draw giant faint background date watermark
        self.canv.setFont("Helvetica-Bold", 42)
        self.canv.setFillColor(colors.HexColor('#F1F5F9')) # Soft professional grey
        self.canv.drawCentredString(self.width / 2.0, 16, self.day_num)
        self.canv.restoreState()
        
        # Draw inner content near the top with 3pt left padding
        if self.inner:
            self.inner.drawOn(self.canv, 3, self.height - self._inner_h - 3)


def fetch_yearly_market_data(region_key, year):
    """
    Fetches full-year daily market data and extracts weekly closing snapshots (~52 points) for robust charting.
    """
    config = MARKET_CONFIGS[region_key]
    print(f"[{region_key}] Fetching yearly market actuals for {year} via yfinance...")
    
    all_tickers = {**config["indices"], **config["commodities_currencies"]}
    yearly_data = {}
    weekly_closes = {asset: [] for asset in all_tickers.keys()}
    
    for label, symbol in all_tickers.items():
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(start=f"{year}-01-01", end=f"{year}-12-31")
            if df.empty:
                continue
            
            df['Prev_Close'] = df['Close'].shift(1)
            df['Change'] = df['Close'] - df['Prev_Close']
            
            # Daily matrix population
            for date_val, row in df.iterrows():
                close_val = row['Close']
                change_val = row['Change']
                if math.isnan(close_val):
                    continue
                
                m, d = date_val.month, date_val.day
                if m not in yearly_data:
                    yearly_data[m] = {}
                if d not in yearly_data[m]:
                    yearly_data[m][d] = {}
                
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
            
            # Weekly grouping for ~52 trend points
            df['Week'] = df.index.isocalendar().week
            df['Month'] = df.index.month
            
            w_points = []
            for _, group in df.groupby(df.index.isocalendar().week):
                if group.empty:
                    continue
                last_row = group.iloc[-1]
                close_val = last_row['Close']
                month_val = last_row.name.month
                if not math.isnan(close_val):
                    w_points.append({
                        'month': month_val,
                        'val': float(close_val)
                    })
            weekly_closes[label] = w_points
            
        except Exception as e:
            print(f"-> Error downloading data for {label}: {e}")
            
    return yearly_data, weekly_closes

def get_holiday_checker(region_key, year):
    country_code = MARKET_CONFIGS[region_key]["holiday_country"]
    return holidays.country_holidays(country_code, years=year)


# ==========================================
# 2. WEEKLY SAMPLED YTD TREND CHART BUILDER
# ==========================================
def create_single_asset_trend_drawing(weekly_data_list, asset_name, current_month_limit, title_text, width=370, height=200):
    """
    Builds a clean YTD trend chart using weekly closing points up to the current month, 
    with X-axis labels marking month boundaries.
    """
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
        d.add(String(width / 2, height / 2, f"Insufficient Data for {asset_name}", fontName="Helvetica", fontSize=9, textAnchor="middle", fillColor=colors.HexColor('#A0AEC0')))
        d.add(String(width / 2, height - 20, title_text, fontName="Helvetica-Bold", fontSize=10, textAnchor="middle", fillColor=colors.HexColor('#2D3748')))
        return d

    chart = HorizontalLineChart()
    chart.x = 45
    chart.y = 25
    chart.width = width - 60
    chart.height = height - 55
    
    chart.data = [points]
    chart.categoryAxis.categoryNames = active_labels
    chart.categoryAxis.labels.fontSize = 6
    chart.categoryAxis.labels.dy = -10
    
    chart.valueAxis.valueMin = min(points) * 0.95
    chart.valueAxis.valueMax = max(points) * 1.05
    chart.valueAxis.labels.fontSize = 6
    
    chart.lines[0].strokeColor = colors.HexColor('#2B6CB0') if asset_name == "NASDAQ" else colors.HexColor('#B7791F')
    chart.lines[0].strokeWidth = 1.5
    
    d.add(chart)
    d.add(String(width / 2, height - 15, title_text, fontName="Helvetica-Bold", fontSize=10, textAnchor="middle", fillColor=colors.HexColor('#2D3748')))
    return d


# ==========================================
# 3. MAIN PDF GENERATOR ENGINE
# ==========================================
def build_netganesh_macro_matrix(region_key="USA", year=2026, filename="NetGanesh_Global_Macro_Matrix_2026.pdf"):
    doc = SimpleDocTemplate(
        filename,
        pagesize=landscape(letter),
        rightMargin=14, leftMargin=14, topMargin=14, bottomMargin=14
    )
    
    story = []
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('MatrixTitle', parent=styles['Heading1'], fontSize=13, leading=16, alignment=1, textColor=colors.HexColor('#1A365D'))
    subtitle_style = ParagraphStyle('MatrixSub', parent=styles['Normal'], fontSize=8, leading=10, alignment=1, textColor=colors.HexColor('#4A5568'))
    cell_text_style = ParagraphStyle('CellText', parent=styles['Normal'], fontSize=4.6, leading=5.8, alignment=0)
    footer_style = ParagraphStyle('MatrixFooter', parent=styles['Italic'], fontSize=7, leading=9, alignment=1, textColor=colors.HexColor('#718096'))

    config = MARKET_CONFIGS[region_key]
    yearly_market_data, weekly_closes = fetch_yearly_market_data(region_key, year)
    holiday_list = get_holiday_checker(region_key, year)
    
    cal = calendar.Calendar(firstweekday=6) # Sunday start
    
    index_keys = list(config["indices"].keys())
    cc_keys = list(config["commodities_currencies"].keys())
    
    for month in range(1, 13):
        month_name = calendar.month_name[month]
        print(f"Building pages for {month_name} {year}...")
        
        # ----------------------------------------------------
        # PAGE 1: MONTHLY CALENDAR MATRIX GRID
        # ----------------------------------------------------
        story.append(Paragraph(f"<b>{month_name} {year} | {config['name']}</b>", title_style))
        story.append(Paragraph(f"Left: Equities & Treasuries ({', '.join(index_keys)}) | Right: Commodities & Currencies ({', '.join(cc_keys)})", subtitle_style))
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
                        
                        primary_asset = index_keys[0]
                        if primary_asset in d_metrics:
                            if d_metrics[primary_asset]["color"] == "GREEN":
                                bg_styles.append(('BACKGROUND', (col_idx, row_idx), (col_idx, row_idx), colors.HexColor('#F0FFF4')))
                            else:
                                bg_styles.append(('BACKGROUND', (col_idx, row_idx), (col_idx, row_idx), colors.HexColor('#FFF5F5')))
                    else:
                        if is_weekend:
                            bg_styles.append(('BACKGROUND', (col_idx, row_idx), (col_idx, row_idx), colors.HexColor('#F7FAFC')))
                    
                    # Wrap with custom Flowable for background watermark + top-aligned padded text
                    wrapped_cell = WatermarkedCell(day, cell_content, 122, 68)
                    row_cells.append(wrapped_cell)
                        
            table_data.append(row_cells)
            
        col_widths = [56, 122, 122, 122, 122, 122, 56]
        row_height = 78
        row_heights = [16] + [row_height] * len(month_weeks)
        
        cal_table = Table(table_data, colWidths=col_widths, rowHeights=row_heights)
        base_table_style = [
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2D3748')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E0')),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#A0AEC0')),
        ]
        cal_table.setStyle(TableStyle(base_table_style + bg_styles))
        
        story.append(cal_table)
        story.append(Spacer(1, 3))
        story.append(Paragraph(f"NetGanesh Publishing | Global Macro Matrix | Page {(month * 2) - 1} of 24", footer_style))
        story.append(PageBreak())
        
        # ----------------------------------------------------
        # PAGE 2: YTD TREND CHARTS (NASDAQ & GOLD)
        # ----------------------------------------------------
        story.append(Paragraph(f"<b>{month_name} {year} | YTD Macro Trend Analysis (NASDAQ & Gold)</b>", title_style))
        story.append(Paragraph(f"Weekly closing trajectories tracking technology equity momentum and safe-haven precious metals.", subtitle_style))
        story.append(Spacer(1, 10))
        
        nasdaq_weekly = weekly_closes.get("NASDAQ", [])
        gold_weekly = weekly_closes.get("Gold", [])

        chart_nasdaq = create_single_asset_trend_drawing(nasdaq_weekly, "NASDAQ", month, f"NASDAQ YTD Trend — Up to {month_name} {year}", width=370, height=220)
        chart_gold = create_single_asset_trend_drawing(gold_weekly, "Gold", month, f"Gold YTD Trend — Up to {month_name} {year}", width=370, height=220)
        
        analytics_table = Table([[chart_nasdaq, chart_gold]], colWidths=[382, 382])
        analytics_table.setStyle(TableStyle([
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('LEFTPADDING', (0,0), (-1,-1), 2),
            ('RIGHTPADDING', (0,0), (-1,-1), 2),
            ('TOPPADDING', (0,0), (-1,-1), 2),
            ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ]))
        
        story.append(analytics_table)
        story.append(Spacer(1, 15))
        story.append(Paragraph(f"Curated & Published by <b>NetGanesh Publishing</b> (Toronto, Ontario) | Page {month * 2} of 24", footer_style))
        
        if month < 12:
            story.append(PageBreak())
            
    doc.build(story)
    print(f"Successfully generated 24-page full-year matrix with weekly-sampled YTD charts: {filename}")

if __name__ == "__main__":
    build_netganesh_macro_matrix(region_key="USA", year=2026, filename="NetGanesh_Global_Macro_Matrix_2026.pdf")