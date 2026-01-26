"""Flask API for interview prep - People and Tasks management."""
import csv
import json
from flask import Flask, jsonify, request

app = Flask(__name__)


@app.route('/hello_world', methods=['GET'])
def hello_world():
    """Return a simple hello world response."""
    return jsonify({"hello": "world"}), 200


if __name__ == '__main__':
    app.run(debug=True, port=5001)
