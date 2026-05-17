#!/usr/bin/env python3
"""
CI entrypoint: fetches data and writes index.html to the current directory.
Used by GitHub Actions for daily dashboard updates.
"""

import os
import sys
from lng_dashboard_3 import LNGDashboard

API_KEY = os.environ.get('EIA_API_KEY', 'tb5PBlfspIj7G3WJMBuvFvJNo2EhRBGeB9vzU6xx')

print("\n" + "=" * 50)
print("US NATURAL GAS & LNG DASHBOARD (CI BUILD)")
print("=" * 50 + "\n")

dashboard = LNGDashboard(api_key=API_KEY, output_dir='./')

df_price = dashboard.fetch_price_data(days=3650)
if df_price is None or len(df_price) == 0:
    print("❌ Failed to fetch price data.")
    sys.exit(1)

df_export = dashboard.fetch_export_data(days=3650)

dashboard.save_csv(df_price, df_export)

fig = dashboard.create_dashboard(df_price, df_export)
if fig is None:
    print("❌ Failed to create dashboard.")
    sys.exit(1)

dashboard.save_html(fig, 'index.html')

print("\n✅ index.html generated successfully")
print("=" * 50 + "\n")
