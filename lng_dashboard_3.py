#!/usr/bin/env python3
"""
US LNG & Natural Gas Market Dashboard - Simplified
Shows Henry Hub prices (10-year history) and US LNG exports
"""

import requests
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import webbrowser
import os

# EIA API Configuration
API_KEY = 'tb5PBlfspIj7G3WJMBuvFvJNo2EhRBGeB9vzU6xx'
PRICE_URL = 'https://api.eia.gov/v2/natural-gas/pri/fut/data/'
EXPORT_URL = 'https://api.eia.gov/v2/natural-gas/move/expc/data/'

class LNGDashboard:
    def __init__(self, api_key, output_dir='./'):
        self.api_key = api_key
        self.output_dir = output_dir
        
    def fetch_price_data(self, days=3650):  # 10 years
        """Fetch Henry Hub price data from EIA API"""
        print(f"📊 Fetching Henry Hub prices (10 years)...")
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        end_str = end_date.strftime('%Y-%m-%d')
        start_str = start_date.strftime('%Y-%m-%d')
        
        query = (
            f"frequency=daily&data[0]=value"
            f"&start={start_str}&end={end_str}"
            f"&facets[series][]=RNGWHHD"
            f"&sort[0][column]=period&sort[0][direction]=asc"
            f"&offset=0&length=5000&api_key={self.api_key}"
        )

        try:
            response = requests.get(f"{PRICE_URL}?{query}")
            response.raise_for_status()
            
            data = response.json()
            
            if 'response' not in data or 'data' not in data['response'] or len(data['response']['data']) == 0:
                raise ValueError("No price data received from EIA API")
            
            records = []
            for item in data['response']['data']:
                if item['value'] is None:
                    continue
                records.append({
                    'date': item['period'],
                    'price': float(item['value'])
                })
            
            df = pd.DataFrame(records)
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date')
            
            print(f"✅ Fetched {len(df)} price records")
            return df
            
        except Exception as e:
            print(f"❌ Price API Error: {e}")
            return None
    
    def fetch_export_data(self, days=3650):  # 10 years
        """Fetch US LNG export data from EIA API"""
        print(f"📊 Fetching US LNG exports (10 years)...")
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        end_str = end_date.strftime('%Y-%m')
        start_str = start_date.strftime('%Y-%m')

        query = (
            f"frequency=monthly&data[0]=value"
            f"&start={start_str}&end={end_str}"
            f"&facets[series][]=N9133US2"
            f"&sort[0][column]=period&sort[0][direction]=asc"
            f"&offset=0&length=5000&api_key={self.api_key}"
        )

        try:
            response = requests.get(f"{EXPORT_URL}?{query}")
            response.raise_for_status()
            
            data = response.json()
            
            if 'response' not in data or 'data' not in data['response'] or len(data['response']['data']) == 0:
                print("⚠️  No export data available")
                return None
            
            records = []
            for item in data['response']['data']:
                if item['value'] is None:
                    continue
                records.append({
                    'date': item['period'],
                    'export': float(item['value']) / 1000  # MMCF → Bcf
                })
            
            df = pd.DataFrame(records)
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date')
            
            print(f"✅ Fetched {len(df)} export records")
            return df
            
        except Exception as e:
            print(f"⚠️  Export data unavailable: {e}")
            return None
    
    def create_dashboard(self, df_price, df_export):
        """Create simplified dashboard"""
        if df_price is None or len(df_price) == 0:
            print("❌ No price data available")
            return None
        
        print("📈 Creating dashboard...")
        
        latest_price = df_price.iloc[-1]['price']
        latest_date = df_price.iloc[-1]['date']
        avg_price = df_price['price'].mean()
        max_price = df_price['price'].max()
        min_price = df_price['price'].min()
        
        # Create subplots
        fig = make_subplots(
            rows=2, cols=1,
            subplot_titles=(
                'Henry Hub Natural Gas - 10 Year History',
                'US LNG Exports - 10 Year History (Monthly)'
            ),
            specs=[
                [{"secondary_y": False}],
                [{"secondary_y": False}]
            ],
            vertical_spacing=0.15,
            row_heights=[0.6, 0.4]
        )
        
        # Chart 1: 10-Year Price
        fig.add_trace(
            go.Scatter(
                x=df_price['date'],
                y=df_price['price'],
                name='Henry Hub Price',
                mode='lines',
                line=dict(color='#1f77b4', width=2),
                fill='tozeroy',
                fillcolor='rgba(31, 119, 180, 0.15)',
                hovertemplate='<b>%{x|%Y-%m-%d}</b><br>$%{y:.2f}/MMBtu<extra></extra>'
            ),
            row=1, col=1
        )
        
        # Average line
        fig.add_hline(
            y=avg_price, 
            line_dash="dash", 
            line_color="gray",
            annotation_text=f"Avg: ${avg_price:.2f}",
            row=1, col=1
        )
        
        # Chart 2: LNG Exports
        if df_export is not None and len(df_export) > 0:
            fig.add_trace(
                go.Bar(
                    x=df_export['date'],
                    y=df_export['export'],
                    name='LNG Exports',
                    marker=dict(color='#ff7f0e'),
                    hovertemplate='<b>%{x|%Y-%m}</b><br>%{y:.0f} Bcf<extra></extra>'
                ),
                row=2, col=1
            )
        
        # Update layout
        fig.update_layout(
            title_text="<b>US Natural Gas & LNG Market Dashboard</b>",
            title_font_size=18,
            height=900,
            showlegend=True,
            hovermode='x unified',
            plot_bgcolor='rgba(240, 240, 240, 0.3)',
            paper_bgcolor='white',
            font=dict(family="Arial, sans-serif", size=11)
        )
        
        # Update axes
        fig.update_yaxes(title_text="Price ($/MMBtu)", row=1, col=1)
        fig.update_yaxes(title_text="LNG Exports (Bcf)", row=2, col=1)
        fig.update_xaxes(title_text="Date", row=2, col=1)
        
        # Metrics box
        metrics_text = (
            f"<b>Current:</b> ${latest_price:.2f}/MMBtu<br>"
            f"<b>Date:</b> {latest_date.strftime('%Y-%m-%d')}<br>"
            f"<b>10Y Avg:</b> ${avg_price:.2f}<br>"
            f"<b>10Y High:</b> ${max_price:.2f}<br>"
            f"<b>10Y Low:</b> ${min_price:.2f}"
        )
        
        fig.add_annotation(
            text=metrics_text,
            xref="paper", yref="paper",
            x=0.02, y=0.98,
            showarrow=False,
            font=dict(size=10),
            bgcolor="rgba(255, 255, 255, 0.9)",
            bordercolor="black",
            borderwidth=1,
            borderpad=10,
            xanchor="left",
            yanchor="top"
        )
        
        print("✅ Dashboard created")
        return fig
    
    def save_csv(self, df_price, df_export):
        """Save data to CSV"""
        price_file = os.path.join(self.output_dir, 'henry_hub_10y.csv')
        df_price.to_csv(price_file, index=False)
        print(f"💾 Saved: henry_hub_10y.csv")
        
        if df_export is not None:
            export_file = os.path.join(self.output_dir, 'lng_exports.csv')
            df_export.to_csv(export_file, index=False)
            print(f"💾 Saved: lng_exports.csv")
    
    def save_html(self, fig, filename='lng_dashboard.html'):
        """Save dashboard as HTML"""
        filepath = os.path.join(self.output_dir, filename)
        fig.write_html(filepath)
        print(f"💾 Saved: {filename}")
        return filepath
    
    def run(self):
        """Run pipeline"""
        print("\n" + "="*50)
        print("US NATURAL GAS & LNG DASHBOARD")
        print("="*50 + "\n")
        
        df_price = self.fetch_price_data(days=3650)
        
        if df_price is None or len(df_price) == 0:
            print("❌ Failed to fetch data.")
            return False
        
        df_export = self.fetch_export_data(days=3650)

        self.save_csv(df_price, df_export)
        
        fig = self.create_dashboard(df_price, df_export)
        
        if fig is None:
            print("❌ Failed to create dashboard.")
            return False
        
        html_file = self.save_html(fig)
        
        print("\n🌐 Opening dashboard...\n")
        webbrowser.open('file://' + os.path.realpath(html_file))
        
        print("="*50)
        print("✅ Done! Dashboard ready on Desktop")
        print("="*50 + "\n")
        
        return True

def main():
    """Main entry point"""
    desktop_path = os.path.expanduser('~/Desktop')
    
    if not os.path.exists(desktop_path):
        os.makedirs(desktop_path)
    
    dashboard = LNGDashboard(
        api_key='tb5PBlfspIj7G3WJMBuvFvJNo2EhRBGeB9vzU6xx',
        output_dir=desktop_path
    )
    
    dashboard.run()

if __name__ == '__main__':
    main()
