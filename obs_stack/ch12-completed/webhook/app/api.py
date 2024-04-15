import logging
from typing import Literal

import fastapi
from prefect.deployments.deployments import run_deployment
from pydantic import BaseModel


router = fastapi.APIRouter()
log = logging.getLogger("webhook")


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


@router.post("/v1/api/webhook", status_code=204)
def process_webhook(alertmanager_webhook: AlertmanagerWebhook):
    """Process an alertmanager webhook to provide a Root Cause Analysis."""
    log.info("Alertmanager webhook status is firing, let's provide some educated guesses...")
    log.info(f"Received alertmanager webhook: {alertmanager_webhook}")

    for alert in alertmanager_webhook.alerts:
        _ = run_deployment(
            name="alert-receiver",
            parameters=alert.model_dump(),
        )

    log.info(f"Alert status is {alertmanager_webhook.status}, exiting")
    return {"message": "Processed webhook"}
