#!/usr/bin/env python3
"""
LNG & Natural Gas Market Dashboard — Dark tabbed layout
Tabs: US Market | Europe (TTF) | Global Flows
"""

import os
import requests
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta, timezone
import webbrowser

API_KEY   = os.environ.get('EIA_API_KEY', 'tb5PBlfspIj7G3WJMBuvFvJNo2EhRBGeB9vzU6xx')
PRICE_URL  = 'https://api.eia.gov/v2/natural-gas/pri/fut/data/'
EXPORT_URL = 'https://api.eia.gov/v2/natural-gas/move/expc/data/'

# Light theme palette
D = dict(
    paper  = '#ffffff',
    plot   = '#f8f9fa',
    text   = '#1a1a2e',
    sub    = '#6c757d',
    grid   = '#dee2e6',
    blue   = '#0d6efd',
    green  = '#198754',
    orange = '#e07b00',
    red    = '#dc3545',
)


class LNGDashboard:
    def __init__(self, api_key, output_dir='./', agsi_key=None):
        self.api_key    = api_key
        self.output_dir = output_dir
        self.agsi_key   = agsi_key

    # ------------------------------------------------------------------ #
    # Data fetching
    # ------------------------------------------------------------------ #

    def fetch_price_data(self, days=3650):
        print("Fetching Henry Hub spot prices (10 years)...")
        end   = datetime.now()
        start = end - timedelta(days=days)
        query = (
            f"frequency=daily&data[0]=value"
            f"&start={start.strftime('%Y-%m-%d')}&end={end.strftime('%Y-%m-%d')}"
            f"&facets[series][]=RNGWHHD"
            f"&sort[0][column]=period&sort[0][direction]=asc"
            f"&offset=0&length=5000&api_key={self.api_key}"
        )
        try:
            r = requests.get(f"{PRICE_URL}?{query}")
            r.raise_for_status()
            data = r.json()
            if not data.get('response', {}).get('data'):
                raise ValueError("Empty response")
            records = [
                {'date': i['period'], 'price': float(i['value'])}
                for i in data['response']['data'] if i['value'] is not None
            ]
            df = pd.DataFrame(records)
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date').reset_index(drop=True)
            print(f"  {len(df)} records")
            return df
        except Exception as e:
            print(f"  Error: {e}")
            return None

    def fetch_export_data(self, days=3650):
        print("Fetching US LNG exports (10 years)...")
        end   = datetime.now()
        start = end - timedelta(days=days)
        query = (
            f"frequency=monthly&data[0]=value"
            f"&start={start.strftime('%Y-%m')}&end={end.strftime('%Y-%m')}"
            f"&facets[series][]=N9133US2"
            f"&sort[0][column]=period&sort[0][direction]=asc"
            f"&offset=0&length=5000&api_key={self.api_key}"
        )
        try:
            r = requests.get(f"{EXPORT_URL}?{query}")
            r.raise_for_status()
            data = r.json()
            if not data.get('response', {}).get('data'):
                print("  No data")
                return None
            records = [
                {'date': i['period'], 'export': float(i['value']) / 1000}  # MMCF → Bcf
                for i in data['response']['data'] if i['value'] is not None
            ]
            df = pd.DataFrame(records)
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date').reset_index(drop=True)
            print(f"  {len(df)} records")
            return df
        except Exception as e:
            print(f"  Error: {e}")
            return None

    def fetch_production_data(self, days=3650):
        print("Fetching US dry natural gas production (10 years)...")
        end   = datetime.now()
        start = end - timedelta(days=days)
        query = (
            f"frequency=monthly&data[0]=value"
            f"&start={start.strftime('%Y-%m')}&end={end.strftime('%Y-%m')}"
            f"&facets[series][]=N9070US2"
            f"&sort[0][column]=period&sort[0][direction]=asc"
            f"&offset=0&length=5000&api_key={self.api_key}"
        )
        try:
            r = requests.get(f"https://api.eia.gov/v2/natural-gas/prod/sum/data/?{query}")
            r.raise_for_status()
            data = r.json()
            if not data.get('response', {}).get('data'):
                print("  No data")
                return None
            records = [
                {'date': i['period'], 'production': float(i['value']) / 1000}  # MMcf → Bcf
                for i in data['response']['data'] if i['value'] is not None
            ]
            df = pd.DataFrame(records)
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date').reset_index(drop=True)
            print(f"  {len(df)} records")
            return df
        except Exception as e:
            print(f"  Error: {e}")
            return None

    def fetch_ttf_data(self, days=3650):
        print("Fetching TTF natural gas futures (yfinance)...")
        try:
            import yfinance as yf
            df = yf.download('TTF=F', period='max', progress=False, auto_adjust=True)
            if df.empty:
                print("  No TTF data")
                return None
            df = df[['Close']].copy()
            df.columns = ['price']
            df.index.name = 'date'
            df = df.reset_index()
            df['date'] = pd.to_datetime(df['date']).dt.tz_localize(None)
            df = df.dropna().sort_values('date').reset_index(drop=True)
            cutoff = df['date'].max() - pd.Timedelta(days=days)
            df = df[df['date'] >= cutoff].reset_index(drop=True)
            print(f"  {len(df)} records, latest: {df['price'].iloc[-1]:.2f} EUR/MWh")
            return df
        except Exception as e:
            print(f"  Error: {e}")
            return None

    def fetch_storage_all(self, days=20, country_dates=5):
        """Fetch EU aggregate for last N days + country snapshots for last M dates."""
        print(f"Fetching EU gas storage ({days} days, {country_dates} country snapshots)...")
        if not self.agsi_key:
            print("  No AGSI key — skipping")
            return [], {}
        eu_history, country_by_date = [], {}
        seen_days = set()
        attempt = 0
        while len(eu_history) < days and attempt < days + 15:
            dt = datetime.now() - timedelta(days=attempt)
            date_str = dt.strftime('%Y-%m-%d')
            try:
                r = requests.get(
                    'https://agsi.gie.eu/api',
                    params={'country': 'eu', 'date': date_str, 'size': 1},
                    headers={'x-key': self.agsi_key}, timeout=10
                )
                if r.status_code == 200:
                    data = r.json().get('data', [])
                    if data and data[0].get('full') not in (None, '-'):
                        row = data[0]
                        gas_day = row.get('gasDayStart', date_str)
                        if gas_day not in seen_days:
                            seen_days.add(gas_day)
                            eu_history.append(row)
                            if len(country_by_date) < country_dates and row.get('children'):
                                country_by_date[gas_day] = row['children']
            except Exception:
                pass
            attempt += 1
        print(f"  {len(eu_history)} EU rows, {len(country_by_date)} country dates")
        return eu_history, country_by_date

    def save_csv(self, df_price, df_export):
        df_price.to_csv(os.path.join(self.output_dir, 'henry_hub_10y.csv'), index=False)
        print("  Saved: henry_hub_10y.csv")
        if df_export is not None:
            df_export.to_csv(os.path.join(self.output_dir, 'lng_exports.csv'), index=False)
            print("  Saved: lng_exports.csv")

    # ------------------------------------------------------------------ #
    # Chart builders
    # ------------------------------------------------------------------ #

    def _fig_hh_price(self, df_price):
        monthly = (df_price.set_index('date')
                   .resample('ME')['price'].mean().reset_index())
        avg = df_price['price'].mean()
        max_p = df_price['price'].max()

        # Key events: (date, label, color, y_anchor 0..1)
        events = [
            ('2020-03-11', 'COVID-19<br>Pandemic',   '#0dcaf0', 0.78),
            ('2021-02-10', 'Winter Storm<br>Uri',     '#6f42c1', 0.65),
            ('2022-02-24', 'Russia–Ukraine<br>War',   D['red'],  0.92),
            ('2023-10-07', 'Israel–Gaza<br>War',      '#fd7e14', 0.72),
            ('2024-01-15', 'Polar Vortex<br>Jan 2024','#adb5bd', 0.58),
            ('2026-02-28', 'US–Iran<br>War',          '#20c997', 0.85),
        ]

        fig = go.Figure()

        # Daily — more visible
        fig.add_trace(go.Scatter(
            x=df_price['date'], y=df_price['price'],
            mode='lines', line=dict(color='rgba(13,110,253,0.45)', width=1.2),
            showlegend=False,
            hovertemplate='%{x|%Y-%m-%d}: $%{y:.2f}/MMBtu<extra>Daily</extra>'
        ))
        # Monthly avg — solid + fill
        fig.add_trace(go.Scatter(
            x=monthly['date'], y=monthly['price'],
            name='Monthly avg', mode='lines',
            line=dict(color=D['blue'], width=2.5),
            fill='tozeroy', fillcolor='rgba(13,110,253,0.08)',
            hovertemplate='%{x|%Y-%m}: $%{y:.2f}/MMBtu<extra>Monthly avg</extra>'
        ))
        # 10Y average line
        fig.add_hline(y=avg, line_dash='dash', line_color=D['sub'], line_width=1,
                      annotation_text=f'10Y avg ${avg:.2f}',
                      annotation_font=dict(color=D['sub'], size=11))

        # Event markers
        for date_str, label, color, y_frac in events:
            fig.add_vline(x=date_str, line_dash='dot', line_color=color, line_width=1.5)
            fig.add_annotation(
                x=date_str, y=max_p * y_frac,
                text=label, showarrow=False,
                xanchor='left', xshift=6,
                font=dict(color=color, size=10)
            )

        fig.update_layout(
            height=420, margin=dict(l=50, r=20, t=10, b=40),
            paper_bgcolor=D['paper'], plot_bgcolor=D['plot'],
            font=dict(color=D['text'], family='Arial'),
            hovermode='x unified', showlegend=False,
            xaxis=dict(gridcolor=D['grid'], showgrid=True, zeroline=False),
            yaxis=dict(gridcolor=D['grid'], showgrid=True, zeroline=False,
                       title='$/MMBtu'),
        )
        return fig

    def _fig_exports(self, df_export):
        fig = go.Figure(go.Bar(
            x=df_export['date'], y=df_export['export'],
            marker=dict(color=D['green'], opacity=0.8),
            hovertemplate='%{x|%Y-%m}: %{y:.1f} Bcf<extra>US LNG Exports</extra>'
        ))
        fig.update_layout(
            height=280, margin=dict(l=50, r=20, t=10, b=40),
            paper_bgcolor=D['paper'], plot_bgcolor=D['plot'],
            font=dict(color=D['text'], family='Arial'),
            hovermode='x unified', showlegend=False,
            xaxis=dict(gridcolor=D['grid'], showgrid=False, zeroline=False),
            yaxis=dict(gridcolor=D['grid'], showgrid=True, zeroline=False,
                       title='Bcf / month'),
        )
        return fig

    # ------------------------------------------------------------------ #
    # HTML assembly
    # ------------------------------------------------------------------ #

    def _fig_production(self, df_prod):
        fig = go.Figure(go.Scatter(
            x=df_prod['date'], y=df_prod['production'],
            mode='lines',
            line=dict(color=D['orange'], width=2),
            fill='tozeroy', fillcolor='rgba(224,123,0,0.08)',
            hovertemplate='%{x|%Y-%m}: %{y:.0f} Bcf<extra>Dry Gas Production</extra>'
        ))
        fig.update_layout(
            height=250, margin=dict(l=50, r=20, t=10, b=40),
            paper_bgcolor=D['paper'], plot_bgcolor=D['plot'],
            font=dict(color=D['text'], family='Arial'),
            hovermode='x unified', showlegend=False,
            xaxis=dict(gridcolor=D['grid'], showgrid=False, zeroline=False),
            yaxis=dict(gridcolor=D['grid'], showgrid=True, zeroline=False,
                       title='Bcf / month'),
        )
        return fig

    def _fig_ttf(self, df):
        monthly = (df.set_index('date').resample('ME')['price'].mean().reset_index())
        avg = df['price'].mean()
        max_p = df['price'].max()

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df['date'], y=df['price'],
            mode='lines', line=dict(color='rgba(13,110,253,0.4)', width=1.2),
            showlegend=False,
            hovertemplate='%{x|%Y-%m-%d}: €%{y:.2f}/MWh<extra>Daily</extra>'
        ))
        fig.add_trace(go.Scatter(
            x=monthly['date'], y=monthly['price'],
            name='Monthly avg', mode='lines',
            line=dict(color=D['blue'], width=2.5),
            fill='tozeroy', fillcolor='rgba(13,110,253,0.08)',
            hovertemplate='%{x|%Y-%m}: €%{y:.2f}/MWh<extra>Monthly avg</extra>'
        ))
        fig.add_hline(y=avg, line_dash='dash', line_color=D['sub'], line_width=1,
                      annotation_text=f'Avg €{avg:.1f}',
                      annotation_font=dict(color=D['sub'], size=11))
        fig.add_vline(x='2022-02-24', line_dash='dot', line_color=D['red'], line_width=1.5)
        fig.add_annotation(x='2022-02-24', y=max_p * 0.92,
                           text='Russia–Ukraine<br>War', showarrow=False,
                           xanchor='left', xshift=6,
                           font=dict(color=D['red'], size=10))
        fig.update_layout(
            height=400, autosize=True, margin=dict(l=60, r=20, t=10, b=40),
            paper_bgcolor=D['paper'], plot_bgcolor=D['plot'],
            font=dict(color=D['text'], family='Arial'),
            hovermode='x unified', showlegend=False,
            xaxis=dict(gridcolor=D['grid'], showgrid=True, zeroline=False),
            yaxis=dict(gridcolor=D['grid'], showgrid=True, zeroline=False,
                       title='EUR/MWh'),
        )
        return fig

    def _full_badge(self, val_str):
        """Colored badge for fill% value."""
        try:
            v = float(val_str)
        except (TypeError, ValueError):
            return f'<span class="badge badge-na">N/A</span>'
        if v < 30:   color = '#dc3545'
        elif v < 50: color = '#e07b00'
        elif v < 70: color = '#e9a800'
        else:        color = '#198754'
        return f'<span class="badge" style="background:{color}">{v:.2f}%</span>'

    def _trend_cell(self, val_str):
        try:
            v = float(val_str)
            arrow = '▲' if v > 0 else ('▼' if v < 0 else '—')
            cls   = 'trend-up' if v > 0 else ('trend-dn' if v < 0 else 'trend-flat')
            return f'<span class="{cls}">{arrow} {abs(v):.2f}%</span>'
        except (TypeError, ValueError):
            return '—'

    def _fmt(self, val, decimals=2):
        try:
            return f'{float(val):,.{decimals}f}'
        except (TypeError, ValueError):
            return '—'

    def _table_eu_storage(self, eu_history, country_by_date):
        THEAD = '''<thead><tr>
          <th>Gas Day Start</th><th>Gas Day End</th>
          <th>Gas in Storage (TWh)</th><th>Full %</th><th>Trend</th>
          <th>Injection (GWh/d)</th><th>Withdrawal (GWh/d)</th>
          <th>Consumption (GWh/d)</th><th>Working Cap (TWh)</th>
        </tr></thead>'''

        # ── EU 20-day history table ──
        eu_rows_html = ''
        for r in eu_history:
            eu_rows_html += f'''<tr>
              <td>{r.get("gasDayStart","")}</td>
              <td>{r.get("gasDayEnd","")}</td>
              <td>{self._fmt(r.get("gasInStorage"),2)}</td>
              <td>{self._full_badge(r.get("full"))}</td>
              <td>{self._trend_cell(r.get("trend"))}</td>
              <td>{self._fmt(r.get("injection"),2)}</td>
              <td>{self._fmt(r.get("withdrawal"),2)}</td>
              <td>{self._fmt(r.get("consumption"),2)}</td>
              <td>{self._fmt(r.get("workingGasVolume"),2)}</td>
            </tr>'''
        latest_updated = eu_history[0].get('updatedAt', '') if eu_history else ''

        # ── Country tables (one per date, tabbed) ──
        dates = list(country_by_date.keys())  # most recent first

        tab_btns = ''
        country_tables = ''
        for i, date_str in enumerate(dates):
            active_btn = 'active' if i == 0 else ''
            display    = '' if i == 0 else 'style="display:none"'
            tab_btns  += f'<button class="date-tab {active_btn}" onclick="showCt(\'{date_str}\',this)">{date_str}</button>'

            rows_html = ''
            valid = [c for c in country_by_date[date_str]
                     if c.get('name') and c.get('full') not in (None, '-')]
            valid.sort(key=lambda x: float(x['full']))
            for c in valid:
                try:
                    rows_html += f'''<tr>
                      <td>{c.get("name","")}</td>
                      <td>{self._fmt(c.get("gasInStorage"),2)}</td>
                      <td>{self._full_badge(c.get("full"))}</td>
                      <td>{self._trend_cell(c.get("trend"))}</td>
                      <td>{self._fmt(c.get("injection"),2)}</td>
                      <td>{self._fmt(c.get("withdrawal"),2)}</td>
                      <td>{self._fmt(c.get("consumption"),2)}</td>
                      <td>{self._fmt(c.get("workingGasVolume"),2)}</td>
                    </tr>'''
                except Exception:
                    continue

            country_tables += f'''
<div id="ct-{date_str}" class="country-tbl" {display}>
<div class="tbl-wrap">
<table class="data-tbl">
  <thead><tr>
    <th>Country</th><th>Gas in Storage (TWh)</th><th>Full %</th><th>Trend</th>
    <th>Injection (GWh/d)</th><th>Withdrawal (GWh/d)</th>
    <th>Consumption (GWh/d)</th><th>Working Cap (TWh)</th>
  </tr></thead>
  <tbody>{rows_html}</tbody>
</table>
</div></div>'''

        return f'''
<div class="tbl-meta">Source: GIE AGSI+ &nbsp;|&nbsp; Last updated: <strong>{latest_updated}</strong></div>

<div class="tbl-section-label">EU Aggregate — Last 20 Days</div>
<div class="tbl-wrap">
<table class="data-tbl">
  {THEAD}
  <tbody>{eu_rows_html}</tbody>
</table>
</div>

<div class="tbl-section-label" style="margin-top:24px">By Country — Select Date</div>
<div class="date-tabs">{tab_btns}</div>
{country_tables}

<script>
function showCt(d,btn){{
  document.querySelectorAll('.country-tbl').forEach(t=>t.style.display='none');
  document.querySelectorAll('.date-tab').forEach(b=>b.classList.remove('active'));
  document.getElementById('ct-'+d).style.display='';
  btn.classList.add('active');
}}
</script>'''

    def _stat_card(self, label, value, note=None, up=None):
        note_html = ''
        if note is not None:
            cls   = 'up' if up else ('down' if up is False else 'neutral')
            arrow = '▲ ' if up else ('▼ ' if up is False else '')
            note_html = f'<div class="stat-note {cls}">{arrow}{note}</div>'
        return f'''<div class="stat-card">
  <div class="stat-lbl">{label}</div>
  <div class="stat-val">{value}</div>
  {note_html}
</div>'''

    def build_html(self, df_price, df_export, df_prod=None, eu_history=None, country_by_date=None, df_ttf=None):
        # ---- stats ----
        cur  = df_price.iloc[-1]['price']
        prev = df_price.iloc[-2]['price']
        chg  = cur - prev
        avg  = df_price['price'].mean()
        hi   = df_price['price'].max()
        lo   = df_price['price'].min()

        stats = (
            self._stat_card('Henry Hub Spot', f'${cur:.2f}',
                            f'{abs(chg):.2f} vs prev day', chg >= 0)
            + self._stat_card('10Y Average', f'${avg:.2f}')
            + self._stat_card('10Y High', f'${hi:.2f}')
            + self._stat_card('10Y Low',  f'${lo:.2f}')
        )
        if df_export is not None and len(df_export) > 1:
            ex_cur  = df_export.iloc[-1]['export']
            ex_prev = df_export.iloc[-2]['export']
            ex_chg  = ex_cur - ex_prev
            stats += self._stat_card(
                'LNG Exports (latest)', f'{ex_cur:.0f} Bcf',
                f'{abs(ex_chg):.0f} Bcf vs prev month', ex_chg >= 0
            )
        if df_prod is not None and len(df_prod) > 1:
            pr_cur  = df_prod.iloc[-1]['production']
            pr_prev = df_prod.iloc[-2]['production']
            pr_chg  = pr_cur - pr_prev
            stats += self._stat_card(
                'Dry Gas Production (latest)', f'{pr_cur:.0f} Bcf',
                f'{abs(pr_chg):.0f} Bcf vs prev month', pr_chg >= 0
            )

        # ---- EU storage stat cards ----
        eu_stats = ''
        latest = eu_history[0] if eu_history else None
        if latest:
            full  = latest.get('full')
            gas   = latest.get('gasInStorage')
            trend = latest.get('trend')
            if full not in (None, '-'):
                eu_stats += self._stat_card('EU Storage Fill', f'{float(full):.1f}%')
            if gas not in (None, '-'):
                eu_stats += self._stat_card('Gas in Storage', f'{float(gas):.0f} TWh')
            if trend not in (None, '-'):
                t = float(trend)
                eu_stats += self._stat_card('Daily Trend', f'{t:+.2f}%', up=t >= 0)
        if df_ttf is not None and not df_ttf.empty:
            ttf_cur  = df_ttf['price'].iloc[-1]
            ttf_prev = df_ttf['price'].iloc[-2]
            ttf_chg  = ttf_cur - ttf_prev
            eu_stats += self._stat_card('TTF Front-Month', f'€{ttf_cur:.2f}/MWh',
                                        f'{ttf_chg:+.2f} vs prev day', ttf_chg >= 0)

        # ---- EU storage table ----
        if eu_history:
            storage_table = self._table_eu_storage(eu_history, country_by_date or {})
        else:
            storage_table = '<div class="placeholder">Storage data unavailable</div>'

        # ---- plotly divs ----
        opts = dict(full_html=False, include_plotlyjs=False,
                    config={'responsive': True, 'displayModeBar': False})
        hh_div = self._fig_hh_price(df_price).to_html(**opts)
        ex_div = (self._fig_exports(df_export).to_html(**opts)
                  if df_export is not None else
                  '<div class="placeholder">Export data unavailable</div>')
        prod_div = (self._fig_production(df_prod).to_html(**opts)
                    if df_prod is not None else
                    '<div class="placeholder">Production data unavailable</div>')
        ttf_div = (self._fig_ttf(df_ttf).to_html(**opts)
                   if df_ttf is not None else
                   '<div class="placeholder">TTF data unavailable</div>')

        ts = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')

        return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>LNG &amp; Gas Market Dashboard</title>
