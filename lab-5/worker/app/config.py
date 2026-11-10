import os

DATABASE_URL = os.environ["DATABASE_URL"]
RABBITMQ_URL = os.environ["RABBITMQ_URL"]

OPERATIONS_EXCHANGE = "loyalty"
OPERATIONS_QUEUE = "operations"
OPERATIONS_KEY = "operation"

EVENTS_EXCHANGE = "loyalty.events"
EVENT_QUEUES = ("notifier.events", "analytics.events")

READY_FILE = "/tmp/worker.ready"   # признак готовности для healthcheck
