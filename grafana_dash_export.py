import requests
import json
import boto3
from botocore.client import Config
import os
import logging

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

headers = {
    'Authorization': f'Bearer {GRAFANA_API_KEY}',
}

# Export datasources from Grafana
response = handle_request(f'{GRAFANA_URL}/api/datasources')

if response:
    for datasource in response.json():
        # Save the datasource data to a JSON file
        try:
            safe_filename = datasource["name"].replace("/", "-")
            with open(f'{safe_filename}.json', 'w') as f:
                json.dump(datasource, f)
        except Exception as e:
            logging.error(f'Failed to save datasource JSON: {e}')
            continue

        # Upload the datasource JSON file to MinIO
        try:
            with open(f'{safe_filename}.json', 'rb') as data:
                s3.Bucket(MINIO_BUCKET).put_object(Key=os.path.join(DATASOURCES_BACKUP_DIR, f'{safe_filename}.json'), Body=data)
        except Exception as e:
            logging.error(f'Failed to upload datasource JSON to MinIO: {e}')
            continue

# Export dashboards from Grafana
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
                            safe_filename = dashboard_data['dashboard']['title'].replace("/", "-")

                            # Save the dashboard data to a JSON file
                            try:
                                with open(f'{safe_filename}.json', 'w') as f:
                                    json.dump(dashboard_data, f)
                            except Exception as e:
                                logging.error(f'Failed to save dashboard JSON: {e}')
                                continue
                           # Upload the dashboard JSON file to MinIO
                            try:
                                with open(f'{safe_filename}.json', 'rb') as data:
                                    s3.Bucket(MINIO_BUCKET).put_object(Key=os.path.join(DASHBOARDS_BACKUP_DIR, folder_data['title'], f'{safe_filename}.json'), Body=data)
                            except Exception as e:
                                logging.error(f'Failed to upload dashboard JSON to MinIO: {e}')
                                continue
logging.info('Export script completed successfult.')