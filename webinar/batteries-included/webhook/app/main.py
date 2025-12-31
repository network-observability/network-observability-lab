import logging
import os
import re
from logging.config import dictConfig

import fastapi
import uvicorn
from app import config
from app import api


dictConfig(config.LogConfig().dict())
log = logging.getLogger("webhook")


app = fastapi.FastAPI()
config.load()


def configure_routing():
    app.include_router(api.router)


def configure():
    configure_routing()


def validate_prefect_api_url():
    # Fetch the environment variable
    url = os.getenv("PREFECT_API_URL")

    if not url:
        raise ValueError("PREFECT_API_URL environment variable is not set.")

    # Define the regex pattern for the URL
    pattern = re.compile(
        r"^https://api\.prefect\.cloud/api/accounts/[a-fA-F0-9\-]+/workspaces/[a-fA-F0-9\-]+$"
    )

    # Validate the URL
    if not pattern.match(url):
        raise ValueError(
            "PREFECT_URL is not in the expected format: "
            "https://api.prefect.cloud/api/accounts/[ACCOUNT-ID]/workspaces/[WORKSPACE-ID]."
        )

    log.info("PREFECT_URL is valid.")
    return True


@app.get("/")
def index():
    return {"message": "The Webhook service is waiting for your requests!"}


if __name__ == "__main__":
    configure()
    log.info("Running as script. Host and port from config.")
    try:
        validate_prefect_api_url()
    except ValueError as e:
        log.error(e)
    uvicorn.run(app, port=config.SETTINGS.port, host=config.SETTINGS.host)  # type: ignore
else:
    log.info("Running as library.")
    configure()
