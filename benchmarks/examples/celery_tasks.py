from celery import Celery

app = Celery("tasks", broker="pyamqp://guest@localhost//")

@app.task
def process_order(order_id):
    print(f"Processing order: {order_id}")
    return True
