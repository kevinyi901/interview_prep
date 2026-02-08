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
@app.route("/ingest/<dataset>", methods = ["POST"])
def ingest(dataset):
    #Get file name from body or use default. 
    body = request.get_json(silent= True) or {}
    filename = body.get("filename", f"{dataset}.csv")

    #read csv file
    with open(filename) as f:
        records = list(csv.DictReader(f))
    
    #Save to dataset
    data_store[dataset] = records
    return jsonify(status = "ok", count = len(records)), 200


# ============================================================
# Option B: Fetch from HTTP URL with API key (uncomment if needed)
# curl -X POST http://localhost:5001/fetch/people \
#   -H "Content-Type: application/json" \
#   -d '{"url": "https://api.example.com/data", "api_key": "your-key"}'
# ============================================================
# import requests
# from flask import request
#
# ============================================================
# GET endpoints
# curl http://localhost:5001/people
# curl http://localhost:5001/tasks
# ============================================================
@app.route('/<dataset>', methods = ['GET'])
def get_people(dataset):
    return jsonify(data_store[dataset]), 200


# ============================================================
# Filtered tasks endpoint (max 5000 rows)
# curl "http://localhost:5001/tasks/filter?category=math"
# curl "http://localhost:5001/tasks/filter?customer=Acme Corp"
# curl "http://localhost:5001/tasks/filter?customer=Acme Corp&category=math"
# ============================================================
MAX_RESULTS = 5000

@app.route('/tasks/filter', methods = ['GET'])
def filter_tasks():
    category = request.args.get('category')
    customer = request.args.get('customer')

    results = data_store['tasks']
    if category:
        results = [t for t in results if t['category'] == category]
    if customer:
        results = [t for t in results if t['customer'] == customer]

    return jsonify(results[:MAX_RESULTS]), 200



@app.route('/people/groups', methods = ['GET'])
def group_people():
    groups = defaultdict(list)
    for person in data_store['people']:
        groups[person['skill']].append(person)
    return jsonify(groups), 200

# ============================================================
# Classification endpoints
# curl http://localhost:5001/people/groups
# curl http://localhost:5001/match
# ============================================================
@app.route('/match', methods =['GET'])
def match_people_to_tasks():
    #pre group people by skill
    people_by_skill = defaultdict(list)
    for person in data_store["people"]:
        people_by_skill[person['skill']].append(person)
    
    #match tasks to people
    matches = []
    for task in data_store["tasks"]:
        matches.append({'task':task,
                        "people": people_by_skill[task['category']]})
    return jsonify(matches), 200

if __name__ == '__main__':
    app.run(debug=True, port=5001)
