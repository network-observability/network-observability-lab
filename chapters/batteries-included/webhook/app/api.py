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


def _link_tag(device: str, interface: str) -> str:
    return f"link:{device}:{interface}".replace("/", "-")


@router.post("/v1/api/webhook", status_code=204)
def process_webhook(alert_group: AlertmanagerAlertGroup):
    """Process an alertmanager webhook to send data to Prefect for automated workflows."""
    log.info("Alertmanager webhook status is firing")
    log.info(f"Received alertmanager webhook: {alert_group}")

    # error = ""
    # try:
    #     _ = run_deployment(
    #         name="alert-receiver/alert-receiver",
    #         parameters={"alert_group": alert_group.model_dump(mode="json")},
    #     )

    #     log.info(f"Alert status is {alert_group.status}, exiting")
    # except Exception as e:
    #     log.error(f"Error running deployment: {e}")
    #     error = str(e)
    # return {"message": "Processed webhook"} if not error else {"error": error}

    error = ""
    try:
        status = alert_group.status
        alertname = alert_group.groupLabels.get("alertname", "unknown")

        pairs = {
            (a.labels.get("device"), a.labels.get("interface"))
            for a in alert_group.alerts
        }
        pairs = {(d, i) for (d, i) in pairs if d and i}
        log.info(
            f"Processinginin {len(pairs)} device/interface pairs for alert '{alertname}' with status '{status}'"
        )

        for device, interface in pairs:
            flow_run_name = f"alert | {alertname}:{status} | {device}:{interface}"

            log.info(f"Submitting Prefect run for {flow_run_name}")

            _ = run_deployment(
                name="alert-receiver/alert-receiver",
                parameters={"alert_group": alert_group.model_dump(mode="json")},
                flow_run_name=f"alert | {alertname}:{status} | {device}:{interface}",
                # tags=[
                #     f"link:{device}:{interface}".replace("/", "-"),
                #     f"alert:{alertname}",
                #     f"status:{status}",
                #     "source:loki",
                # ],
                # idempotency_key=f"{alertname}:{status}:{device}:{interface}:{alert_group.groupKey}",
                # flow_run_name=f"alert | {alertname}:{status} | {device}:{interface}",
                # tags=[
                #     _link_tag(device, interface),
                #     f"alert:{alertname}",
                #     f"status:{status}",
                #     "source:loki",
                # ],
                # idempotency_key=f"{alertname}:{status}:{device}:{interface}:{alert_group.groupKey}",
                timeout=10,
            )

        log.info(
            f"✅ Submitted {len(pairs)} flow run(s) for alert {alertname}:{status}"
        )

        log.info(f"Alert status is {alert_group.status}, exiting")
    except Exception as e:
        log.error(f"Error running deployment: {e}")
        error = str(e)
    return {"message": "Processed webhook"} if not error else {"error": error}
