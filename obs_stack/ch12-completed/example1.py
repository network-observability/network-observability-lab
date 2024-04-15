"""Chapter 12 example 1: A simple metric explorer script for Prometheus usin prometheus-api-client."""
from rich import print as rprint
from prometheus_api_client import PrometheusConnect

# Create a Prometheus API client
prom = PrometheusConnect(url="http://localhost:9090", disable_ssl=True)

# Get the current value of the bgp_neighbor_state metric for the ceos-01 device
data = prom.get_current_metric_value(metric_name="bgp_neighbor_state", label_config={"device": "ceos-01"})
rprint(data)
