"""Chapter 12 example 1: A simple metric explorer script for Prometheus usin prometheus-api-client."""
import time

from rich import print as rprint
from prometheus_api_client import PrometheusConnect

# Create a Prometheus API client
prom = PrometheusConnect(url="http://localhost:9090", disable_ssl=True)

# Define the query to collect a sum of the incoming bits/sec for all interfaces on the ceos-01 device
query = 'sum(rate(interface_in_octets{device="ceos-01"}[1m]) * 8) by (name)'
# Get the data
data = prom.custom_query(query)
rprint(data)
# Sleep for 30 seconds
time.sleep(30)
# Get the data again
data = prom.custom_query(query)
rprint(data)
