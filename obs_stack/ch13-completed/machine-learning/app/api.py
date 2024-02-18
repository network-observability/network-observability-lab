import os
import logging
from typing import Literal
from datetime import datetime, timedelta

import fastapi
import requests
from openai import OpenAI
from pydantic import BaseModel

# from app import config
# from app.log import APP

router = fastapi.APIRouter()
log = logging.getLogger("machine-learning")


class AlertmanagerAlert(BaseModel):
    status: str
    labels: dict
    annotations: dict
    startsAt: str
    endsAt: str
    generatorURL: str
    fingerprint: str


class AlertmanagerWebhook(BaseModel):
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


def retrieve_data_loki(query: str, start_timestamp: int, end_time: int) -> dict:
    """Retrieve data from Grafana Loki.
    Args:
        query (str): Loki query
        start_timestamp (int): Start timestamp
        end_time (int): End timestamp
    Returns:
        dict: Loki query result
    """
    log.info("Retrieving data from Loki...")

    # Send the data to Loki
    response = requests.get(
        url=f"http://loki:3001/loki/api/v1/query_range",
        params={
            "query": query,
            "start": int(start_timestamp),
            "end": int(end_time),
            "limit": 1000,
        },
    )
    log.info("Data retrieved from Loki")
    return response.json()["data"]["result"]

def generate_rca_prompt(loki_results, device_name, neighbor_id, neighbor_asn):
    return f"""
    RCA for a BGP neighbor issues:
    Available Data:
    - A BGP session in {device_name} has changed from Established to another non desired state
    - BGP neighbor IP: {neighbor_id}
    - BGP neighbor ASN: {neighbor_asn}
    - Associated Logs: {loki_results}
    Analysis Questions:
    1. Based on the available data, what are the potential causes the lost of BGP Established state?
    2. Did the traffic shift succeeded by looking at the traffic on the secondary site before and after?, and if not why might the automated workflow not have executed as expected?
    3. What system interactions or external factors could have influenced this event?
    Actionable Insights:
    - Given the findings, what immediate actions should be taken to mitigate the current issue?
    - What additional data would be helpful to further investigate this issue?
    Please limit your response to max 2000 characters and use as much data as possble from the available data presented above (devices, interfaces, BGP information, but focusing on the logs) to add more clarification.
    """


def ask_openai(prompt: str, model: str = "gpt-3.5-turbo") -> str:
    """
    Ask OpenAI a question and return the response.
    Args:
        prompt (str): The prompt to send to OpenAI.
        model (str, optional): The model to use. Defaults to "gpt-3.5-turbo".
    Returns:
        str: The response from OpenAI.
    """
    # Construct the prompt for OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": prompt,
            },
        ],
    )

    # Print out the response from OpenAI or send it to the Slack message
    log.info(response)
    return response.choices[0].message.content


@router.post("/v1/api/rca-webhook", status_code=204)
def process_webhook(alertmanager_webhook: AlertmanagerWebhook):
    """Process an alertmanager webhook to provide a Root Cause Analysis."""
    log.info("Alertmanager webhook status is firing, let's provide some educated guesses...")
    log.info(f"Received alertmanager webhook: {alertmanager_webhook.json()}")

    for alert in alertmanager_webhook.alerts:
        device_name = alert.labels["device"]
        now = datetime.now()
        loki_logs = retrieve_data_loki(
            query=f'{{device="{device_name}"}}',
            # Look back for 10 minutes
            start_timestamp=datetime.timestamp(now - timedelta(hours=0, minutes=10)),
            end_time=datetime.timestamp(now)
        )
        log.info(f"Loki logs: {loki_logs}")

        prompt = generate_rca_prompt(loki_logs, device_name, alert.labels["neighbor"], alert.labels["neighbor_asn"])

        rca_response = ask_openai(prompt)

        log.info(f"RCA Analysis: {rca_response}")


    log.info(f"Alert status is {alertmanager_webhook.status}, exiting")
    return {"message": "Processed webhook"}
