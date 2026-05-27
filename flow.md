# How Web Vitals Automation Works

## Overview

Instead of manually downloading a CSV from GA4 (which is sampled and capped at 1 lakh rows), this automation directly queries the full raw data stored in BigQuery — no file download, no sampling, no row limit.

---

## Flow Diagram

```
You run a command on your terminal
          │
          ▼
Python script sends SQL query to BigQuery (Google Cloud)
          │
          ▼
BigQuery processes query on ~26 lakh raw events (server-side)
          │
          ▼
Only the result (p50/p75/p90/p95 for 5 metrics) is sent back
          │
          ▼
Script finds the correct date column in Google Sheet
          │
          ▼
Writes 20 values into the sheet (done)
```

---

## Why This Is Better Than the Manual CSV Method

| | Manual (CSV) | This Automation |
|---|---|---|
| Data coverage | ~55% sampled | 100% full data |
| Row limit | 1 lakh rows | No limit |
| Data download | Full CSV to your PC | Only final result |
| Time taken | 5–10 mins daily | ~30 seconds |
| Human error | Possible | None |

---

## Key Technical Details

### 1. Where is the data?
GA4 automatically exports raw event data to BigQuery daily. Each day's data sits in a separate table named `events_YYYYMMDD` (e.g., `events_20260523`) inside the dataset `analytics_327723810` on the GCP project `indiamart-ga-big-data`.

### 2. No data is downloaded
The SQL query runs entirely on Google's servers. BigQuery scans all ~26 lakh rows on the cloud, calculates the percentiles, and returns only 1 row of results (20 numbers) to your machine. Your internet connection only carries that tiny result back.

### 3. How events are filtered
Each GA4 event has parameters attached. The query filters for:
- Event name starts with `Web_Vitals_buylead_listing_imweb`
- Hostname contains `app.indiamart.com`
- Page location contains `/buyleads`
- Operating system = `Android` or `iOS`

### 4. How metric values are extracted
Each matching event has an `eventAction` parameter that looks like:
```
FCP: 476, CLS: null, INP: null, LCP: 476, TTFB: 433, Rating: good, Network: 4g, Device: Android
```
The SQL uses `REGEXP_EXTRACT` to parse out the numeric value for each metric from this string.

### 5. How percentiles are calculated
BigQuery's `APPROX_QUANTILES(column, 100)` function calculates percentiles across all events in one pass. Each individual event counts as one data point — no weighting issues like in the old CSV script.

- `OFFSET(50)` → p50 (median)
- `OFFSET(75)` → p75
- `OFFSET(90)` → p90
- `OFFSET(95)` → p95

### 6. How the sheet is updated
The script reads Row 1 of the sheet to find the column matching the date (e.g., "23 May"). If found, it updates that column. If not found, it appends a new column at the end. It writes values into fixed rows per metric (e.g., LCP p50 always goes in row 4, LCP p75 in row 5, etc.).

### 7. Authentication
A Google Cloud **Service Account** (`python-automation@indiamart-ga-big-data.iam.gserviceaccount.com`) handles all authentication. Its JSON key file is used to:
- Authenticate with BigQuery to run queries
- Authenticate with Google Sheets API to write results

---

## Future Possibilities

- **Hourly breakdown** — BigQuery has an `event_timestamp` column, so we can group by hour and see how metrics change throughout the day
- **Custom date range / weekly** — Query across multiple days using BigQuery's table wildcard (`events_*`) with a date range filter, same approach used for weekly reports
- **Automated daily scheduling** — Set up a Windows Task Scheduler job to run both Android and iOS commands automatically every morning
