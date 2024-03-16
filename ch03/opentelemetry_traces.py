# export FLASK_APP=opentelemetry_traces
from flask import Flask
from time import sleep
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.export import ConsoleSpanExporter


app = Flask(__name__)


provider = TracerProvider()
processor = BatchSpanProcessor(ConsoleSpanExporter())
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)
tracer = trace.get_tracer(__name__)


@app.route("/")
def entry():
    with tracer.start_as_current_span("my_opentelemetry_traces"):
        return do_something()


def do_something():
    with tracer.start_as_current_span("my_opentelemetry_traces"):
        sleep(3)
        return "job done"
