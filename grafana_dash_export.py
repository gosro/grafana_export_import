import requests
import json
import boto3
from botocore.client import Config
import os
import logging

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

# Function to handle requests
def handle_request(url):
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response
    except requests.exceptions.HTTPError as errh:
        logging.error(f'HTTP Error: {errh}')
    except requests.exceptions.ConnectionError as errc:
        logging.error(f'Error Connecting: {errc}')
    except requests.exceptions.Timeout as errt:
        logging.error(f'Timeout Error: {errt}')
    except requests.exceptions.RequestException as err:
        logging.error(f'Oops: Something Else: {err}')

# Get folders from Grafana
headers = {
    'Authorization': f'Bearer {GRAFANA_API_KEY}',
}

backup_successful = True

response = handle_request(f'{GRAFANA_URL}/api/search')

if response:
    for folder in response.json():
        if folder['type'] == 'dash-folder':
            folder_response = handle_request(f'{GRAFANA_URL}/api/folders/{folder["uid"]}')
            if folder_response:
                folder_data = folder_response.json()

                # Get dashboards within the folder
                folder_dash_response = handle_request(f'{GRAFANA_URL}/api/search?folderIds={folder["id"]}')
                
                if folder_dash_response:
                    for dashboard in folder_dash_response.json():
                        dashboard_response = handle_request(f'{GRAFANA_URL}/api/dashboards/uid/{dashboard["uid"]}')
                        if dashboard_response:
                            dashboard_data = dashboard_response.json()

                            # Save the dashboard data to a JSON file
                            try:
                                with open(f'{dashboard["title"]}.json', 'w') as f:
                                    json.dump(dashboard_data['dashboard'], f)
                            except Exception as e:
                                logging.error(f'Failed to save dashboard JSON: {e}')
                                continue

                            # Upload the dashboard JSON file to MinIO
                            try:
                                with open(f'{dashboard["title"]}.json', 'rb') as data:
                                    s3.Bucket(MINIO_BUCKET).put_object(Key=os.path.join(BACKUP_DIR, folder["title"], f'{dashboard["title"]}.json'), Body=data)
                            except Exception as e:
                                logging.error(f'Failed to upload dashboard JSON to MinIO: {e}')
                                continue
if backup_successful: 
    logging.info('Backup script finished successfully.') 
else: 
    logging.error('Backup script finished with errors.')