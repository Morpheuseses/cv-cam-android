import os
import sys
import json
import argparse
import asyncio
import websockets
import base64
import cv2
import numpy as np
import logging
import time
import signal
from datetime import datetime
from ultralytics import YOLO

class JSONConfig:
    
    def __init__(self, config_path="config.json"):
        self.config_path = config_path
        self.data = self.load_config()
        
    def load_config(self):
        try:
            with open(self.config_path, 'r', encoding='utf-8') as file:
                config = json.load(file)
                logging.info(f"Конфигурация загружена из {self.config_path}")
                return config
        except FileNotFoundError:
            logging.error(f"Конфигурационный файл не найден: {self.config_path}")
            sys.exit(1)
        except json.JSONDecodeError as e:
            logging.error(f"Ошибка в формате JSON: {e}")
            sys.exit(1)
    
    def get(self, key, default=None):
        keys = key.split('.')
        value = self.data
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value

class RobustYOLOStreamer:
    def __init__(self, config_path="config.json"):
        self.config = JSONConfig(config_path)
        self.setup_logging()
        
        self.server_url = self.config.get('server.url')
        self.model_path = self.config.get('model.path')
        self.confidence_thresh = self.config.get('model.confidence_threshold', 0.5)
        
        self.camera = None
        self.model = None
        self.labels = None
        self.is_streaming = False
        self.websocket = None
        self.frame_count = 0
        
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = self.config.get('server.max_reconnect_attempts', 10)
        self.reconnect_delay = self.config.get('server.reconnect_delay', 5)
        self.reconnect_backoff = self.config.get('server.reconnect_backoff', 2)
        
        self.last_successful_frame = 0
        self.consecutive_errors = 0
        self.max_consecutive_errors = 5
        
        self.shutdown_requested = False
        self.connection_active = False
        
        self.message_queue = asyncio.Queue()
        
        self.bbox_colors = self.config.get('colors.bbox_colors', [
            [164, 120, 87], [68, 148, 228], [93, 97, 209], [178, 182, 133], [88, 159, 106],
            [96, 202, 231], [159, 124, 168], [169, 162, 241], [98, 118, 150], [172, 176, 184]
        ])
        
        logging.info("Robust YOLO Streamer инициализирован")
        
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

    def signal_handler(self, signum, frame):
        logging.info(f"Получен сигнал {signum}, завершение работы...")
        self.shutdown_requested = True
        self.is_streaming = False

    def setup_logging(self):
        log_level = self.config.get('logging.level', 'INFO')
        log_format = self.config.get('logging.format', '%(asctime)s - %(levelname)s - %(message)s')
        log_file = self.config.get('logging.file')
        
        logging.basicConfig(
            level=getattr(logging, log_level.upper()),
            format=log_format,
            filename=log_file,
            encoding='utf-8',
            force=True
        )
        
        if self.config.get('logging.console', True):
            console_handler = logging.StreamHandler()
            console_handler.setLevel(getattr(logging, log_level.upper()))
            console_handler.setFormatter(logging.Formatter(log_format))
            logging.getLogger().addHandler(console_handler)

    def initialize_model(self):
        try:
            if self.model is not None:
                return True
                
            logging.info("Инициализация YOLO модели...")
            
            if not os.path.exists(self.model_path):
                logging.error(f"Файл модели не найден: {self.model_path}")
                return False
            
            self.model = YOLO(self.model_path, task='detect')
            self.labels = self.model.names
            logging.info(f"YOLO модель загружена. Классы: {len(self.labels)}")
            return True
            
        except Exception as e:
            logging.error(f"Ошибка загрузки YOLO модели: {e}")
            self.model = None
            return False

    def initialize_camera(self):
        max_reconnects = self.config.get('camera.max_camera_reconnects', 5)
        
        for attempt in range(max_reconnects):
            try:
                if self.camera is not None:
                    self.camera.release()
                    self.camera = None
                
                logging.info(f"Попытка инициализации камеры {attempt + 1}/{max_reconnects}...")
                
                device_options = self.config.get('camera.device_options', [0])
                target_width = self.config.get('camera.width', 640)
                target_height = self.config.get('camera.height', 480)
                target_fps = self.config.get('camera.fps', 30)
                
                for camera_option in device_options:
                    try:
                        self.camera = cv2.VideoCapture(camera_option)
                        
                        if self.camera.isOpened():
                            time.sleep(0.5)
                            
                            ret, test_frame = self.camera.read()
                            if ret and test_frame is not None:
                                self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, target_width)
                                self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, target_height)
                                self.camera.set(cv2.CAP_PROP_FPS, target_fps)
                                
                                actual_width = self.camera.get(cv2.CAP_PROP_FRAME_WIDTH)
                                actual_height = self.camera.get(cv2.CAP_PROP_FRAME_HEIGHT)
                                
                                logging.info(f"Камера инициализирована: {camera_option}")
                                logging.info(f"Разрешение: {actual_width}x{actual_height}")
                                return True
                            else:
                                self.camera.release()
                                self.camera = None
                    except Exception as e:
                        logging.warning(f"Камера {camera_option} не доступна: {e}")
                        continue
                
                if attempt < max_reconnects - 1:
                    logging.warning(f"Повторная попытка подключения камеры через 2 секунды...")
                    time.sleep(2)
                    
            except Exception as e:
                logging.error(f"Ошибка инициализации камеры: {e}")
                if attempt < max_reconnects - 1:
                    time.sleep(2)
        
        logging.error("Не удалось инициализировать камеру после всех попыток")
        return False

    async def safe_capture_frame(self):
        try:
            if self.camera is None or not self.camera.isOpened():
                logging.warning("Камера не инициализирована, попытка переподключения...")
                if not self.initialize_camera():
                    return None, False
            
            ret, frame = self.camera.read()
            if not ret or frame is None:
                self.consecutive_errors += 1
                logging.warning(f"Ошибка захвата кадра (ошибка #{self.consecutive_errors})")
                
                if self.consecutive_errors >= self.max_consecutive_errors:
                    logging.error("Превышено максимальное количество ошибок, переинициализация камеры...")
                    if not self.initialize_camera():
                        return None, False
                    self.consecutive_errors = 0
                
                return None, False
            
            self.consecutive_errors = 0
            return frame, True
            
        except Exception as e:
            logging.error(f"Критическая ошибка при захвате кадра: {e}")
            self.consecutive_errors += 1
            return None, False

    def process_frame_with_yolo(self, frame):
        try:
            if self.model is None:
                if not self.initialize_model():
                    return frame, [], 0
            
            results = self.model(frame, verbose=False, conf=self.confidence_thresh)
            detections = results[0].boxes
            
            object_count = 0
            detection_data = []
            
            for i in range(len(detections)):
                xyxy_tensor = detections[i].xyxy.cpu()
                xyxy = xyxy_tensor.numpy().squeeze()
                xmin, ymin, xmax, ymax = xyxy.astype(int)
                
                classidx = int(detections[i].cls.item())
                classname = self.labels[classidx]
                confidence = detections[i].conf.item()
                
                if confidence > self.confidence_thresh:
                    color = tuple(self.bbox_colors[classidx % len(self.bbox_colors)])
                    
                    cv2.rectangle(frame, (xmin, ymin), (xmax, ymax), color, 2)
                    
                    label = f'{classname}: {confidence*100:.1f}%'
                    labelSize, baseLine = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                    label_ymin = max(ymin, labelSize[1] + 10)
                    
                    cv2.rectangle(frame, (xmin, label_ymin-labelSize[1]-10), 
                                 (xmin+labelSize[0], label_ymin+baseLine-10), color, cv2.FILLED)
                    cv2.putText(frame, label, (xmin, label_ymin-7), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
                    
                    object_count += 1
                    detection_data.append({
                        'class': classname,
                        'confidence': float(confidence),
                        'bbox': [int(xmin), int(ymin), int(xmax), int(ymax)],
                        'class_id': classidx
                    })
            
            if hasattr(self, 'current_fps'):
                cv2.putText(frame, f'FPS: {self.current_fps:.1f}', (10, 20), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
                cv2.putText(frame, f'Objects: {object_count}', (10, 50), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            
            return frame, detection_data, object_count
            
        except Exception as e:
            logging.error(f"Ошибка обработки YOLO: {e}")
            return frame, [], 0

    async def safe_send_frame(self, frame, detection_data, object_count):
        try:
            if self.websocket is None or self.websocket.closed:
                logging.warning("WebSocket соединение разорвано")
                return False
            
            jpeg_quality = self.config.get('stream.jpeg_quality', 70)
            _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality])
            base64_frame = base64.b64encode(buffer).decode('utf-8')
            
            message_data = {
                "type": "video_frame",
                "data": base64_frame,
                "frame_id": self.frame_count,
                "timestamp": time.time(),
                "detections": detection_data,
                "object_count": object_count,
                "fps": getattr(self, 'current_fps', 0)
            }
            
            await asyncio.wait_for(
                self.websocket.send(json.dumps(message_data)),
                timeout=5.0
            )
            
            self.frame_count += 1
            self.last_successful_frame = time.time()
            
            if self.frame_count % 30 == 0:
                logging.info(f"Отправлен кадр {self.frame_count}, объектов: {object_count}")
            
            return True
            
        except asyncio.TimeoutError:
            logging.warning("Таймаут отправки кадра")
            return False
        except websockets.exceptions.ConnectionClosed:
            logging.warning("Соединение закрыто при отправке")
            return False
        except Exception as e:
            logging.error(f"Ошибка отправки кадра: {e}")
            return False

    async def health_check(self):
        try:
            if self.websocket and not self.websocket.closed:
                await asyncio.wait_for(
                    self.websocket.ping(),
                    timeout=5.0
                )
                return True
        except:
            pass
        return False

    async def message_handler(self):
        try:
            async for message in self.websocket:
                try:
                    data = json.loads(message)
                    await self.message_queue.put(data)
                except json.JSONDecodeError as e:
                    logging.error(f"Невалидный JSON: {e}")
        except websockets.exceptions.ConnectionClosed:
            logging.info("Соединение закрыто в обработчике сообщений")
        except Exception as e:
            logging.error(f"Ошибка в обработчике сообщений: {e}")

    async def process_commands(self):
        while self.connection_active:
            try:
                data = await asyncio.wait_for(self.message_queue.get(), timeout=1.0)
                
                message_type = data.get("type")
                command = data.get("command")
                
                logging.info(f"Получено сообщение: {message_type}, команда: {command}")
                
                if message_type == "command":
                    if command == "start_stream":
                        if not self.is_streaming:
                            logging.info("Получена команда start_stream")
                            if not self.initialize_camera():
                                logging.error("Не удалось инициализировать камеру")
                                continue
                            if not self.initialize_model():
                                logging.error("Не удалось инициализировать модель")
                                continue
                            self.is_streaming = True
                            await self.send_ack("start_stream", "success", "Поток запущен")
                        else:
                            logging.info("Поток уже запущен")
                            
                    elif command == "stop_stream":
                        if self.is_streaming:
                            logging.info("Получена команда stop_stream")
                            self.is_streaming = False
                            await self.send_ack("stop_stream", "success", "Поток остановлен")
                        else:
                            logging.info("Поток уже остановлен")
                            
                    elif command == "update_threshold":
                        new_thresh = data.get("threshold", self.confidence_thresh)
                        old_thresh = self.confidence_thresh
                        self.confidence_thresh = new_thresh
                        logging.info(f"Порог уверенности изменен: {old_thresh} -> {new_thresh}")
                        await self.send_ack("update_threshold", "success", f"Порог обновлен на {new_thresh}")
                        
                    elif command == "get_status":
                        status = self.get_status()
                        await self.websocket.send(json.dumps({
                            "type": "status",
                            "data": status
                        }))
                        
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logging.error(f"Ошибка обработки команды: {e}")

    async def send_ack(self, command, status, message):
        if self.websocket and not self.websocket.closed:
            try:
                await self.websocket.send(json.dumps({
                    "type": "ack",
                    "command": command,
                    "status": status,
                    "message": message
                }))
            except Exception as e:
                logging.error(f"Ошибка отправки подтверждения: {e}")

    def get_status(self):
        return {
            "streaming": self.is_streaming,
            "frame_count": self.frame_count,
            "fps": getattr(self, 'current_fps', 0),
            "camera_initialized": self.camera is not None and self.camera.isOpened(),
            "model_loaded": self.model is not None,
            "confidence_threshold": self.confidence_thresh,
            "connection_active": self.connection_active
        }

    async def streaming_loop(self):
        logging.info("Запуск цикла потоковой передачи")
        
        fps_counter = 0
        fps_time = time.time()
        last_health_check = time.time()
        health_check_interval = 30  

        while self.is_streaming and not self.shutdown_requested:
            try:
                if not self.is_streaming:
                    logging.info("Флаг is_streaming сброшен, остановка потока")
                    break
                
                current_time = time.time()
                if current_time - last_health_check > health_check_interval:
                    if not await self.health_check():
                        logging.warning("Проверка здоровья не пройдена, переподключение...")
                        break
                    last_health_check = current_time
                
                frame, success = await self.safe_capture_frame()
                if not success:
                    await asyncio.sleep(0.1)
                    continue
                
                processed_frame, detection_data, object_count = self.process_frame_with_yolo(frame)
                
                fps_counter += 1
                if current_time - fps_time >= 1.0:
                    self.current_fps = fps_counter / (current_time - fps_time)
                    fps_counter = 0
                    fps_time = current_time
                
                send_success = await self.safe_send_frame(processed_frame, detection_data, object_count)
                if not send_success:
                    logging.warning("Ошибка отправки, переподключение...")
                    break
                
                target_fps = self.config.get('stream.target_fps', 15)
                await asyncio.sleep(max(0, 1.0 / target_fps - 0.01)) 
                
            except Exception as e:
                logging.error(f"Критическая ошибка в цикле потоковой передачи: {e}")
                break
        
        self.is_streaming = False
        logging.info("Цикл потоковой передачи остановлен")

    async def manage_connection(self):
        self.reconnect_attempts = 0
        
        while not self.shutdown_requested:
            try:
                logging.info(f"Подключение к {self.server_url} (попытка {self.reconnect_attempts + 1})")
                
                async with websockets.connect(
                    self.server_url,
                    ping_interval=self.config.get('server.ping_interval', 20),
                    ping_timeout=self.config.get('server.ping_timeout', 40)
                ) as websocket:
                    self.websocket = websocket
                    self.connection_active = True
                    self.reconnect_attempts = 0
                    
                    logging.info("Успешное подключение к серверу")
                    
                    message_task = asyncio.create_task(self.message_handler())
                    command_task = asyncio.create_task(self.process_commands())
                    
                    try:
                        while self.connection_active and not self.shutdown_requested:
                            if self.is_streaming:
                                await self.streaming_loop()
                            else:
                                await asyncio.sleep(0.1)
                                
                    except Exception as e:
                        logging.error(f"Ошибка в основном цикле управления: {e}")
                    finally:
                        self.connection_active = False
                        message_task.cancel()
                        command_task.cancel()
                        try:
                            await asyncio.gather(message_task, command_task, return_exceptions=True)
                        except:
                            pass
                    
            except ConnectionRefusedError:
                logging.error(f"Сервер отказал в подключении: {self.server_url}")
            except Exception as e:
                logging.error(f"Ошибка подключения: {e}")
            
            self.cleanup()
            
            self.reconnect_attempts += 1
            if self.reconnect_attempts >= self.max_reconnect_attempts:
                logging.error(f"Превышено максимальное количество попыток подключения ({self.max_reconnect_attempts})")
                break
            
            delay = min(self.reconnect_delay * (self.reconnect_backoff ** (self.reconnect_attempts - 1)), 60)
            logging.info(f"Повторное подключение через {delay} секунд...")
            await asyncio.sleep(delay)

    def cleanup(self):
        logging.info("Очистка ресурсов...")
        
        self.is_streaming = False
        self.connection_active = False
        
        if self.camera:
            self.camera.release()
            self.camera = None
        
        if self.websocket:
            self.websocket = None

    async def run(self):
        try:
            logging.info("Запуск Robust YOLO Streamer")
            logging.info(f"Модель: {self.model_path}")
            logging.info(f"Сервер: {self.server_url}")
            
            await self.manage_connection()
            
        except Exception as e:
            logging.error(f"Критическая ошибка: {e}")
        finally:
            self.cleanup()
            logging.info("Robust YOLO Streamer завершен")

def main():
    parser = argparse.ArgumentParser(description='Robust YOLO Streamer')
    parser.add_argument('--config', default='config.json', help='Path to config file')
    parser.add_argument('--model', help='Override model path')
    parser.add_argument('--server', help='Override server URL')
    
    args = parser.parse_args()
    
    try:
        streamer = RobustYOLOStreamer(args.config)
        
        if args.model:
            streamer.model_path = args.model
        if args.server:
            streamer.server_url = args.server
        
        asyncio.run(streamer.run())
        
    except KeyboardInterrupt:
        logging.info("Программа завершена пользователем")
    except Exception as e:
        logging.error(f"Ошибка: {e}")

if __name__ == "__main__":
    main()

