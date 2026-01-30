"""Flask API for interview prep - People and Tasks management."""
import csv
import json
from flask import Flask, jsonify

app = Flask(__name__)


@app.route('/hello_world', methods=['GET'])
def hello_world():
    """Return a simple hello world response."""
    return jsonify({"hello": "world"}), 200

############################################
data_store = {"people": [], "tasks": []}

## CSV ingestion
@app.route('/people/csv', methods=['POST'])
def ingest_people_csv():
    with open('people.csv') as f:
        data_store["people"] = list(csv.DictReader(f))
    return jsonify(data_store["people"]), 200

@app.route('/tasks/csv', methods=['POST'])
def ingest_tasks_csv():
    with open('tasks.csv') as f:
        data_store["tasks"] = list(csv.DictReader(f))
    return jsonify(data_store["tasks"]), 200

## JSON ingestion
@app.route('/people/json', methods=['POST'])
def ingest_people_json():
    with open('people.json') as f:
        data_store["people"] = json.load(f)
    return jsonify(data_store["people"]), 200

@app.route('/tasks/json', methods=['POST'])
def ingest_tasks_json():
    with open('tasks.json') as f:
        data_store["tasks"] = json.load(f)
    return jsonify(data_store["tasks"]), 200

## GET endpoints
@app.route('/people', methods=['GET'])
def get_people():
    return jsonify(data_store["people"]), 200

@app.route('/tasks', methods=['GET'])
def get_tasks():
    return jsonify(data_store["tasks"]), 200

## Matching and Grouping Endpoints

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
############################################
if __name__ == '__main__':
    app.run(debug=True, port=5001)


