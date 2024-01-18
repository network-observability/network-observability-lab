import os
import sys
import fileinput
from dataclasses import dataclass
from typing import Optional

import requests
import jmespath
from line_protocol_parser import parse_line
from requests.exceptions import ConnectionError


# Define the Nautobot URL and API token
NAUTOBOT_URL = os.getenv("NAUTOBOT_URL", "")
NAUTOBOT_SUPERUSER_API_TOKEN = os.getenv("NAUTOBOT_SUPERUSER_API_TOKEN", "")


# Nautobot GraphQL query to retrieve device data
NAUTOBOT_DEVICE_GQL = """
query ($device_name: [String]) {
  devices (name: $device_name) {
    name
    id
    interfaces {
      name
      label
      ip_addresses {
        address
      }
    }
  }
}
"""


@dataclass
class InfluxMetric:
    measurement: str
    tags: dict
    fields: dict
    time: Optional[int] = None

    def __str__(self):
        tags_string = ""
        for key, value in self.tags.items():
            if value is not None:
                if isinstance(value, str):
                    value = value.replace(" ", r"\ ")
                tags_string += f",{key}={value}"

        fields_string = ""
        for key, value in self.fields.items():
            if fields_string:
                fields_string += ","
            if isinstance(value, bool):
                fields_string += f"{key}=true" if value else f"{key}=false"
            elif isinstance(value, (int)):
                fields_string += f"{key}={value}i"
            elif isinstance(value, (float)):
                fields_string += f"{key}={value}"
            elif isinstance(value, str):
                value = value.replace(" ", r"\ ")
                fields_string += f'{key}="{value}"'
            else:
                fields_string += f"{key}={value}"

        return (
            f"{self.measurement}{tags_string} {fields_string} {self.time}"
            if self.time
            else f"{self.measurement}{tags_string} {fields_string}"
        )


def get_device_data(device_name) -> Optional[dict]:
    """Retrieve device data from Nautobot GraphQL API if available."""
    # Retrieve the device data from Nautobot GraphQL API
    try:
        response = requests.post(
            url=f"{NAUTOBOT_URL}/api/graphql/",
            headers={"Authorization": f"Token {NAUTOBOT_SUPERUSER_API_TOKEN}"},
            json={
                "query": NAUTOBOT_DEVICE_GQL,
                "variables": {"device_name": device_name},
            },
        )
    except ConnectionError:
        print("[ERROR] Unable to connect to Nautobot GraphQL API", file=sys.stderr, flush=True)
        return None

    # Return the device data
    if response.json()["data"]["devices"]:
        return response.json()["data"]["devices"][0]
    else:
        print(f"[WARNING] Device `{device_name}` data not found in {NAUTOBOT_URL}", file=sys.stderr, flush=True)
        return None


def main():
    # Iterate over the lines of input
    for line in fileinput.input():
        # Parse the line into an InfluxMetric object
        influx_metric = InfluxMetric(**parse_line(line))

        # Extract the device name from the tags
        device_name = influx_metric.tags.get("device")
        if not device_name:
            # Print metric even if device_name is not available
            print(influx_metric, flush=True)
            continue

        # Retrieve device data from Nautobot
        device_data = get_device_data(device_name)
        if not device_data:
            # Print metric even if device data is not available
            print(influx_metric, flush=True)
            continue

        # Create JMESPath expressions to extract and interface data from the device
        jpath = f"interfaces[?name=='{influx_metric.tags['name']}'].label"

        # Extract the interface label from the device data
        intf_role = jmespath.search(jpath, device_data)[0]

        # Add the interface role to the tags
        influx_metric.tags["intf_role"] = intf_role

        # Print the line protocol string
        print(influx_metric, flush=True)


if __name__ == "__main__":
    # Start the processor
    main()
