import os
import json
import pandas as pd
from flask import Flask, request, jsonify, render_template
from elasticsearch import Elasticsearch  # Removed ElasticsearchException

app = Flask(__name__)

# Initialize the Elasticsearch client
es = Elasticsearch([{'host': 'elasticsearch', 'port': 9200, 'scheme': 'http'}])   # Adjust hostname if necessary

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/logs', methods=['GET'])
def get_logs():
    try:
        response = es.search(index="logs-*")  # Query Elasticsearch using the client
        # Extract relevant data from the response
        logs = [hit['_source'] for hit in response['hits']['hits']]
        return jsonify(logs)  # Return the list of logs
    except Exception as e:
        app.logger.error(f"Error retrieving logs: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'logFile' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['logFile']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    # Determine the file type and process accordingly
    if file.filename.endswith('.json'):
        return process_json(file)
    elif file.filename.endswith('.csv'):
        return process_csv(file)
    elif file.filename.endswith('.log'):
        return process_log(file)
    else:
        return jsonify({'error': 'Unsupported file type'}), 400

def process_json(file):
    try:
        logs = json.load(file)
        for log in logs:
            response = es.index(index="logs", body=log)  # Index log using Elasticsearch client
            if response['result'] != 'created':
                app.logger.error(f"Failed to upload log: {response}")
        return jsonify({'message': 'JSON logs injected successfully'}), 200
    except json.JSONDecodeError:
        return jsonify({'error': 'Invalid JSON format'}), 400
    except Exception as e:  # Catching generic exceptions
        return jsonify({'error': str(e)}), 500

def process_csv(file):
    try:
        df = pd.read_csv(file)
        for _, row in df.iterrows():
            log_data = {
                'message': row['message'],
                '@timestamp': row['timestamp']
            }
            response = es.index(index="logs", body=log_data)  # Index log using Elasticsearch client
            if response['result'] != 'created':
                app.logger.error(f"Failed to upload log: {response}")
        return jsonify({'message': 'CSV logs injected successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def process_log(file):
    try:
        for line in file:
            log_data = {'message': line.decode('utf-8').strip()}  # Decode bytes to string
            response = es.index(index="logs", body=log_data)  # Index log using Elasticsearch client
            if response['result'] != 'created':
                app.logger.error(f"Failed to upload log: {response}")
        return jsonify({'message': 'LOG files injected successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/test_elasticsearch', methods=['GET'])
def test_elasticsearch():
    try:
        response = es.info()  # Use the Elasticsearch client to check connection
        return jsonify(response), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)