import os
from typing import Literal

import requests
from prefect import flow, task
from prefect.blocks.system import Secret
from pydantic import BaseModel


class AlertmanagerAlert(BaseModel):
    status: str
    labels: dict
    annotations: dict
    startsAt: str
    endsAt: str
    generatorURL: str
    fingerprint: str


class AlertmanagerAlertGroup(BaseModel):
    version: str
    groupKey: str
    truncatedAlerts: int
    status: Literal["firing", "resolved"]
    receiver: str
    groupLabels: dict
    commonLabels: dict
    commonAnnotations: dict
    externalURL: str
    alerts: list[AlertmanagerAlert]


def get_nautobot_secret() -> str:
    """Retrieve the Nautobot API token from the secret store."""
    secret_block = Secret.load("nautobot-token")
    return secret_block.get()


@task(task_run_name="[RETRIEVE] {device}", log_prints=True)
def retrieve_device_info(device: str) -> dict:
    """Retrieve device information from Nautobot.

    Args:
        device (str): The device name.

    Returns:
        dict: The device information.
    """
    gql = """
    query($device: [String]) {
        devices(name: $device) {
            name
            interfaces {
                name
                id
            }
        }
    }
    """
    response = requests.post(
        url="http://localhost:8080/api/graphql/",
        headers={"Authorization": f"Token {get_nautobot_secret()}"},
        json={"query": gql, "variables": {"device": device}},
    )
    response.raise_for_status()
    return response.json()["data"]["devices"][0]


@task(task_run_name="[UPDATE] {device_info[name]}: {interface} status {status}", log_prints=True)
def update_device_intf_status(device_info: dict, interface: str, status: Literal["firing", "resolved"]) -> bool:
    """Update the device interface status.

    Example device_info:

    {
        "name": "ceos-01",
        "interfaces": [
          {
            "name": "Ethernet1",
            "id": "d3f6335f-1d6c-429f-9c5c-c62f5d6c1363"
          },
          {
            "name": "Ethernet2",
            "id": "5821eda8-affb-4209-bcd8-f39fc6876cc3"
          },
          {
            "name": "Loopback0",
            "id": "79b617b1-d9b7-4ad1-855f-15e02e702b5f"
          },
          {
            "name": "Loopback1",
            "id": "7f81041e-db6f-4002-8315-0ada1467a7b6"
          },
          {
            "name": "Management0",
            "id": "0d513d72-7089-4c7b-b484-8ae5a18caf91"
          }
        ]
      }

    Args:
        device_info (dict): The device information.
        interface (str): The interface name.
        status (Literal["firing", "resolved"]): The status to update.

    Returns:
        bool: True if the status was updated successfully.
    """
    # Search for the interface
    interface_id = None
    for intf in device_info["interfaces"]:
        if intf["name"] == interface:
            interface_id = intf["id"]
            break

    if interface_id is None:
        print(f"Interface {interface} not found on device {device_info['name']}")
        return False

    # Update the interface status
    try:
        result = requests.patch(
            url=f"http://localhost:8080/api/dcim/interfaces/{interface_id}/",
            headers={"Authorization": f"Token {get_nautobot_secret()}"},
            json={"status": "lab-active"} if status == "resolved" else {"status": "Alerted"},
        )
        result.raise_for_status()
    except Exception as e:
        print(f"Failed to update interface {interface} status on device {device_info['name']}: {e}")
        return False

    print(f"Interface {interface} status updated to {status} on device {device_info['name']}")

    return True


@flow(log_prints=True)
def alert_receiver(alert_group: AlertmanagerAlertGroup):
    """Process the alert."""
    print(f"Received alertmanager alert group with status {alert_group.status} -- {alert_group.groupLabels}")
    # Check te subject of the alert and forward to respective workflow
    if alert_group.groupLabels["alertname"] == "PeerInterfaceFlapping":
        for alert in alert_group.alerts:

            # Run the peer interface flap workflow
            result = peer_interface_flap(
                device=alert.labels["device"],
                interface=alert.labels["interface"],
                status=alert_group.status,
            )

            # Print the result to console
            print(f"Peer Interface Flap Workflow Successful: {result}")
    print("Alertmanager Alert Group status processed, exiting")


@flow(flow_run_name="Peer Interface Flap Workflow {device}:{interface} - status {status}", log_prints=True)
def peer_interface_flap(device: str, interface: str, status: Literal["firing", "resolved"]) -> bool:
    """Update Nautobot with the latest information."""
    # Retrieve the device information
    device_info = retrieve_device_info(device=device)
    # Print the device information to console for debug purposes
    print(device_info)
    # Update the device status
    return update_device_intf_status(device_info=device_info, interface=interface, status=status)


if __name__ == "__main__":
    _ = alert_receiver.serve(name="alert-receiver")
