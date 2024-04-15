from typing import Literal

import requests
from prefect import flow
from pydantic import BaseModel


class AlertmanagerAlert(BaseModel):
    status: str
    labels: dict
    annotations: dict
    startsAt: str
    endsAt: str
    generatorURL: str
    fingerprint: str


class PeerInterfaceFlap(BaseModel):
    """Model to represent the Peer Interface Flap."""

    device: str
    interface: str


@flow(log_prints=True)
def alert_receiver(alert: AlertmanagerAlert):
    """Process the alert."""
    print(f"Processing alert: {alert}")




# @flow(log_prints=True)
# def peer_interface_flap(data: PeerInterfaceFlap, status: Literal["firing", "resolved"]):
#     """Update Nautobot with the latest information."""
#     result = requests.post(
#         url=""
#     )


if __name__ == "__main__":
    _ = alert_receiver.serve(name="alert-receiver")
