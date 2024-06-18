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
    df = pd.DataFrame()

    metric_list = []
    for data in interface_usage:
        data_dict = {}
        # Convert the `seconds` representation of the timestamp into datetime object
        data_dict["ds"] = pd.to_datetime(data[0], unit="s")
        # Save the interface counters value retrieved in a `float` format
        data_dict["y"] = float(data[1])
        metric_list.append(data_dict)

    df_metric = pd.DataFrame(metric_list)

    # Create t1 and t2 references in datetime object to enable comparison operations
    reference_time_t1 = pd.to_datetime(t1, unit="s")
    reference_time_t2 = pd.to_datetime(t2, unit="s")

    # Fabricate historic and current metrics
    historic_metric = df_metric[df_metric["ds"] < reference_time_t1]
    current_metric = df_metric[df_metric["ds"] > reference_time_t2]

    log.debug(historic_metric)
    log.debug(current_metric)

    # Create the model based on historic metrics
    m = Prophet().fit(historic_metric)
    # Create future dataframes and perform prediction
    future = m.make_future_dataframe(periods=150, freq="15s")
    log.debug(future)
    forecast = m.predict(future)
    log.debug(forecast)
    combined_results = pd.merge(current_metric, forecast[["ds", "yhat", "yhat_lower", "yhat_upper"]], on="ds")
    log.debug("Combined current and forecasted metrics")
    log.debug(combined_results)

    combined_results["anomaly"] = combined_results.apply(
        lambda rows: 1 if ((float(rows.y) < rows.yhat_lower) | (float(rows.y) > rows.yhat_upper)) else 0, axis=1
    )
    return combined_results[combined_results["anomaly"] == 1].sort_values(by="ds")


if __name__ == "__main__":
    # This is not necessary for the example, it was used for running it as a standalone script
    interface_usage = get_interface_usage("ceos-01", "Ethernet1")

    df = pd.DataFrame()

    metric_list = []
    for data in interface_usage:
        data_dict = {}
        data_dict["ds"] = pd.to_datetime(data[0], unit="s")
        data_dict["y"] = float(data[1])
        metric_list.append(data_dict)

    df_metric = pd.DataFrame(metric_list)

    # The values of the t1 and t2 were taken during the tests
    t1 = 1708843856.917
    t2 = 1708844051.917
    reference_time_t1 = pd.to_datetime(t1, unit="s")
    reference_time_t2 = pd.to_datetime(t2, unit="s")

    historic_metric = df_metric[df_metric["ds"] < reference_time_t1]
    current_metric = df_metric[df_metric["ds"] > reference_time_t2]

    current_metric.loc[:, "y"] = current_metric["y"] * 2

    m = Prophet().fit(historic_metric)
    future = m.make_future_dataframe(periods=150, freq="15s")
    forecast = m.predict(future)

    combined_results = pd.merge(current_metric, forecast[["ds", "yhat", "yhat_lower", "yhat_upper"]], on="ds")
    combined_results["anomaly"] = combined_results.apply(
        lambda rows: 1 if ((float(rows.y) < rows.yhat_lower) | (float(rows.y) > rows.yhat_upper)) else 0, axis=1
    )
    combined_results["anomaly"].value_counts()

    anomalies = combined_results[combined_results["anomaly"] == 1].sort_values(by="ds")
