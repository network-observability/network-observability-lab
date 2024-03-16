import os
import logging
import copy

from prometheus_api_client import PrometheusConnect
from prometheus_api_client.utils import parse_datetime

from prophet import Prophet
import pandas as pd


log = logging.getLogger("machine-learning")
pd.set_option("display.max_rows", 200)
pd.set_option("display.max_columns", 15)


def get_interface_usage(
    device: str,
    interface: str,
) -> float:
    """Get the average usage of an interface over a time period."""
    log.info("Connecting to Prometheus...")

    prom = PrometheusConnect(url="http://prometheus:9090")

    # Query to get the Interface In bytes for last 30min
    query = f'interface_in_octets{{device="{device}",name="{interface}"}}[30m]'
    log.debug(f"Query: {query}")

    response = prom.custom_query(query)
    log.debug(f"Response: {response}")

    return response[0]["values"]


def look_for_anomalies(device, interface, t1, t2):
    interface_usage = get_interface_usage(device, interface)
    log.debug(interface_usage)

    # TODO: DO YOUR FORECASTING CHECK HERE!

    # TODO: REMOVE THIS TO RETURN THE RESULTING DATA FRAME
    class MockResponse:
        empty = True
    return MockResponse()
    ######################################################
