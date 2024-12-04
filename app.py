import os
from flask import Flask, render_template, request, jsonify,redirect, url_for
from datetime import datetime
import time
from elasticsearch import Elasticsearch

app = Flask(__name__)

es = Elasticsearch("http://elasticsearch:9200")
# Path where log files are stored inside the container
LOG_FILE_DIR = '/usr/share/logstash/data/logfile'


@app.route('/')
def index():
    # Get the list of log files in the directory
     search_term = request.args.get('search', '').lower()
    
    # Get all log files in the log directory
     logs = [f for f in os.listdir(LOG_FILE_DIR) if f.endswith('.log')]
    
    # If there's a search term, filter the logs based on the term
     if search_term:
        logs = [log for log in logs if search_term in log.lower()]

    # Return the index page with the filtered list of logs
     return render_template('index.html', logs=logs)

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
