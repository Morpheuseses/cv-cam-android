import requests
import socket

SERVER_URL = "http://<SERVER_IP>:5000/register"
DEVICE_NAME = "raspberry_pi_1"

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    finally:
        s.close()
    return ip

def register_ip():
    ip = get_local_ip()
    payload = {"device_name": DEVICE_NAME, "ip": ip}
    try:
        response = requests.post(SERVER_URL, json=payload, timeout=5)
        if response.status_code == 200:
            print("Successfully sent:", response.json())
        else:
            print("Registration error:", response.status_code, response.text)
    except Exception as e:
        print("Connection error:", e)

if __name__ == "__main__":
    register_ip()
