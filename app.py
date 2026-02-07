"""Flask API for interview prep - People and Tasks management."""
import csv
from collections import defaultdict
import requests
from flask import Flask, jsonify, request

app = Flask(__name__)

# ============================================================
# curl http://localhost:5001/hello_world
# ============================================================
@app.route('/hello_world', methods=['GET'])
def hello_world():
    return jsonify({"hello": "world"}), 200


# Auto-creates empty list for any dataset name
data_store = defaultdict(list)


# ============================================================
# Ingest from local CSV file
# Default:  curl -X POST http://localhost:5001/ingest/people
# Custom:   curl -X POST http://localhost:5001/ingest/people \
#             -H "Content-Type: application/json" \
#             -d '{"filename": "/path/to/people.csv"}'
# ============================================================
@app.route("/ingest/<dataset>", methods=["POST"])
def ingest(dataset):
    # Get filename (from request body or use default)
    body = request.get_json() or {}
    filename = body.get("filename", f"{dataset}.csv")

    # Read CSV file (schema is inferred from headers)
    with open(filename) as f:
        records = list(csv.DictReader(f))

    # Save to data_store (auto-creates dataset if new)
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
    body = request.get_json() or {}
    url = body.get("url")
    api_key = body.get("api_key")

    headers = {"Authorization": f"Bearer {api_key}"}
    response = requests.get(url, headers=headers)

    # Parse as JSON or CSV based on Content-Type
    if 'json' in response.headers.get('Content-Type', ''):
        records = response.json()
    else:
        lines = response.text.splitlines()
        records = list(csv.DictReader(lines))

    # Save to data_store (auto-creates dataset if new)
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
    groups = defaultdict(list)
    for person in data_store["people"]:
        groups[person["skill"]].append(person)
    return jsonify(groups), 200


@app.route('/match', methods=['GET'])
def match_people_to_tasks():
    # Pre-group people by skill
    people_by_skill = defaultdict(list)
    for person in data_store["people"]:
        people_by_skill[person["skill"]].append(person)

    # Match tasks to people
    matches = []
    for task in data_store["tasks"]:
        matches.append({
            "task": task,
            "people": people_by_skill[task["category"]]
        })
    return jsonify(matches), 200


if __name__ == '__main__':
    app.run(debug=True, port=5001)
