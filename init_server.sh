#!/bin/bash

echo 'System Update';
apt update -y && apt upgrade -y 

apt install -y python3-venv

echo 'Python venv initialization';
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

echo 'Starting server...'
python3 start_server.py

