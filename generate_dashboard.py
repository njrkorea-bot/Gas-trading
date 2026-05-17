#!/usr/bin/env python3
"""
CI entrypoint: fetches data and writes index.html to the current directory.
Used by GitHub Actions for daily dashboard updates.
"""

import os
import sys
from lng_dashboard_3 import LNGDashboard

API_KEY  = os.environ.get('EIA_API_KEY',  'tb5PBlfspIj7G3WJMBuvFvJNo2EhRBGeB9vzU6xx')
AGSI_KEY = os.environ.get('AGSI_API_KEY', '871bc294dd1ec294dd1f9940f45bdea2')

print("\n" + "=" * 50)
print("LNG & GAS MARKET DASHBOARD (CI BUILD)")
print("=" * 50 + "\n")

dashboard = LNGDashboard(api_key=API_KEY, output_dir='./', agsi_key=AGSI_KEY)

df_price = dashboard.fetch_price_data(days=3650)
if df_price is None or df_price.empty:
    print("Failed to fetch price data.")
    sys.exit(1)

df_export                   = dashboard.fetch_export_data(days=3650)
df_prod                     = dashboard.fetch_production_data(days=3650)
eu_history, country_by_date = dashboard.fetch_storage_all(days=20, country_dates=5)
df_ttf                      = dashboard.fetch_ttf_data()
dashboard.save_csv(df_price, df_export)

html = dashboard.build_html(df_price, df_export, df_prod, eu_history, country_by_date, df_ttf)
dashboard.save_html(html, 'index.html')

print("\nDone.\n")
