@echo off
cd /d "C:\Users\Indiamart\Desktop\Web_vitals_automation"
.\.venv\Scripts\python.exe web_vitals_automation.py ios >> logs\ios_daily.log 2>&1
