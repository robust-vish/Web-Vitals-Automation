import os
import sys
import math
from datetime import datetime, timedelta

import pandas as pd
from google.cloud import bigquery
from google.oauth2 import service_account
import gspread
from gspread.utils import rowcol_to_a1
from dotenv import load_dotenv

load_dotenv()

PROJECT_ID = os.getenv("PROJECT_ID")
DATASET_ID = os.getenv("DATASET_ID")
JSON_KEY_PATH = os.getenv("JSON_KEY_PATH")
SHEET_URL = os.getenv("REPORT_SHEET_URL")
PLATFORM_CONFIG = {
    "android": {
        "os_filter": "Android",
        "sheet_name": "Android web vitals",
        "label": "Android",
    },
    "ios": {
        "os_filter": "iOS",
        "sheet_name": "IOS web vitals",
        "label": "iOS",
    },
}

# Sheet row mapping: metric -> (p50_row, p75_row, p90_row, p95_row)
METRIC_ROWS = {
    "lcp":  (4, 5, 6, 7),
    "cls":  (9, 10, 11, 12),
    "inp":  (14, 15, 16, 17),
    "fcp":  (19, 20, 21, 22),
    "ttfb": (24, 25, 26, 27),
}

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def format_value(metric, value, platform="android"):
    if value is None or pd.isna(value):
        return 0 if metric == "cls" and platform == "ios" else ""
    if metric in ("fcp", "lcp", "inp"):
        return int(round(value))
    elif metric == "cls":
        return round(value, 2)
    return round(value, 2)


def query_bigquery(date_str, os_filter):
    credentials = service_account.Credentials.from_service_account_file(JSON_KEY_PATH)
    client = bigquery.Client(credentials=credentials, project=PROJECT_ID)

    sql = f"""
    WITH parsed AS (
      SELECT
        SAFE_CAST(REGEXP_EXTRACT(ea, r'FCP:\\s*([\\d.]+)') AS FLOAT64) AS fcp,
        SAFE_CAST(REGEXP_EXTRACT(ea, r'CLS:\\s*([\\d.]+)') AS FLOAT64) AS cls,
        SAFE_CAST(REGEXP_EXTRACT(ea, r'INP:\\s*([\\d.]+)') AS FLOAT64) AS inp,
        SAFE_CAST(REGEXP_EXTRACT(ea, r'LCP:\\s*([\\d.]+)') AS FLOAT64) AS lcp,
        SAFE_CAST(REGEXP_EXTRACT(ea, r'TTFB:\\s*([\\d.]+)') AS FLOAT64) AS ttfb
      FROM (
        SELECT
          (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'eventAction') AS ea
        FROM `{PROJECT_ID}.{DATASET_ID}.events_{date_str}`
        WHERE
          STARTS_WITH(event_name, 'Web_Vitals_buylead_listing_imweb')
          AND device.operating_system = '{os_filter}'
          AND (SELECT value.string_value FROM UNNEST(event_params)
               WHERE key = 'page_location') LIKE '%app.indiamart.com%'
          AND (SELECT value.string_value FROM UNNEST(event_params)
               WHERE key = 'page_location') LIKE '%/buyleads%'
      )
    )
    SELECT
      APPROX_QUANTILES(lcp,  100 IGNORE NULLS)[OFFSET(50)] AS lcp_p50,
      APPROX_QUANTILES(lcp,  100 IGNORE NULLS)[OFFSET(75)] AS lcp_p75,
      APPROX_QUANTILES(lcp,  100 IGNORE NULLS)[OFFSET(90)] AS lcp_p90,
      APPROX_QUANTILES(lcp,  100 IGNORE NULLS)[OFFSET(95)] AS lcp_p95,
      APPROX_QUANTILES(cls,  100 IGNORE NULLS)[OFFSET(50)] AS cls_p50,
      APPROX_QUANTILES(cls,  100 IGNORE NULLS)[OFFSET(75)] AS cls_p75,
      APPROX_QUANTILES(cls,  100 IGNORE NULLS)[OFFSET(90)] AS cls_p90,
      APPROX_QUANTILES(cls,  100 IGNORE NULLS)[OFFSET(95)] AS cls_p95,
      APPROX_QUANTILES(inp,  100 IGNORE NULLS)[OFFSET(50)] AS inp_p50,
      APPROX_QUANTILES(inp,  100 IGNORE NULLS)[OFFSET(75)] AS inp_p75,
      APPROX_QUANTILES(inp,  100 IGNORE NULLS)[OFFSET(90)] AS inp_p90,
      APPROX_QUANTILES(inp,  100 IGNORE NULLS)[OFFSET(95)] AS inp_p95,
      APPROX_QUANTILES(fcp,  100 IGNORE NULLS)[OFFSET(50)] AS fcp_p50,
      APPROX_QUANTILES(fcp,  100 IGNORE NULLS)[OFFSET(75)] AS fcp_p75,
      APPROX_QUANTILES(fcp,  100 IGNORE NULLS)[OFFSET(90)] AS fcp_p90,
      APPROX_QUANTILES(fcp,  100 IGNORE NULLS)[OFFSET(95)] AS fcp_p95,
      APPROX_QUANTILES(ttfb, 100 IGNORE NULLS)[OFFSET(50)] AS ttfb_p50,
      APPROX_QUANTILES(ttfb, 100 IGNORE NULLS)[OFFSET(75)] AS ttfb_p75,
      APPROX_QUANTILES(ttfb, 100 IGNORE NULLS)[OFFSET(90)] AS ttfb_p90,
      APPROX_QUANTILES(ttfb, 100 IGNORE NULLS)[OFFSET(95)] AS ttfb_p95,
      COUNT(*) AS total_events
    FROM parsed
    """

    query_job = client.query(sql)
    return query_job.to_dataframe()


