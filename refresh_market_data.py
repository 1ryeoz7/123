"""Run one market/internal-indicator refresh from Task Scheduler or cron."""
from market_scheduler import get_market_data, update_market_data_job


if __name__ == "__main__":
    update_market_data_job()
    for key, item in get_market_data().items():
        print(f"{key}\t{item.get('value')}\t{item.get('data_type')}\t{item.get('fetch_time')}")