<script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#f0f2f5;color:#1a1a2e;font-family:Arial,sans-serif;min-height:100vh}}

/* ── nav ── */
.nav{{background:#ffffff;border-bottom:1px solid #dee2e6;
      display:flex;align-items:center;height:54px;padding:0 24px;gap:8px;
      box-shadow:0 1px 3px rgba(0,0,0,.08)}}
.nav-brand{{color:#0d6efd;font-size:15px;font-weight:700;margin-right:20px;white-space:nowrap}}
.tabs{{display:flex;gap:2px}}
.tab-btn{{
  padding:8px 16px;border:none;border-radius:6px 6px 0 0;cursor:pointer;
  color:#6c757d;font-size:13px;background:transparent;
  border-bottom:2px solid transparent;transition:all .15s;
}}
.tab-btn:hover{{color:#1a1a2e;background:#f0f2f5}}
.tab-btn.active{{color:#0d6efd;background:#f0f2f5;border-bottom:2px solid #0d6efd}}
.nav-time{{margin-left:auto;color:#6c757d;font-size:11px;white-space:nowrap}}

/* ── layout ── */
.panel{{display:none;padding:20px 24px}}
.panel.active{{display:block}}

/* ── stat cards ── */
.stats{{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:20px}}
.stat-card{{background:#ffffff;border:1px solid #dee2e6;border-radius:8px;padding:14px 20px;min-width:150px;
            box-shadow:0 1px 3px rgba(0,0,0,.06)}}
.stat-lbl{{color:#6c757d;font-size:10px;text-transform:uppercase;letter-spacing:.6px}}
.stat-val{{color:#1a1a2e;font-size:22px;font-weight:700;margin-top:4px;line-height:1}}
.stat-note{{font-size:11px;margin-top:5px}}
.stat-note.up{{color:#198754}}.stat-note.down{{color:#dc3545}}.stat-note.neutral{{color:#6c757d}}

/* ── chart cards ── */
.card{{background:#ffffff;border:1px solid #dee2e6;border-radius:8px;padding:16px;margin-bottom:16px;
       box-shadow:0 1px 3px rgba(0,0,0,.06)}}
.card-title{{color:#6c757d;font-size:10px;text-transform:uppercase;letter-spacing:.6px;margin-bottom:10px}}

/* ── placeholder ── */
.placeholder{{
  display:flex;align-items:center;justify-content:center;
  height:280px;color:#adb5bd;font-size:13px;
  border:1px dashed #dee2e6;border-radius:8px;
}}

/* ── storage tables ── */
.tbl-meta{{font-size:12px;color:#6c757d;margin-bottom:12px}}
.tbl-section-label{{font-size:10px;text-transform:uppercase;letter-spacing:.6px;
                    color:#6c757d;font-weight:700;margin-bottom:6px}}
.tbl-wrap{{overflow-x:auto;margin-bottom:4px}}
.data-tbl{{width:100%;border-collapse:collapse;font-size:13px}}
.data-tbl th{{background:#f8f9fa;color:#6c757d;font-size:10px;text-transform:uppercase;
              letter-spacing:.5px;padding:8px 12px;text-align:right;border-bottom:2px solid #dee2e6;
              white-space:nowrap}}
.data-tbl th:first-child{{text-align:left}}
.data-tbl td{{padding:7px 12px;text-align:right;border-bottom:1px solid #f0f2f5;color:#1a1a2e}}
.data-tbl td:first-child{{text-align:left;font-weight:500}}
.data-tbl tbody tr:hover{{background:#f8f9fa}}
.badge{{display:inline-block;padding:2px 8px;border-radius:4px;color:#fff;font-size:12px;font-weight:600}}
.badge-na{{background:#adb5bd}}
.trend-up{{color:#198754;font-weight:600}}
.trend-dn{{color:#dc3545;font-weight:600}}
.trend-flat{{color:#6c757d}}
.js-plotly-plot, .plotly-graph-div{{width:100% !important}}
.date-tabs{{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:10px;margin-top:6px}}
.date-tab{{padding:5px 12px;border:1px solid #dee2e6;border-radius:6px;background:#fff;
           color:#6c757d;font-size:12px;cursor:pointer;transition:all .15s}}
.date-tab:hover{{background:#f0f2f5;color:#1a1a2e}}
.date-tab.active{{background:#0d6efd;color:#fff;border-color:#0d6efd}}
</style>
</head>
<body>

<nav class="nav">
  <div class="nav-brand">⚡ Gas Market Dashboard</div>
  <div class="tabs">
    <button class="tab-btn active" onclick="show('us',this)">US</button>
    <button class="tab-btn"        onclick="show('eu',this)">EU</button>
    <button class="tab-btn"        onclick="show('gl',this)">Macroeconomic</button>
    <button class="tab-btn"        onclick="show('in',this)">Insight</button>
    <button class="tab-btn"        onclick="show('mo',this)">Modelling</button>
  </div>
  <div class="nav-time">Updated: {ts}</div>
</nav>

<!-- ═══════════════════════ US MARKET ═══════════════════════ -->
<div id="us" class="panel active">
  <div class="stats">{stats}</div>

  <div class="card">
    <div class="card-title">Henry Hub — Spot Price &nbsp;(daily + monthly avg, $/MMBtu)</div>
    {hh_div}
  </div>

  <div class="card">
    <div class="card-title">US LNG Exports — Monthly Volume (Bcf)</div>
    {ex_div}
  </div>

  <div class="card">
    <div class="card-title">US Dry Natural Gas Production — Monthly (Bcf)</div>
    {prod_div}
  </div>
</div>

<!-- ═══════════════════════ EUROPE ═══════════════════════ -->
<div id="eu" class="panel">
  <div class="stats">{eu_stats}</div>
  <div class="card">
    <div class="card-title">EU Natural Gas Storage — Latest Snapshot (GIE AGSI+)</div>
    {storage_table}
  </div>
  <div class="card">
    <div class="card-title">TTF Natural Gas Futures — Front Month (EUR/MWh)</div>
    {ttf_div}
  </div>
</div>

<!-- ═══════════════════════ GLOBAL FLOWS ═══════════════════════ -->
<div id="gl" class="panel">
  <div class="placeholder">Macroeconomic indicators — coming soon</div>
</div>

<!-- ═══════════════════════ INSIGHT ═══════════════════════ -->
<div id="in" class="panel">
  <div class="placeholder">Market insights &amp; analysis — coming soon</div>
</div>

<!-- ═══════════════════════ MODELLING ═══════════════════════ -->
<div id="mo" class="panel">
  <div class="placeholder">Price modelling &amp; forecasting — coming soon</div>
</div>

<script>
function show(id,btn){{
  document.querySelectorAll('.panel').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(b=>b.classList.remove('active'));
  document.getElementById(id).classList.add('active');
  btn.classList.add('active');
}}
</script>
</body>
</html>'''

    def save_html(self, html, filename='index.html'):
        path = os.path.join(self.output_dir, filename)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"  Saved: {filename}")
        return path

    # ------------------------------------------------------------------ #
    # Entry point
    # ------------------------------------------------------------------ #

    def run(self):
        print("\n" + "=" * 50)
        print("LNG & GAS MARKET DASHBOARD")
        print("=" * 50 + "\n")

        df_price = self.fetch_price_data()
        if df_price is None or df_price.empty:
            print("Failed to fetch price data.")
            return False

        df_export                    = self.fetch_export_data()
        df_prod                      = self.fetch_production_data()
        eu_history, country_by_date  = self.fetch_storage_all()
        df_ttf                       = self.fetch_ttf_data()
        self.save_csv(df_price, df_export)

        html = self.build_html(df_price, df_export, df_prod, eu_history, country_by_date, df_ttf)
        path = self.save_html(html)

        print("\nOpening dashboard in browser...")
        webbrowser.open('file://' + os.path.realpath(path))
        print("Done!\n")
        return True


AGSI_KEY = os.environ.get('AGSI_API_KEY', '871bc294dd1ec294dd1f9940f45bdea2')

def main():
    desktop = os.path.expanduser('~/Desktop')
    os.makedirs(desktop, exist_ok=True)
    LNGDashboard(api_key=API_KEY, output_dir=desktop, agsi_key=AGSI_KEY).run()


if __name__ == '__main__':
    main()
