import os
import logging
import copy

from prometheus_api_client import PrometheusConnect
from prometheus_api_client.utils import parse_datetime

from prophet import Prophet
import pandas as pd

# FIXME: prophet, plotly, prometheus_api_client


log = logging.getLogger("machine-learning")


def get_interface_usage(
    device: str,
    interface: str,
    # start_time: str = "5m",
    # end_time: str = "now",
) -> float:
    """Get the average usage of an interface over a time period."""
    # Connect to Prometheus
    log.info("Connecting to Prometheus...")

    # FIXME: change to prometheus
    prom = PrometheusConnect(url="http://0.0.0.0:9090")

    # Time interval for the query - last 5 mins
    # start = parse_datetime(start_time)
    # end = parse_datetime(end_time)
    # log.debug(f"Start time: {start}")
    # log.debug(f"End time: {end}")

    # Query to get the Interface In bytes for 10min
    query = f'interface_in_octets{{device="{device}",name="{interface}"}}[10m]'
    log.debug(f"Query: {query}")

    response = prom.custom_query(query)
    log.debug(f"Response: {response}")
    if response is None:
        log.warning("No data found for the query")
        return 0.0

    return response[0]["values"]


if __name__ == "__main__":
    interface_usage = get_interface_usage("ceos-01", "Ethernet1")

    df = pd.DataFrame()


    metric_list = []
    for data in interface_usage:
        data_dict={}
        data_dict['ds'] = pd.to_datetime(data[0], unit='s')
        data_dict['y'] = data[1]
        metric_list.append(data_dict)

    df_metric = pd.DataFrame(metric_list)

    m = Prophet().fit(df_metric)
    future = m.make_future_dataframe(periods=10,freq="min")
    fcst = m.predict(future)
