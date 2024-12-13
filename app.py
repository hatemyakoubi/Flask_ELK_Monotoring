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

@app.route('/')
def index():
    search_query = request.args.get('search_query', '')
    page = int(request.args.get('page', 1))
    page = max(page, 1)

    try:
        if search_query:
            if search_query.isalnum():
                query = {
                    "query": {
                        "term": {
                            "_id": search_query
                        }
                    }
                }
            else:
                query = {
                    "query": {"match_all": {}},
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

        response = es.search(index="logstash-logs-*", body=query)
        logs = []
        for hit in response['hits']['hits']:
            log = hit['_source']
            created_date = log.get('@timestamp', '')
            if created_date:
                log['formatted_date'] = datetime.strptime(created_date, "%Y-%m-%dT%H:%M:%S.%fZ").strftime("%d-%m-%Y %H:%M:%S")
            log['id'] = hit['_id']
            log['content'] = log.get('message', 'No content available')
            log['version'] = log.get('@version', 'N/A')
            log['event_original'] = log.get('event.original', 'N/A')
            log['host_name'] = log.get('host.name', 'N/A')
            log['log_file_path'] = log.get('log.file.path', 'N/A')
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
        uploaded_file = request.files.get('file')

        if uploaded_file:
            # Read the entire file content
            file_content = uploaded_file.read().decode('utf-8')  # Read and decode the file content

            # Save the uploaded file (optional)
            file_path = os.path.join(LOG_FILE_DIR, uploaded_file.filename)
            uploaded_file.save(file_path)
            print(f"File uploaded successfully: {file_path}")

            # Log entry for file upload
            log_entry = {
                "@timestamp": datetime.utcnow().isoformat() + "Z",
                "message": file_content,  # Store the entire file content as one log entry
                "file_path": file_path  # Optional: Store file path or additional info
            }
            try:
                es.index(index="logstash-logs-" + datetime.utcnow().strftime("%Y.%m.%d"), body=log_entry)
                return redirect(url_for('index'))
            except Exception as e:
                print(f"Error adding log: {e}")
                return jsonify({"error": "Error adding log", "message": str(e)}), 500

        elif message:  # Handle simple log messages
            try:
                log_entry = {
                    "@timestamp": datetime.utcnow().isoformat() + "Z",
                    "message": message
                }
                es.index(index="logstash-logs-" + datetime.utcnow().strftime("%Y.%m.%d"), body=log_entry)
                print("Log added successfully")
                return redirect(url_for('index'))
            except Exception as e:
                print(f"Error adding log: {e}")
                return jsonify({"error": "Error adding log", "message": str(e)}), 500

        else:
            return "Message or file is required.", 400

    return render_template('add_log.html')


@app.route('/view_log/<log_id>')
def view_log(log_id):
    try:
        response = es.get(index="logstash-logs-*", id=log_id)
        log_content = response['_source']
        return render_template('view_log.html', log_id=log_id, content=log_content)

    except NotFoundError:
        return "Log not found!", 404

    except Exception as e:
        return f"An error occurred: {e}", 500


@app.route('/statistics')
def statistics():
    return render_template('statistics.html')


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
