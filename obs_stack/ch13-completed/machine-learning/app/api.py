# import json
import logging
from typing import Literal

import fastapi

# from prefect.deployments import run_deployment
# from prefect.settings import PREFECT_API_URL
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


@router.post("/v1/api/machine-learning", status_code=204)
def process_webhook(alertmanager_webhook: AlertmanagerWebhook):
    """Process an alertmanager webhook and run a Prefect deployment."""
    log.info(f"Received alertmanager webhook: {alertmanager_webhook.json()}")
    log.info("Alertmanager webhook status is firing, running deployment")

    # TODO: Add the logic
    # deployment = {
    #     "name": "Network Ops/alertmanager webhook receiver",
    #     "parameters": {
    #         "alertmanager_webhook": alertmanager_webhook.dict(),
    #     },
    # }
    # response = run_deployment(**deployment)
    # log.debug(response)
    # log.info(f"Successfully ran Prefect deployment: {PREFECT_API_URL.value()}")
    log.info(f"Alert status is {alertmanager_webhook.status}, exiting")
    return
