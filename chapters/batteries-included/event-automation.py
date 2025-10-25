import requests
from prefect import flow, task
from prefect.blocks.system import Secret


@task(retries=3, log_prints=True)
def get_nautobot_intf_id(device: str, interface: str) -> str | None:
    """Retrieve the Nautobot Interface ID."""

    # GraphQL query to retrieve the device interfaces information
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

    # Retrieve the Nautobot API token from Prefect Block Secret
    secret_block = Secret.load("nautobot-token")
    nautobot_token = secret_block.get()

    # Get the device information from Nautobot using GraphQL
    response = requests.post(
        url="http://localhost:8080/api/graphql/",
        headers={"Authorization": f"Token {nautobot_token}"},
        json={"query": gql, "variables": {"device": device}},
    )
    response.raise_for_status()

    # Parse the response and return the interface ID
    result = response.json()["data"]["devices"][0]
    for intf in result["interfaces"]:
        if intf["name"] == interface:
            return intf["id"]


@task(retries=3, log_prints=True)
def update_nautobot_intf_state(interface_id: str, status: str) -> bool:
    """Update the device interface status."""

    # Retrieve the Nautobot API token from Prefect Block Secret
    secret_block = Secret.load("nautobot-token")
    nautobot_token = secret_block.get()

    # Mapping Alertmanager status to Nautobot status
    status = "lab-active" if status == "resolved" else "Alerted"

    # Update the interface status
    result = requests.patch(
        url=f"http://localhost:8080/api/dcim/interfaces/{interface_id}/",
        headers={"Authorization": f"Token {nautobot_token}"},
        json={"status": status},
    )
    result.raise_for_status()

    # Print the result to console
    print(f"Interface ID {interface_id} status updated to {status}")

    return True


@flow(log_prints=True)
def interface_flapping_processor(device: str, interface: str, status: str) -> bool:
    """Interface Flapping Event Processor."""

    # Retrieve Nautobot Interface ID
    intf_id = get_nautobot_intf_id(device=device, interface=interface)
    if intf_id is None:
        raise ValueError("Interface not found in Nautobot")

    # Print the interface ID
    print(f"Interface: {interface} == ID: {intf_id}")

    # Update the device interface status in Nautobot
    is_good = update_nautobot_intf_state(interface_id=intf_id, status=status)
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

    # NOTE: Add your alert workflow logic here
    # Check the subject of the alert and forward to respective workflow
    if alertgroup_name == "PeerInterfaceFlapping":
        for alert in alerts:

            # Run the interface flapping processor
            result = interface_flapping_processor(
                device=alert["labels"]["device"],
                interface=alert["labels"]["interface"],
                status=alert_group["status"],
            )

            # Print the result to console
            print(f"Interface Flapping Processor Result: {result}")

    print("Alertmanager Alert Group status processed, exiting")


if __name__ == "__main__":
    _ = alert_receiver.serve(name="alert-receiver")
    # alert_receiver.deploy(
    #     name="alert-receiver-deployment",
    #     work_pool_name="netobs-work-pool",
    #     image="my-registry.com/my-docker-image:my-tag",
    #     push=False # switch to True to push to your image registry
    # )
