import os
import json
import time
import logging
from datetime import datetime
from concurrent.futures import TimeoutError
from google.cloud import storage, pubsub_v1

def load_config(config_file='config.json'):
    """Load configuration from the specified JSON file."""
    with open(config_file, 'r') as f:
        return json.load(f)

def initialize_clients(service_account_path):
    """Initialize the GCS and Pub/Sub clients."""
    storage_client = storage.Client.from_service_account_json(service_account_path)
    pubsub_client = pubsub_v1.SubscriberClient()
    return storage_client, pubsub_client

def setup_logger():
    """Set up logging to both stdout and a log file."""
    timestamp = datetime.utcnow().strftime('%Y%m%d-%H%M%S')
    log_filename = f"gcs-fetcher-{timestamp}.log"
    log_path = os.path.join("/tmp", log_filename)

    # Create logger
    logger = logging.getLogger("gcs_fetcher")
    logger.setLevel(logging.INFO)

    # File handler
    file_handler = logging.FileHandler(log_path)
    file_handler.setLevel(logging.INFO)
    file_formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')
    file_handler.setFormatter(file_formatter)

    # Stream handler (stdout)
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(file_formatter)

    # Add handlers to logger
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)

    return logger, log_path

def upload_log_to_gcs(log_path, bucket_name, storage_client, logger):
    """Upload the log file to GCS under /logs/gcs-fetcher-script/."""
    log_blob_name = f"logs/gcs-fetcher-script/{os.path.basename(log_path)}"
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(log_blob_name)
    
    logger.info(f"Uploading log file {log_path} to GCS at {log_blob_name}")
    blob.upload_from_filename(log_path)
    logger.info(f"Log file {log_path} successfully uploaded.")

def download_file(bucket_name, blob_name, destination_path, storage_client, logger):
    """Download a specific file from GCS."""
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    destination_file = os.path.join(destination_path, blob_name)
    
    os.makedirs(os.path.dirname(destination_file), exist_ok=True)
    logger.info(f"Downloading {blob_name} to {destination_file}")
    blob.download_to_filename(destination_file)

def handle_message(message, storage_client, config, logger):
    """Handle a single Pub/Sub message."""
    try:
        data = json.loads(message.data.decode('utf-8'))
        file_name = data.get('name')  # File name in GCS
        if file_name:
            download_file(config['gcs_bucket_name'], file_name, config['destination_path'], storage_client, logger)
    except Exception as e:
        logger.error(f"Failed to handle message: {e}")
    message.ack()

def fetch_messages(pubsub_client, subscription, timeout, storage_client, config, logger):
    """Listen for Pub/Sub messages and handle them."""
    def callback(message):
        handle_message(message, storage_client, config, logger)

    future = pubsub_client.subscribe(subscription, callback=callback)
    logger.info(f"Listening for messages on {subscription} for {timeout} seconds...")

    try:
        future.result(timeout=timeout)
    except TimeoutError:
        logger.info("Stopped listening after timeout.")
        future.cancel()

if __name__ == "__main__":
    # Load configuration
    config = load_config()
    storage_client, pubsub_client = initialize_clients(config['service_account_path'])

    # Set up logging
    logger, log_path = setup_logger()

    # Fetch and process messages for 15 seconds
    fetch_messages(
        pubsub_client=pubsub_client,
        subscription=config['pubsub_subscription'],
        timeout=15,
        storage_client=storage_client,
        config=config,
        logger=logger
    )

    # Upload the log file to GCS
    upload_log_to_gcs(log_path, config['gcs_bucket_name'], storage_client, logger)
