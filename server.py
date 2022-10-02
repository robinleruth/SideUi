import random

from flask import Flask

app = Flask(__name__)


@app.route("/<id>")
def hello_world(id: str):
    return [{
        "id": id,
        "a": random.choice([1, 2, 3]),
        "b": random.choice(["a", "b", "c"])
    } for _ in range(0, random.randint(1,10))]


if __name__ == '__main__':
    app.run()