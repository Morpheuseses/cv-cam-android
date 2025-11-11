from flask import Flask, request, jsonify

app = Flask(__name__)

# Storage for IPs
registered_devices = {}

@app.route('/register', methods=['POST'])
def register_device():
    data = request.get_json()
    if not data or 'device_name' not in data or 'ip' not in data:
        return jsonify({'status': 'error', 'message': 'Invalid payload'}), 400

    device_name = data['device_name']
    registered_devices[device_name] = data['ip']
    print(f"[INFO] Registered device {device_name}: {data['ip']}")
    return jsonify({'status': 'ok', 'message': 'Device registered successfully'})

@app.route('/devices', methods=['GET'])
def get_devices():
    return jsonify(registered_devices)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
