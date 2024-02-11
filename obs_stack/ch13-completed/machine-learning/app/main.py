import logging
from logging.config import dictConfig

import fastapi
import uvicorn
from app import config
from app import api

# from app.log import initialize_logging, APP

dictConfig(config.LogConfig().dict())
log = logging.getLogger("machine-learning")


app = fastapi.FastAPI()
config.load()


def configure_routing():
    app.include_router(api.router)


def configure():
    configure_routing()


@app.get("/")
def index():
    return {"message": "Working!"}


if __name__ == "__main__":
    configure()
    log.info("Running as script.")
    uvicorn.run(app, port=config.SETTINGS.port, host=config.SETTINGS.host)  # type: ignore
else:
    log.info("Running as library.")
    configure()
