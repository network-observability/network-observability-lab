import logging
from typing import Literal
from datetime import datetime, timedelta

import fastapi
from pydantic import BaseModel

from .rca import (
    retrieve_data_loki,
    generate_rca_prompt,
    ask_openai
)

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

@router.get("/v1/api/prophet")
def check_anomaly(
    device: str | None = fastapi.Query(default=None, description="Filter by device name"),
    interface: str | None = fastapi.Query(default=None, description="Filter by interface name"),
):
    log.info(f"Checking if the interface {interface} in device {device} is having a normal activity")
    status_normal = True
    return {"message": f"Interface {interface} in {device} traffic is " + "normal" if status_normal else "anormal"}

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
