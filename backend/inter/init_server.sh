#!/bin/bash

echo 'System Update';
apt update && apt upgrade -y 

apt install python3-venv

mkdir server
cd server

echo 'Python venv initialization';
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

echo 'Starting server...'
python3 start_server.py &
status=$?

if [ $status -ne 0 ]; then
    echo "Error occurred while starting the server (код $status)"
    exit $status
else
    echo "Server has been successfully started"
fi
