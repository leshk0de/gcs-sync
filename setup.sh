#!/bin/bash

# Variables
CRON_INTERVAL="${1:-5}"  # Default interval is 5 minutes if not provided
SCRIPT_PATH="$(realpath fetch_pubsub_files.py)"  # Absolute path to the Python script
LOG_DIR="$(realpath "$(dirname "$SCRIPT_PATH")/../logs")"  # Absolute path to logs directory
LOG_PATH="$LOG_DIR/gcs-sync.log"
REQUIREMENTS_FILE="requirements.txt"
VENV_DIR="$(dirname "$SCRIPT_PATH")/.venv"  # Virtual environment directory

# Ensure the script is not run as root
if [ "$EUID" -eq 0 ]; then
   echo "Please run this script as a regular user, not as root." 
   exit 1
fi

# Step 1: Create the log directory if it doesn't exist
echo "Ensuring log directory exists at: $LOG_DIR"
mkdir -p "$LOG_DIR"

# Step 2: Create a Python virtual environment if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating Python virtual environment at: $VENV_DIR"
    python3 -m venv "$VENV_DIR"
else
    echo "Virtual environment already exists at: $VENV_DIR"
fi

# Step 3: Activate the virtual environment and upgrade pip, setuptools, and wheel
echo "Activating the virtual environment..."
. "$VENV_DIR/bin/activate"

echo "Updating pip, setuptools, and wheel..."
pip install --upgrade pip setuptools wheel

# Step 4: Install grpcio and grpcio-tools with pre-compiled binaries
echo "Installing grpcio and grpcio-tools..."
pip install --only-binary=:all: grpcio grpcio-tools

# Step 5: Install remaining dependencies from requirements.txt
echo "Installing dependencies from requirements.txt..."
pip install -r "$REQUIREMENTS_FILE"

# Step 6: Set up the cron job
echo "Setting up the cron job to run every $CRON_INTERVAL minutes..."

# Create a temporary cron file
CRON_FILE=$(mktemp)
crontab -l > "$CRON_FILE" 2>/dev/null  # Save existing cron jobs

# Add new cron job for gcs-sync if it doesn't already exist
if ! grep -q "$SCRIPT_PATH" "$CRON_FILE"; then
    echo "*/$CRON_INTERVAL * * * * $VENV_DIR/bin/python $SCRIPT_PATH >> $LOG_PATH 2>&1" >> "$CRON_FILE"
    crontab "$CRON_FILE"
    echo "Cron job installed successfully."
else
    echo "Cron job already exists."
fi

# Clean up
rm "$CRON_FILE"

# Output paths for confirmation
echo "Setup complete."
echo "Python script path: $SCRIPT_PATH"
echo "Virtual environment path: $VENV_DIR"
echo "Log directory path: $LOG_DIR"
echo "Log file path: $LOG_PATH"
echo "Your GCS sync script is now scheduled to run every $CRON_INTERVAL minutes."

# Print the current cron jobs for verification
echo "Current cron jobs for user $(whoami):"
crontab -l
