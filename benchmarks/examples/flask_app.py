from flask import Flask, jsonify, request

app = Flask(__name__)

@app.route("/api/add", methods=["POST"])
def add_numbers():
    data = request.json
    a = data.get("a", 0)
    b = data.get("b", 0)
    result = a + b
    return jsonify({"result": result})

@app.route("/api/greet/<name>", methods=["GET"])
def greet(name):
    return jsonify({"message": f"Hello, {name}!"})

if __name__ == "__main__":
    app.run(port=5000)