def update_sheet(date, data, sheet_name, platform):
    gc = gspread.service_account(filename=JSON_KEY_PATH)
    sh = gc.open_by_url(SHEET_URL)
    ws = sh.worksheet(sheet_name)

    date_header = f"{date.day} {MONTHS[date.month - 1]}"
    day_of_week = DAYS[date.weekday()]

    row1 = ws.row_values(1)

    target_col = None
    for i, val in enumerate(row1):
        if val.strip() == date_header:
            target_col = i + 1
            print(f"  Date '{date_header}' found in column {target_col}, updating...")
            break

    if target_col is None:
        target_col = max(len(row1), 2) + 1
        print(f"  Adding new column {target_col} for '{date_header}' ({day_of_week})")

    column_values = [""] * 27
    column_values[0] = date_header
    column_values[1] = day_of_week

    row_data = data.iloc[0]
    for metric, (p50_r, p75_r, p90_r, p95_r) in METRIC_ROWS.items():
        column_values[p50_r - 1] = format_value(metric, row_data.get(f"{metric}_p50"), platform)
        column_values[p75_r - 1] = format_value(metric, row_data.get(f"{metric}_p75"), platform)
        column_values[p90_r - 1] = format_value(metric, row_data.get(f"{metric}_p90"), platform)
        column_values[p95_r - 1] = format_value(metric, row_data.get(f"{metric}_p95"), platform)

    start = rowcol_to_a1(1, target_col)
    end = rowcol_to_a1(27, target_col)

    ws.update(values=[[v] for v in column_values], range_name=f"{start}:{end}")
    print(f"  Sheet updated for {date_header}!")


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in PLATFORM_CONFIG:
        print("Usage:")
        print("  python web_vitals_automation.py android [YYYY-MM-DD]")
        print("  python web_vitals_automation.py ios [YYYY-MM-DD]")
        print("\nExamples:")
        print("  python web_vitals_automation.py android 2026-05-25")
        print("  python web_vitals_automation.py ios 2026-05-25")
        print("  python web_vitals_automation.py android          (yesterday)")
        sys.exit(1)

    platform = sys.argv[1]
    config = PLATFORM_CONFIG[platform]

    if len(sys.argv) > 2:
        date = datetime.strptime(sys.argv[2], "%Y-%m-%d")
    else:
        date = datetime.now() - timedelta(days=1)

    date_str = date.strftime("%Y%m%d")

    print("=" * 50)
    print(f"  Web Vitals Automation - {config['label']}")
    print(f"  Date: {date.strftime('%Y-%m-%d')} (table: events_{date_str})")
    print("=" * 50)

    print("\n[1/2] Querying BigQuery...")
    try:
        data = query_bigquery(date_str, config["os_filter"])
    except Exception as e:
        print(f"  ERROR: {e}")
        sys.exit(1)

    if data.empty:
        print("  ERROR: No data returned from BigQuery!")
        sys.exit(1)

    total = int(data.iloc[0].get("total_events", 0))
    print(f"  Events processed: {total:,}")

    print(f"\n  {'Metric':<8} {'p50':>10} {'p75':>10} {'p90':>10} {'p95':>10}")
    print(f"  {'-' * 48}")
    for m in ["LCP", "CLS", "INP", "FCP", "TTFB"]:
        vals = [
            format_value(m.lower(), data.iloc[0].get(f"{m.lower()}_{p}"), platform)
            for p in ["p50", "p75", "p90", "p95"]
        ]
        print(f"  {m:<8} {str(vals[0]):>10} {str(vals[1]):>10} {str(vals[2]):>10} {str(vals[3]):>10}")
    print(f"  {'-' * 48}")

    print(f"\n[2/2] Updating Google Sheet ({config['sheet_name']})...")
    try:
        update_sheet(date, data, config["sheet_name"], platform)
    except Exception as e:
        print(f"  ERROR: {e}")
        sys.exit(1)

    print("\nDone!")


if __name__ == "__main__":
    main()
