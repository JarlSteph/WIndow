"""
scheduler.py — Run the Daily Window pipeline every day at 08:00.

Usage:
    python scheduler.py

Alternatively, set up a system cron job (macOS / Linux):
    0 8 * * * cd /path/to/window && python main.py >> output/cron.log 2>&1
"""

import time
import schedule
from main import run


def main():
    print("Scheduler started — Daily Window will run at 08:00 each day.")
    schedule.every().day.at("08:00").do(run)

    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    main()
