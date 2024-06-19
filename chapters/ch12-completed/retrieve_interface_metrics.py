"""Collect metrics from Prometheus using the prometheus_api_client library."""
import time

from prometheus_api_client import PrometheusConnect
from rich import print as rprint


def retrieve_data_prometheus(query: str) -> list[dict]:
    """Collect metrics from Prometheus."""

    # Create a Prometheus API client
    prom = PrometheusConnect(url="http://localhost:9090", disable_ssl=True)

    # Query Prometheus and return the results
    return prom.custom_query(query=query)


def main():

    # Define the query to collect a sum of the incoming bits/sec for all interfaces on the ceos-01 device
    query = """
    sum by (name) (
        rate(interface_in_octets{device="ceos-01"}[1m]) * 8
    )
    """

    # Get the data
    data = retrieve_data_prometheus(query=query)
    rprint(data)

    time.sleep(30)

    # Get the data again
    data = retrieve_data_prometheus(query=query)
    rprint(data)


if __name__ == "__main__":
    main()
