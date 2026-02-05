"""Flask API for interview prep - People and Tasks management."""
import csv
import requests
from flask import Flask, jsonify, request

app = Flask(__name__)

# ============================================================
# curl http://localhost:5001/hello_world
# ============================================================
@app.route('/hello_world', methods=['GET'])
def hello_world():
    return jsonify({"hello": "world"}), 200


data_store = {
    "people": [],
    "tasks": []
}

# Define required fields for each dataset
SCHEMA = {
    "people": {"id", "name", "skill"},
    "tasks": {"customer", "project_id", "category", "prompt", "response"}
}


# ============================================================
# Ingest from local CSV file
# Default:  curl -X POST http://localhost:5001/ingest/people
# Custom:   curl -X POST http://localhost:5001/ingest/people \
#             -H "Content-Type: application/json" \
#             -d '{"filename": "/path/to/people.csv"}'
# ============================================================
@app.route("/ingest/<dataset>", methods=["POST"])
def ingest(dataset):
    # 1. Validate dataset
    if dataset not in data_store:
        return jsonify(error="Invalid dataset"), 400

    # 2. Get filename (from request body or use default)
    body = request.get_json() or {}
    filename = body.get("filename", f"{dataset}.csv")

    # 3. Read CSV file
    with open(filename) as f:
        records = list(csv.DictReader(f))

    # 4. Schema validation
    required = SCHEMA[dataset]
    for i, row in enumerate(records):
        missing = required - row.keys()
        if missing:
            return jsonify(error=f"Row {i} missing fields: {list(missing)}"), 400

    # 5. Save
    data_store[dataset] = records
    return jsonify(status="ok", count=len(records)), 200


# ============================================================
# Option B: Fetch from HTTP URL with API key (uncomment if needed)
# curl -X POST http://localhost:5001/fetch/people \
#   -H "Content-Type: application/json" \
#   -d '{"url": "https://api.example.com/data", "api_key": "your-key"}'
# ============================================================
# import requests
# from flask import request
#
@app.route("/fetch/<dataset>", methods=["POST"])
def fetch(dataset):
    if dataset not in data_store:
        return jsonify(error="Invalid dataset"), 400

    body = request.get_json() or {}
    url = body.get("url")
    api_key = body.get("api_key")

    headers = {"Authorization": f"Bearer {api_key}"}
    response = requests.get(url, headers=headers)

     # If CSV response:
    lines = response.text.splitlines()
    records = list(csv.DictReader(lines))

    # If JSON response:
    records = response.json()

    # Schema validation
    required = SCHEMA[dataset]
    for i, row in enumerate(records):
        missing = required - row.keys()
        if missing:
            return jsonify(error=f"Row {i} missing fields: {list(missing)}"), 400

    data_store[dataset] = records
    return jsonify(status="ok", count=len(records)), 200


# ============================================================
# GET endpoints
# curl http://localhost:5001/people
# curl http://localhost:5001/tasks
# ============================================================
@app.route('/people', methods=['GET'])
def get_people():
    return jsonify(data_store["people"]), 200

@app.route('/tasks', methods=['GET'])
def get_tasks():
    return jsonify(data_store["tasks"]), 200


# ============================================================
# Filtered tasks endpoint (max 5000 rows)
# curl "http://localhost:5001/tasks/filter?category=math"
# curl "http://localhost:5001/tasks/filter?customer=Acme Corp"
# curl "http://localhost:5001/tasks/filter?customer=Acme Corp&category=math"
# ============================================================
MAX_RESULTS = 5000

@app.route('/tasks/filter', methods=['GET'])
def filter_tasks():
    results = data_store["tasks"]

    # Apply filters from query params
    for field in ["customer", "project_id", "category"]:
        value = request.args.get(field)
        if value:
            results = [t for t in results if t.get(field) == value]

    # Cap at 5000
    results = results[:MAX_RESULTS]

    return jsonify(count=len(results), tasks=results), 200


# ============================================================
# Classification endpoints
# curl http://localhost:5001/people/groups
# curl http://localhost:5001/match
# ============================================================
@app.route('/people/groups', methods=['GET'])
def group_people():
    groups = {}
    for person in data_store["people"]:
        skill = person["skill"]
        if skill not in groups:
            groups[skill] = []
        groups[skill].append(person)
    return jsonify(groups), 200


@app.route('/match', methods=['GET'])
def match_people_to_tasks():
    matches = []
    for task in data_store["tasks"]:
        matched_people = [
            p for p in data_store["people"]
            if p["skill"] == task["category"]
        ]
        matches.append({
            "task": task,
            "people": matched_people
        })
    return jsonify(matches), 200


if __name__ == '__main__':
    app.run(debug=True, port=5001)
