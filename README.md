# Web Vitals Automation

Automates daily Web Vitals (FCP, CLS, INP, LCP, TTFB) reporting for the BuyLeads listing page on Android and iOS.

Fetches raw event data from **Google Analytics 4 via BigQuery**, calculates **p50/p75/p90/p95 percentiles** across all events (no sampling), and writes the results to a **Google Sheet**.

## How It Works

```
GA4 (app.indiamart.com)
  --> Automatic export to BigQuery (analytics_327723810)
    --> Python script queries BigQuery for a given date
      --> Extracts FCP, CLS, INP, LCP, TTFB from eventAction parameter
        --> Calculates p50/p75/p90/p95 using APPROX_QUANTILES
          --> Updates the Google Sheet (one column per day)
```

### BigQuery Filters

| Filter | Value |
|--------|-------|
| Event name | begins with `Web_Vitals_buylead_listing_imweb` |
| Hostname | contains `app.indiamart.com` |
| Landing page | contains `/buyleads` |
| Operating system | `Android` or `iOS` (based on command) |

## Setup

### 1. Clone and create virtual environment

```bash
git clone <repo-url>
cd Web_vitals_automation
python -m venv .venv
```

### 2. Activate virtual environment

**Windows (PowerShell):**
```powershell
.\.venv\Scripts\Activate.ps1
```

**Windows (CMD):**
```cmd
.\.venv\Scripts\activate.bat
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Create a `.env` file in the project root:

```env
PROJECT_ID=indiamart-ga-big-data
DATASET_ID=analytics_327723810
JSON_KEY_PATH=files/python-automation-sa.json
REPORT_SHEET_URL=https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/edit
```

### 5. Service account key

Place your Google Cloud service account JSON key at `files/python-automation-sa.json`.

The service account needs:
- **BigQuery Data Viewer** and **BigQuery Job User** roles on the project
- **Editor** access on the Google Sheet (share the sheet with the service account email)

Required APIs enabled on the GCP project:
- BigQuery API
- Google Sheets API
- Google Drive API

## Usage

```bash
cd C:\Users\Indiamart\Desktop\Web_vitals_automation
```

**Android - specific date:**
```bash
.\.venv\Scripts\python.exe web_vitals_automation.py android 2026-05-25
```

**iOS - specific date:**
```bash
.\.venv\Scripts\python.exe web_vitals_automation.py ios 2026-05-25
```

**Yesterday's data (no date argument):**
```bash
.\.venv\Scripts\python.exe web_vitals_automation.py android
.\.venv\Scripts\python.exe web_vitals_automation.py ios
```

### Sample Output

```
==================================================
  Web Vitals Automation - Android
  Date: 2026-05-23 (table: events_20260523)
==================================================

[1/2] Querying BigQuery...
  Events processed: 2,603,114

  Metric          p50        p75        p90        p95
  ------------------------------------------------
  LCP            1000       1680       2812       4072
  CLS             0.0        0.0       0.04       0.08
  INP             152        392       1136       1992
  FCP             988       1652       2752       3980
  TTFB          426.1      678.6     1070.3     1685.8
  ------------------------------------------------

[2/2] Updating Google Sheet (Android web vitals)...
  Date '23 May' found in column 130, updating...
  Sheet updated for 23 May!

Done!
```

## Google Sheet Format

The script writes to a specific sheet tab per platform:
- **Android** -> `Android web vitals` tab
- **iOS** -> `IOS web vitals` tab

Each date occupies one column. The row layout is fixed:

| Row | Content |
|-----|---------|
| 1 | Date header (e.g., "23 May") |
| 2 | Day of week (e.g., "Fri") |
| 3 | **LCP** (section header) |
| 4-7 | LCP p50, p75, p90, p95 |
| 8 | **CLS** (section header) |
| 9-12 | CLS p50, p75, p90, p95 |
| 13 | **INP** (section header) |
| 14-17 | INP p50, p75, p90, p95 |
| 18 | **FCP** (section header) |
| 19-22 | FCP p50, p75, p90, p95 |
| 23 | **TTFB** (section header) |
| 24-27 | TTFB p50, p75, p90, p95 |

## Project Structure

```
Web_vitals_automation/
├── web_vitals_automation.py   # Main automation script
├── requirements.txt           # Python dependencies
├── .env                       # Environment config (not in git)
├── .gitignore
├── README.md
└── files/
    ├── python-automation-sa.json  # Service account key (not in git)
    ├── overallwithp75.py          # Original Android CSV script (reference)
    ├── Ios_webvitals.py           # Original iOS CSV script (reference)
    ├── download.csv               # Sample Android CSV (reference)
    └── download_ios.csv           # Sample iOS CSV (reference)
```
