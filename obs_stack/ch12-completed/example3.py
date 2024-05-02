"""Chapter 12 example 1: A simple metric explorer script for Prometheus usin prometheus-api-client."""
from datetime import datetime, timedelta

import requests
from rich import print as rprint


def retrieve_data_loki(query: str, start_time: int, end_time: int) -> list[dict]:
    """Retrieve data from Grafana Loki.
    Args:
        query (str): Loki query
        start_time (int): Start timestamp
        end_time (int): End timestamp
    Returns:
        dict: Loki query result
    """
    response = requests.get(
        url=f"http://localhost:3001/loki/api/v1/query_range",
        params={
            "query": query,
            "start": int(start_time),
            "end": int(end_time),
            "limit": 1000,
        },
    )
    return response.json()["data"]["result"]


def main():
    # Retrieve the logs from ceos-02 over the last 30 minutes
    query = '{device="ceos-02"}'

    # Get the current time and the time 30 minutes ago
    now = datetime.now()
    start_time = datetime.timestamp(now - timedelta(minutes=30))
    end_time = datetime.timestamp(now)

    # Retrieve the logs
    loki_results = retrieve_data_loki(query, start_time, end_time)  # type: ignore

    # Print the results
    rprint(loki_results)


if __name__ == "__main__":
    main()
