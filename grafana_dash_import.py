import boto3
from botocore.client import Config
import os
import requests
import json
import logging
import uuid

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Grafana settings
GRAFANA_URL = 'http://localhost:3000'
GRAFANA_API_KEY = 'eyJrIjoid1F5cmIzZTFuNEV1M2RWcjQzdjU2TTVWcng4c0FKVEEiLCJuIjoidGVzdCIsImlkIjoxfQ=='

# MinIO settings
MINIO_URL = 'http://192.168.178.44:9000'
MINIO_ACCESS_KEY = 'z87jm0qT4Xr4uJ6UrJd9'
MINIO_SECRET_KEY = 'rrJEtjIWGpxhVy6Mq2YVXR4994y8ykwrqR6ExNp2'
MINIO_BUCKET = 'dashbords'

# Backup directory
BACKUP_DIR = 'grafana_dashboards'

# Initialize MinIO client
try:
    s3 = boto3.resource(
        's3',
        endpoint_url=MINIO_URL,
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
        config=Config(signature_version='s3v4'),
        region_name='us-east-1'
    )
except Exception as e:
    logging.error(f'Failed to initialize MinIO client: {e}')
    exit(1)

# List files in the backup directory in the MinIO bucket
try:
    files = s3.Bucket(MINIO_BUCKET).objects.filter(Prefix=BACKUP_DIR)
except Exception as e:
    logging.error(f'Failed to list files in MinIO bucket: {e}')
    exit(1)

headers = {
    'Authorization': f'Bearer {GRAFANA_API_KEY}',
    'Accept': 'application/json',
    'Content-Type': 'application/json'
}

success = True

# For each file (dashboard), download it, read the JSON, and import to Grafana
for file in files:
    folder_name, filename = file.key.split('/')[-2:]
    
    # Download file
    s3.Bucket(MINIO_BUCKET).download_file(file.key, filename)

    # Read file
    try:
        with open(filename, 'r') as f:
            dashboard_json = json.load(f)
    except Exception as e:
        logging.error(f'Failed to read JSON file: {e}')
        continue

    # Generate a new uid and nullify id for the dashboard
    dashboard_json['uid'] = str(uuid.uuid4())
    dashboard_json['id'] = None

    # Create folder in Grafana if it doesn't exist
    folder_url = f'{GRAFANA_URL}/api/folders/{folder_name}'
    folder_response = requests.get(folder_url, headers=headers)
    if folder_response.status_code == 404:
        create_folder_data = {
            'uid': folder_name,
            'title': folder_name
        }
        create_folder_response = requests.post(f'{GRAFANA_URL}/api/folders', headers=headers, json=create_folder_data)
        if create_folder_response.status_code != 200:
            logging.error(f'Failed to create folder: {create_folder_response.content}')
            continue
        folder_id = create_folder_response.json().get('id')
    else:
        folder_id = folder_response.json().get('id')

    # Import dashboard to Grafana
    data = {
        'dashboard': dashboard_json,
        'overwrite': True,
        'folderId': folder_id
    }
    response = requests.post(f'{GRAFANA_URL}/api/dashboards/db', headers=headers, json=data)
    
    if response.status_code != 200:
        logging.error(f'Failed to import dashboard: {response.content}')
        continue
if success:
    logging.info('Dashboard import script finished successfully.')
else:
    logging.error('Dashboard import script finished with errors.')