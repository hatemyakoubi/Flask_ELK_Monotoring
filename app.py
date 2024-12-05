import os
from flask import Flask, render_template, request, jsonify,redirect, url_for
from datetime import datetime
import time
from elasticsearch import Elasticsearch

app = Flask(__name__)

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
    search_term = request.args.get('search', '').lower()

    try:
        logs = os.listdir(LOG_FILE_DIR)  # Get all files in the directory
    except FileNotFoundError:
        logs = []

    # Only include .log files
    logs = [log for log in logs if log.endswith('.log')]

    log_details = []
    for log in logs:
        log_path = os.path.join(LOG_FILE_DIR, log)
        try:
            # Read the file content
            with open(log_path, 'r', encoding='utf-8') as file:
                content = file.read().lower()

            # Include log if search term matches filename or content
            if not search_term or (search_term in log.lower() or search_term in content):
                log_details.append({
                    'name': log,
                    'created_at': get_file_creation_time(log_path),
                    'content': content[:50] + '...' if len(content) > 50 else content  # Shorten content
                })
        except Exception as e:
            print(f"Error reading file {log_path}: {e}")  # Debugging log

    return render_template('index.html', logs=log_details, search_query=search_term)


@app.route('/add_log', methods=['GET', 'POST'])
def add_log():
    if request.method == 'POST':
        log_message = request.form['log_message']  # Get log message from the form
        log_filename = f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"
        log_file_path = os.path.join(LOG_FILE_DIR, log_filename)

        # Write the log message to a new log file
        with open(log_file_path, 'w') as log_file:
            log_file.write(log_message)
        return redirect(url_for('index'))  # Redirect to the index page to see the updated list
    return render_template('add_log.html')  # If GET request, show the form


@app.route('/search_logs', methods=['POST'])
def search_logs():
    search_query = request.form['search_query']
    
    # Search in Elasticsearch
    response = es.search(index="logs", body={
        "query": {
            "match": {
                "log_message": search_query
            }
        }
    })

    # Extract hits (log entries) from the Elasticsearch response
    logs = [hit["_source"] for hit in response['hits']['hits']]

    return render_template('index.html', logs=logs, log_files=os.listdir(LOG_FILE_DIR))

# Custom filter to convert file size to human-readable format
@app.template_filter('filesize')
def filesize_filter(value):
    size = os.path.getsize(os.path.join(LOG_FILE_DIR, value))
    if size < 1024:
        return f"{size} bytes"
    elif size < 1048576:
        return f"{size / 1024:.2f} KB"
    elif size < 1073741824:
        return f"{size / 1048576:.2f} MB"
    else:
        return f"{size / 1073741824:.2f} GB"

@app.route('/view_log/<filename>')
def view_log(filename):
    log_filepath = os.path.join(LOG_FILE_DIR, filename)

    # Check if the file exists
    if os.path.exists(log_filepath):
        with open(log_filepath, 'r') as log_file:
            log_content = log_file.read()

        # Return the view_log template with both the filename and content
        return render_template('view_log.html', filename=filename, content=log_content)
    else:
        return "Log file not found!", 404


@app.template_filter('file_creation_time')
def file_creation_time(filename):
    log_filepath = os.path.join(LOG_FILE_DIR, filename)
    if os.path.exists(log_filepath):
        timestamp = os.path.getctime(log_filepath)  # Get creation time in seconds
        return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
    return "Unknown"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
