#!/bin/bash

echo 'System Update';
apt update -y && apt upgrade -y 

apt install -y python python3-venv

if [ ! -d ".venv" ]; then
  echo 'Python venv initialization';
  python3 -m venv .venv
  source .venv/bin/activate
  pip install -r requirements.txt
  mkdir -p ~/tmp
  TMPDIR=~/tmp pip install --no-cache-dir ultralytics
else 
  echo 'Python venv already exists';
  source .venv/bin/activate
fi

echo 'Starting client...'
python3 rasppi.py 

