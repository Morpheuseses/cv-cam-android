import requests
import socket
import json
import os

CONFIG_FILE = "config.json"

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    finally:
        s.close()
    return ip

if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, "r") as f:
        config = json.load(f)
else:
    raise RuntimeError("Config file not found!")

DEVICE_NAME = config['device']['name']
DEVICE_PORT = config['device']['port']
ROLE = config['device']['role']
SERVER_URL = f"http://{config['server']['ip']}:{config['server']['port']}/register"

def register_client():
    ip = get_local_ip()
    payload = {"device_name": DEVICE_NAME, "ip": ip, "port": DEVICE_PORT, "role": ROLE}
    try:
        response = requests.post(SERVER_URL, json=payload, timeout=5)
        if response.status_code == 200:
            config['device']['ip'] = ip
            with open(CONFIG_FILE, "w") as f:
                json.dump(config, f, indent=2)
    except Exception as e:
        print("Connection error:", e)

if __name__ == "__main__":
    register_client()
