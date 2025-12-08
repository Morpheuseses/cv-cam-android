import asyncio
import websockets
import json
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class StreamManager:
    def __init__(self):
        self.connected_clients = set()
        self.raspberry_connection = None
        
    async def handle_raspberry_pi(self, websocket):
        client_ip = websocket.remote_address[0]
        logger.info(f"Raspberry Pi connected from {client_ip}")
        self.raspberry_connection = websocket
        
        try:
            await websocket.send(json.dumps({
                "type": "connection",
                "status": "connected", 
                "message": "Raspberry Pi connected successfully"
            }))
            logger.info("Sent connection confirmation to Raspberry Pi")
            
            async for message in websocket:
                try:
                    data = json.loads(message)
                    message_type = data.get("type")
                    
                    logger.info(f"Received from Raspberry Pi: {message_type}")
                    
                    if message_type == "video_frame":
                        if self.connected_clients:
                            clients_count = len(self.connected_clients)
                            await asyncio.gather(
                                *[client.send(message) for client in self.connected_clients],
                                return_exceptions=True
                            )
                            logger.info(f"Frame forwarded to {clients_count} mobile clients")
                        else:
                            logger.warning("No mobile clients to forward frame to")
                    
                    elif message_type == "command":
                        command = data.get("command")
                        logger.info(f"Command from Raspberry Pi: {command}")
                        
                    elif message_type == "ack":
                        logger.info(f"ACK from Raspberry Pi: {data}")
                        
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON from Raspberry Pi: {e}")
                    logger.error(f"Raw message: {message}")
                    
        except websockets.exceptions.ConnectionClosed as e:
            logger.info(f"Raspberry Pi disconnected: {e}")
        except Exception as e:
            logger.error(f"Error with Raspberry Pi: {e}")
        finally:
            self.raspberry_connection = None
            logger.info("Raspberry Pi connection cleaned up")

    async def handle_mobile_client(self, websocket):
        client_ip = websocket.remote_address[0]
        logger.info(f"Mobile client connected from {client_ip}")
        self.connected_clients.add(websocket)
        
        try:
            await websocket.send(json.dumps({
                "type": "connection",
                "status": "connected",
                "message": "Connected to video stream server",
                "raspberry_connected": self.raspberry_connection is not None
            }))
            logger.info("Sent connection confirmation to mobile client")
            
            async for message in websocket:
                try:
                    data = json.loads(message)
                    command = data.get("command")
                    
                    logger.info(f"Command from mobile: {command}")
                    
                    if command == "start_stream":
                        if self.raspberry_connection:
                            await self.raspberry_connection.send(json.dumps({
                                "type": "command",
                                "command": "start_stream",
                                "from": "mobile_client"
                            }))
                            logger.info("Sent start_stream to Raspberry Pi")
                            
                            await websocket.send(json.dumps({
                                "type": "ack",
                                "command": "start_stream",
                                "status": "success",
                                "message": "Command sent to Raspberry Pi"
                            }))
                        else:
                            logger.warning("No Raspberry Pi connected")
                            await websocket.send(json.dumps({
                                "type": "error",
                                "message": "Raspberry Pi not connected"
                            }))
                            
                    elif command == "stop_stream":
                        if self.raspberry_connection:
                            await self.raspberry_connection.send(json.dumps({
                                "type": "command", 
                                "command": "stop_stream",
                                "from": "mobile_client"
                            }))
                            logger.info("Sent stop_stream to Raspberry Pi")
                            
                            await websocket.send(json.dumps({
                                "type": "ack",
                                "command": "stop_stream", 
                                "status": "success",
                                "message": "Command sent to Raspberry Pi"
                            }))
                        else:
                            await websocket.send(json.dumps({
                                "type": "error",
                                "message": "Raspberry Pi not connected"
                            }))
                            
                    elif command == "status":
                        status_info = {
                            "type": "status",
                            "raspberry_connected": self.raspberry_connection is not None,
                            "clients_count": len(self.connected_clients),
                            "timestamp": datetime.now().isoformat()
                        }
                        await websocket.send(json.dumps(status_info))
                        logger.info(f"Status sent: {status_info}")
                        
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON from mobile: {e}")
                    await websocket.send(json.dumps({
                        "type": "error",
                        "message": "Invalid JSON format"
                    }))
                    
        except websockets.exceptions.ConnectionClosed as e:
            logger.info(f"Mobile client disconnected: {e}")
        except Exception as e:
            logger.error(f"Error with mobile client: {e}")
        finally:
            self.connected_clients.discard(websocket)
            logger.info(f"Mobile client removed. Total: {len(self.connected_clients)}")

stream_manager = StreamManager()

async def handler(websocket):
    client_ip = websocket.remote_address[0]
    path = websocket.path if hasattr(websocket, 'path') else "/"
    
    logger.info(f"New connection from {client_ip}, path: '{path}'")
    
    if path == "/raspberry":
        logger.info("Routing to Raspberry Pi handler")
        await stream_manager.handle_raspberry_pi(websocket)
    else:
        logger.info("Routing to mobile client handler")
        await stream_manager.handle_mobile_client(websocket)

async def health_check():
    while True:
        logger.info(f"Health check - Raspberry: {stream_manager.raspberry_connection is not None}, Mobile clients: {len(stream_manager.connected_clients)}")
        await asyncio.sleep(30)

async def main():
    with open('config.json','r') as f:
        server_info = json.loads(f.read())
    server = await websockets.serve(handler, "0.0.0.0", server_info['ACCESS-PORT'])
    logger.info(f"WebSocket server running on ws://0.0.0.0:{server_info['ACCESS-PORT']}")
    logger.info("Available paths:")
    logger.info("  - /raspberry - для Raspberry Pi")
    logger.info("  - / - для мобильных клиентов")
    
    asyncio.create_task(health_check())
    
    await asyncio.Future()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
