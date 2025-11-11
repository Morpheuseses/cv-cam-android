from flask import Flask, request, jsonify
import json
import os

CONFIG_FILE = "config.json"

app = Flask(__name__)

if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, "r") as f:
        config = json.load(f)
else:
    config = {"server": {"ip": "0.0.0.0", "listen_port": 5000}, "clients": {}}

clients = config.get("clients", {})

def save_config():
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)

@app.route('/register', methods=['POST'])
def register_client():
    data = request.get_json()
    if not data or 'device_name' not in data or 'ip' not in data or 'port' not in data or 'role' not in data:
        return jsonify({'status': 'error', 'message': 'Invalid payload'}), 400

    device_name = data['device_name']
    clients[device_name] = {
        "role": data['role'],
        "ip": data['ip'],
        "port": data['port']
    }

    config['clients'] = clients
    save_config()
    return jsonify({'status': 'ok', 'message': 'Device registered successfully'})

@app.route('/devices', methods=['GET'])
def get_devices():
    return jsonify(clients)

if __name__ == '__main__':
    app.run(host=config['server']['ip'], port=config['server']['listen_port'])
