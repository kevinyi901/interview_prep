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
    # Get file name from body or use default


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

# ============================================================
# Filtered tasks endpoint (max 5000 rows)
# curl "http://localhost:5001/tasks/filter?category=math"
# curl "http://localhost:5001/tasks/filter?customer=Acme Corp"
# curl "http://localhost:5001/tasks/filter?customer=Acme Corp&category=math"
# ============================================================
MAX_RESULTS = 5000


# ============================================================
# Classification endpoints
# curl http://localhost:5001/people/groups
# curl http://localhost:5001/match
# ============================================================


if __name__ == '__main__':
    app.run(debug=True, port=5001)
