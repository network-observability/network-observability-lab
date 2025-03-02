import logging
from typing import Literal

import fastapi
from prefect.deployments import run_deployment
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


@router.post("/v1/api/webhook", status_code=204)
def process_webhook(alert_group: AlertmanagerAlertGroup):
    """Process an alertmanager webhook to send data to Prefect for automated workflows."""
    log.info("Alertmanager webhook status is firing")
    log.info(f"Received alertmanager webhook: {alert_group}")

    _ = run_deployment(
        name="alert-receiver/alert-receiver",
        parameters={"alert_group": alert_group.model_dump(mode="json")},
    )

    log.info(f"Alert status is {alert_group.status}, exiting")
    return {"message": "Processed webhook"}
