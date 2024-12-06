import os
from flask import Flask, render_template, request, jsonify, redirect, url_for
from datetime import datetime
from elasticsearch import Elasticsearch, NotFoundError
from math import ceil
import json

app = Flask(__name__)

# Elasticsearch client
es = Elasticsearch("http://elasticsearch:9200")

# Path where log files are stored inside the container

LOG_FILE_DIR = '/usr/share/logstash/data/logfile'

# Helper to read file content
def open_file_content(filename):
    try:
        filepath = os.path.join(LOG_FILE_DIR, filename)
        with open(filepath, 'r', encoding='utf-8') as file:
            return file.read()
    except FileNotFoundError:
        return "File not found"


# Helper to get file creation time
def get_file_creation_time(filepath):
    try:
        timestamp = os.path.getctime(filepath)
        return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        return "Unknown"

@app.route('/')
def index():
    # Get the search query and page number
    search_query = request.args.get('search_query', '')
    page = int(request.args.get('page', 1))
    page = max(page, 1)  # Ensure valid page number

    try:
        # Elasticsearch query
        if search_query:
            # Determine if the search is for an ID or content
            if search_query.isalnum() and len(search_query) > 5:  # Heuristic for IDs (adjust as needed)
                query = {
                    "query": {
                        "ids": {
                            "values": [search_query]
                        }
                    }
                }
            else:
                query = {
                    "query": {
                        "multi_match": {  # Use multi_match for better text searching
                            "query": search_query,
                            "fields": ["message^2", "message.keyword"]  # Boost "message" for relevance
                        }
                    },
                    "size": 10,
                    "from": (page - 1) * 10,
                    "sort": [{"@timestamp": {"order": "desc"}}]
                }
        else:
            query = {
                "query": {"match_all": {}},
                "size": 10,
                "from": (page - 1) * 10,
                "sort": [{"@timestamp": {"order": "desc"}}]
            }

        # Query Elasticsearch
        response = es.search(index="logs-*,logstash-logs-*", body=query)
        logs = []
        for hit in response['hits']['hits']:
            log = hit['_source']
            created_date = log.get('@timestamp', '')
            if created_date:
                log['formatted_date'] = datetime.strptime(created_date, "%Y-%m-%dT%H:%M:%S.%fZ").strftime("%d-%m-%Y %H:%M:%S")
            log['id'] = hit['_id']
            log['content'] = log.get('message', 'No content available')
            logs.append(log)

        total_logs = response['hits']['total']['value']
        total_pages = max(1, ceil(total_logs / 10))
        page = min(page, total_pages)
        page_range = list(range(max(1, page - 1), min(total_pages + 1, page + 2)))

    except Exception as e:
        logs = []
        total_pages = 1
        page_range = []
        print(f"Error querying Elasticsearch: {e}")

    # Render template
    return render_template(
        'index.html',
        logs=logs,
        search_query=search_query,
        page=page,
        total_pages=total_pages,
        page_range=page_range
    )


@app.route('/add_log', methods=['GET', 'POST'])
def add_log():
    if request.method == 'POST':
        message = request.form.get('message')
        
        if message:  # Ensure message is not empty
            try:
                # Generate the index name dynamically based on the current date
                index_name = f"logs-{datetime.utcnow().strftime('%Y.%m.%d')}"
                
                log_entry = {
                    "@timestamp": datetime.utcnow().isoformat() + "Z",  # Correct timestamp format
                    "message": message
                }
                
                # Index the log in Elasticsearch with the dynamically generated index name
                es.index(index=index_name, body=log_entry)
                print("Log added successfully")
                
                return redirect(url_for('index'))  # Adjust based on your view function
            except Exception as e:
                print(f"Error adding log: {e}")
                return "Error adding log.", 500
        else:
            return "Message is required.", 400

    # For GET request, render the add log form
    return render_template('add_log.html')  # Adjust the template name as per your app

@app.route('/view_log/<log_id>')
def view_log(log_id):
    try:
        print(f"Attempting to retrieve document with ID: {log_id}")
        # Elasticsearch query to fetch document by ID
        response = es.get(index="logs-*,logstash-logs-*", id=log_id)
        print(f"Elasticsearch response: {response}")

        log_content = response['_source']
        return render_template('view_log.html', log_id=log_id, content=log_content)

    except NotFoundError:
        print(f"Document with ID {log_id} not found in Elasticsearch.")
        return "Log not found!", 404

    except Exception as e:
        print(f"Unexpected error occurred while fetching log: {e}")
        return "An error occurred while fetching the log!", 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)