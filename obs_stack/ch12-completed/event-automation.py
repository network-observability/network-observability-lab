import requests
from prefect import flow, task


def get_nautobot_secret() -> str:
    """Retrieve the Nautobot API token from the secret store."""
    secret_block = Secret.load("nautobot-token")
    return secret_block.get()


@task(task_run_name="[RETRIEVE] {device}", retries=3, log_prints=True)
def get_nautobot_intf_id(device: str, interface: str) -> str | None:
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
    result = response.json()["data"]["devices"][0]
    for intf in result["interfaces"]:
        if intf["name"] == interface:
            return intf["id"]


@flow(flow_run_name="Update Nautobot {device}:{interface} - status {status}", log_prints=True)
def update_nautobot_intf_state(device: str, interface: str, status: str) -> bool:
    """Update Nautobot with the latest information."""
    # Retrieve Nautobot Interface ID
    intf_id = get_nautobot_intf_id(device=device, interface=interface)

    # Print the interface ID
    print(f"Interface: {interface} == ID: {intf_id}")

    # Update the device interface status in Nautobot
    is_good = update_device_intf_status(intf_id=intf_id, status=status)
    return is_good

@flow(log_prints=True)
def alert_receiver(alert_group: dict):
    """Process the alert."""
    # Status of the alert group
    status = alert_group["status"]

    # Name of the alert group
    alertgroup_name = alert_group["groupLabels"]["alertname"]

    # Alerts in the alert group
    alerts = alert_group["alerts"]

    print(f"Received alert group: {alertgroup_name} - {status}")

    # Check the subject of the alert and forward to respective workflow
    if alertgroup_name == "PeerInterfaceFlapping":
        for alert in alerts:

            # Run the peer interface flap workflow
            result = update_nautobot_intf_state(
                device=alert["labels"]["device"],
                interface=alert["labels"]["interface"],
                status=alert_group["status"],
            )

            # Print the result to console
            print(f"Peer Interface Flap Workflow Successful: {result}")

    print("Alertmanager Alert Group status processed, exiting")


if __name__ == "__main__":
    _ = alert_receiver.serve(name="alert-receiver")
