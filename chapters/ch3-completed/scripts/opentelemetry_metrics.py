# export FLASK_APP=opentelemetry_metrics
from flask import Flask
from random import randint
from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    ConsoleMetricExporter,
    PeriodicExportingMetricReader,
)

app = Flask(__name__)

metric_reader = PeriodicExportingMetricReader(ConsoleMetricExporter())
provider = MeterProvider(metric_readers=[metric_reader])
metrics.set_meter_provider(provider)
meter = metrics.get_meter("my_opentelemetry_metrics")


@app.route("/")
def entry():
    counter = meter.create_counter("counter")
    counter.add(1)
    return do_something()


def do_something():
    counter = meter.create_counter("counter")
    counter.add(randint(1, 10))
    return "job done"
