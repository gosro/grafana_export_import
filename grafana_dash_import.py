
import boto3
from botocore.client import Config
import os
import requests
import json
import logging
import uuid
import re

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Grafana settings
GRAFANA_URL = 'http://url:3000'
GRAFANA_API_KEY = 'api_key'

# MinIO settings
MINIO_URL = 'http://url:9000'
MINIO_ACCESS_KEY = 'access_key'
MINIO_SECRET_KEY = 'secret_key'
MINIO_BUCKET = 'bucket_name'

# Backup directories
DASHBOARDS_BACKUP_DIR = 'dashboards_dir_name_to_create'
DATASOURCES_BACKUP_DIR = 'datasources_dir_name_to_create'

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

headers = {
    'Authorization': f'Bearer {GRAFANA_API_KEY}',
    'Accept': 'application/json',
    'Content-Type': 'application/json'
}

# Import datasources to Grafana
try:
    datasources = s3.Bucket(MINIO_BUCKET).objects.filter(Prefix=DATASOURCES_BACKUP_DIR)
    for datasource in datasources:
        filename = datasource.key.split('/')[-1]
        s3.Bucket(MINIO_BUCKET).download_file(datasource.key, filename)
        with open(filename, 'r') as f:
            datasource_json = json.load(f)
        response = requests.post(f'{GRAFANA_URL}/api/datasources', headers=headers, json=datasource_json)
        if response.status_code != 200:
            logging.error(f'Failed to import datasource: {response.content}')
            continue
    logging.info('Datasources import completed.')
except Exception as e:
    logging.error(f'Failed to import datasources: {e}')

# Import dashboards to Grafana
try:
    files = s3.Bucket(MINIO_BUCKET).objects.filter(Prefix=DASHBOARDS_BACKUP_DIR)
    for file in files:
        folder_name, filename = file.key.split('/')[-2:]
        safe_folder_uid = re.sub('[^a-z0-9_-]', '-', folder_name.lower())
        if safe_folder_uid[0].isdigit():
            safe_folder_uid = 'f-' + safe_folder_uid
        s3.Bucket(MINIO_BUCKET).download_file(file.key, filename)
        with open(filename, 'r') as f:
            dashboard_json = json.load(f)
        dashboard_json['dashboard']['id'] = None
        folder_url = f'{GRAFANA_URL}/api/folders/{safe_folder_uid}'
        folder_response = requests.get(folder_url, headers=headers)
        if folder_response.status_code == 404:
            create_folder_data = {'uid': safe_folder_uid, 'title': folder_name}
            create_folder_response = requests.post(f'{GRAFANA_URL}/api/folders', headers=headers, json=create_folder_data)
            if create_folder_response.status_code != 200:
                logging.error(f'Failed to create folder: {create_folder_response.content}')
                continue
            else:
                folder_id = create_folder_response.json().get("id")
        else:
            folder_id = folder_response.json().get("id")
        data = {'dashboard': dashboard_json['dashboard'], 'overwrite': True, 'folderId': folder_id}
        response = requests.post(f'{GRAFANA_URL}/api/dashboards/db', headers=headers, json=data)
        if response.status_code != 200:
            logging.error(f'Failed to import dashboard: {response.content}')
            continue
    logging.info('Dashboards import completed.')
except Exception as e:
    logging.error(f'Failed to import dashboards: {e}')