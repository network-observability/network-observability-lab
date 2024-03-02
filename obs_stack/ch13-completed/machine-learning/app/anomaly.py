import os
import logging
import copy

from prometheus_api_client import PrometheusConnect
from prometheus_api_client.utils import parse_datetime

from prophet import Prophet
import pandas as pd

# FIXME: add to dependencies prophet, plotly, prometheus_api_client


log = logging.getLogger("machine-learning")
pd.set_option('display.max_rows', 200)
pd.set_option('display.max_columns', 15)

def get_interface_usage(
    device: str,
    interface: str,
    # start_time: str = "10m",
    # reference_time: str = "5m",
) -> float:
    """Get the average usage of an interface over a time period."""
    # Connect to Prometheus
    log.info("Connecting to Prometheus...")

    # FIXME: change to prometheus
    prom = PrometheusConnect(url="http://prometheus:9090")

    # Time interval for the query
    # start = parse_datetime(start_time)
    # end = parse_datetime(end_time)
    # log.debug(f"Start time: {start}")
    # log.debug(f"End time: {end}")

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
        data_dict={}
        data_dict['ds'] = pd.to_datetime(data[0], unit='s')
        data_dict['y'] = float(data[1])
        metric_list.append(data_dict)

    df_metric = pd.DataFrame(metric_list)

    reference_time_t1 = pd.to_datetime(t1, unit='s')
    reference_time_t2 = pd.to_datetime(t2, unit='s')

    # Filter samples older than the reference time
    # We ignore the sample of the change
    historic_metric = df_metric[df_metric['ds'] < reference_time_t1]
    current_metric = df_metric[df_metric['ds'] > reference_time_t2]

    log.debug(historic_metric)
    log.debug(current_metric)

    m = Prophet().fit(historic_metric)
    future = m.make_future_dataframe(periods=150, freq="15s")
    log.debug(future)
    forecast = m.predict(future)
    log.debug(forecast)
    combined_results = pd.merge(current_metric, forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']], on='ds')
    log.debug("Combined current and forecasted metrics")
    log.debug(combined_results)

    combined_results['anomaly'] = combined_results.apply(lambda rows: 1 if ((float(rows.y)<rows.yhat_lower)|(float(rows.y)>rows.yhat_upper)) else 0, axis = 1)
    return combined_results[combined_results['anomaly']==1].sort_values(by='ds')



if __name__ == "__main__":
    # FIXME: use real data
    interface_usage = get_interface_usage("ceos-01", "Ethernet1")
    #interface_usage = [[1708842626.917, '12054743'], [1708842641.917, '12054743'], [1708842656.917, '12054743'], [1708842671.917, '12055911'], [1708842686.917, '12055911'], [1708842701.917, '12055911'], [1708842716.917, '12055911'], [1708842731.917, '12056990'], [1708842746.917, '12056990'], [1708842761.917, '12056990'], [1708842776.917, '12056990'], [1708842791.917, '12058069'], [1708842806.917, '12058069'], [1708842821.917, '12058069'], [1708842836.917, '12058069'], [1708842851.917, '12059148'], [1708842866.917, '12059148'], [1708842881.917, '12059148'], [1708842896.917, '12059148'], [1708842911.917, '12060297'], [1708842926.917, '12060297'], [1708842941.917, '12060297'], [1708842956.917, '12060297'], [1708842971.917, '12061465'], [1708842986.917, '12061465'], [1708843001.917, '12061465'], [1708843016.917, '12061465'], [1708843031.917, '12062544'], [1708843046.917, '12062544'], [1708843061.917, '12062544'], [1708843076.917, '12062544'], [1708843091.917, '12063623'], [1708843106.917, '12063623'], [1708843121.917, '12063623'], [1708843136.917, '12063623'], [1708843151.917, '12064702'], [1708843166.917, '12064702'], [1708843181.917, '12064702'], [1708843196.917, '12064702'], [1708843211.917, '12065781'], [1708843226.917, '12065781'], [1708843241.917, '12065781'], [1708843256.917, '12065781'], [1708843271.917, '12066860'], [1708843286.917, '12066860'], [1708843301.917, '12066860'], [1708843316.917, '12066860'], [1708843331.917, '12068009'], [1708843346.917, '12068009'], [1708843361.917, '12068009'], [1708843376.917, '12068009'], [1708843391.917, '12069088'], [1708843406.917, '12069088'], [1708843421.917, '12069088'], [1708843436.917, '12069088'], [1708843451.917, '12070256'], [1708843466.917, '12070256'], [1708843481.917, '12070256'], [1708843496.917, '12070256'], [1708843511.917, '12071335'], [1708843526.917, '12071335'], [1708843541.917, '12071335'], [1708843556.917, '12071335'], [1708843571.917, '12072414'], [1708843586.917, '12072414'], [1708843601.917, '12072414'], [1708843616.917, '12072414'], [1708843631.917, '12073493'], [1708843646.917, '12073493'], [1708843661.917, '12073493'], [1708843676.917, '12073493'], [1708843691.917, '12074642'], [1708843706.917, '12074642'], [1708843721.917, '12074642'], [1708843736.917, '12074642'], [1708843751.917, '12075721'], [1708843766.917, '12075721'], [1708843781.917, '12075721'], [1708843796.917, '12075721'], [1708843811.917, '12076889'], [1708843826.917, '12076889'], [1708843841.917, '12076889'], [1708843856.917, '12076889'], [1708843871.917, '12077968'], [1708843886.917, '12077968'], [1708843901.917, '12077968'], [1708843916.917, '12077968'], [1708843931.917, '12079047'], [1708843946.917, '12079047'], [1708843961.917, '12079047'], [1708843976.917, '12079047'], [1708843991.917, '12080126'], [1708844006.917, '12080126'], [1708844021.917, '12080126'], [1708844036.917, '12080126'], [1708844051.917, '12081364'], [1708844066.917, '12081364'], [1708844081.917, '12081364'], [1708844096.917, '12081364'], [1708844111.917, '12082443'], [1708844126.917, '12082443'], [1708844141.917, '12082443'], [1708844156.917, '12082443'], [1708844171.917, '12083522'], [1708844186.917, '12083522'], [1708844201.917, '12083522'], [1708844216.917, '12083522'], [1708844231.917, '12084601'], [1708844246.917, '12084601'], [1708844261.917, '12084601'], [1708844276.917, '12084601'], [1708844291.917, '12085680'], [1708844306.917, '12085680'], [1708844321.917, '12085680'], [1708844336.917, '12085680'], [1708844351.917, '12086829'], [1708844366.917, '12086829'], [1708844381.917, '12086829'], [1708844396.917, '12086829'], [1708844411.917, '12087908']]

    df = pd.DataFrame()

    metric_list = []
    for data in interface_usage:
        data_dict={}
        data_dict['ds'] = pd.to_datetime(data[0], unit='s')
        data_dict['y'] = float(data[1])
        metric_list.append(data_dict)

    df_metric = pd.DataFrame(metric_list)

    # 1111111111111 - T1 - change and estabilization - T2 - 2222222222 - T3(observation)
    # T1, T2 and T3 user inputs
    # Define the reference time
    t1 = 1708843856.917
    t2 = 1708844051.917
    reference_time_t1 = pd.to_datetime(t1, unit='s')
    reference_time_t2 = pd.to_datetime(t2, unit='s')

    # Filter samples older than the reference time
    # We ignore the sample of the change
    historic_metric = df_metric[df_metric['ds'] < reference_time_t1]
    current_metric = df_metric[df_metric['ds'] > reference_time_t2]

    current_metric.loc[:, "y"] = current_metric["y"] * 2

    m = Prophet().fit(historic_metric)
    future = m.make_future_dataframe(periods=150, freq="15s")
    forecast = m.predict(future)
    # Forecast contains the historic and the forecasting metrics
    # forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']].tail()


    # forecast['error'] = forecast['y'] - forecast['yhat']
    # forecast['uncertainty'] = forecast['yhat_upper'] - forecast['yhat_lower']
    combined_results = pd.merge(current_metric, forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']], on='ds')
    combined_results['anomaly'] = combined_results.apply(lambda rows: 1 if ((float(rows.y)<rows.yhat_lower)|(float(rows.y)>rows.yhat_upper)) else 0, axis = 1)
    combined_results['anomaly'].value_counts()

    anomalies = combined_results[combined_results['anomaly']==1].sort_values(by='ds')
    anomalies
