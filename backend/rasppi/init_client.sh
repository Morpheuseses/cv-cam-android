#!/bin/bash

echo 'System Update';
apt update && apt upgrade -y 

apt install python3-venv

mkdir client 
cd client 

echo 'Python venv initialization';
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

echo 'Starting client...'
# 'python3 start_client.py &' or some other file
status=$?

if [ $status -ne 0 ]; then
    echo "Error occurred while starting the client (код $status)"
    exit $status
else
    echo "Client has been successfully started"
fi
