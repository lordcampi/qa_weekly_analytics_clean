@echo off
cd /d "%~dp0"
call .venv\Scripts\activate.bat
python -m qa_weekly_analytics.jobs.publish_week %*
