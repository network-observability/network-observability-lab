"""Chapter 12 example 1: A simple metric explorer script for Prometheus usin prometheus-api-client."""
from datetime import datetime, timedelta

import requests
from rich import print as rprint


def retrieve_data_loki(query: str, start_timestamp: int, end_time: int) -> dict:
    """Retrieve data from Grafana Loki.
    Args:
        query (str): Loki query
        start_timestamp (int): Start timestamp
        end_time (int): End timestamp
    Returns:
        dict: Loki query result
    """
    rprint("Retrieving data from Loki...")

    response = requests.get(
        url=f"http://localhost:3001/loki/api/v1/query_range",
        params={
            "query": query,
            "start": int(start_timestamp),
            "end": int(end_time),
            "limit": 1000,
        },
    )
    rprint("Data retrieved from Loki")
    return response.json()["data"]["result"]


def main():
    # Retrieve the logs from ceos-01 over the last 10 minutes
    query = '{device="ceos-01"}'
    now = datetime.now()
    start_timestamp = datetime.timestamp(now - timedelta(hours=0, minutes=10))
    end_time = datetime.timestamp(now)
    loki_results = retrieve_data_loki(query, start_timestamp, end_time)  # type: ignore
    rprint(loki_results)


if __name__ == "__main__":
    main()
