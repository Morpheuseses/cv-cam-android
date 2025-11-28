package com.example.cv_cam_android;

import android.util.Log;
import org.java_websocket.client.WebSocketClient;
import org.java_websocket.handshake.ServerHandshake;
import org.json.JSONObject;
import java.net.URI;

public class VideoClient {
    private static final String TAG = "VideoClient";
    private WebSocketClient webSocketClient;
    private VideoFrameListener frameListener;

    public interface VideoFrameListener {
        void onFrameReceived(byte[] frameData);
        void onConnectionStatusChanged(boolean connected);
        void onError(String error);
    }

    public VideoClient(VideoFrameListener listener) {
        this.frameListener = listener;
    }

    public void connect(String serverUrl) {
        try {
            Log.d(TAG, "Connecting to: " + serverUrl);

            URI uri = new URI(serverUrl);
            webSocketClient = new WebSocketClient(uri) {
                @Override
                public void onOpen(ServerHandshake handshake) {
                    Log.i(TAG, "WebSocket CONNECTED - Status: " + handshake.getHttpStatus());

                    if (frameListener != null) {
                        frameListener.onConnectionStatusChanged(true);
                    }

                    sendCommand("status");
                }

                @Override
                public void onMessage(String message) {
                    Log.d(TAG, "Raw message length: " + message.length() + " chars");

                    try {
                        JSONObject json = new JSONObject(message);
                        String type = json.getString("type");

                        Log.d(TAG, "Message type: " + type);

                        switch (type) {
                            case "video_frame":
                                String frameData = json.getString("data");
                                Log.d(TAG, "Frame data length: " + frameData.length() + " chars");

                                try {
                                    byte[] decodedFrame = android.util.Base64.decode(frameData, android.util.Base64.DEFAULT);
                                    Log.d(TAG, "Decoded frame size: " + decodedFrame.length + " bytes");

                                    if (frameListener != null) {
                                        frameListener.onFrameReceived(decodedFrame);
                                        Log.d(TAG, "Frame delivered to listener");
                                    } else {
                                        Log.e(TAG, "Frame listener is null!");
                                    }
                                } catch (IllegalArgumentException e) {
                                    Log.e(TAG, "Base64 decoding failed: " + e.getMessage());
                                    if (frameListener != null) {
                                        frameListener.onError("Base64 decoding failed");
                                    }
                                }
                                break;

                            case "connection":
                                String status = json.optString("status", "");
                                String msg = json.optString("message", "");
                                boolean raspberryConnected = json.optBoolean("raspberry_connected", false);
                                Log.i(TAG, "Connection: " + status + " - " + msg);
                                Log.i(TAG, "Raspberry Pi connected: " + raspberryConnected);
                                break;

                            case "ack":
                                String command = json.optString("command", "");
                                String ackStatus = json.optString("status", "");
                                String ackMsg = json.optString("message", "");
                                Log.i(TAG, command + ": " + ackStatus + " - " + ackMsg);
                                break;

                            case "status":
                                boolean rpiConnected = json.optBoolean("raspberry_connected", false);
                                int clientsCount = json.optInt("clients_count", 0);
                                Log.i(TAG, "Status - RPi: " + rpiConnected + ", Clients: " + clientsCount);
                                break;

                            case "error":
                                String errorMsg = json.optString("message", "");
                                Log.e(TAG, "Server error: " + errorMsg);
                                if (frameListener != null) {
                                    frameListener.onError(errorMsg);
                                }
                                break;

                            default:
                                Log.w(TAG, "Unknown message type: " + type);
                        }

                    } catch (Exception e) {
                        Log.e(TAG, "JSON parsing error: " + e.getMessage());
                        Log.e(TAG, "Message content: " + message.substring(0, Math.min(100, message.length())));
                        if (frameListener != null) {
                            frameListener.onError("JSON parsing failed");
                        }
                    }
                }

                @Override
                public void onClose(int code, String reason, boolean remote) {
                    Log.w(TAG, "WebSocket CLOSED - Code: " + code + ", Reason: " + reason + ", Remote: " + remote);

                    if (frameListener != null) {
                        frameListener.onConnectionStatusChanged(false);
                    }
                }

                @Override
                public void onError(Exception ex) {
                    Log.e(TAG, "WebSocket ERROR: " + ex.getMessage());
                    ex.printStackTrace();

                    if (frameListener != null) {
                        frameListener.onConnectionStatusChanged(false);
                        frameListener.onError(ex.getMessage());
                    }
                }
            };

            // Настройка таймаутов
            webSocketClient.setConnectionLostTimeout(30);

            Log.d(TAG, "Starting connection...");
            webSocketClient.connect();

        } catch (Exception e) {
            Log.e(TAG, "Connection failed: " + e.getMessage());
            if (frameListener != null) {
                frameListener.onError("Connection failed: " + e.getMessage());
            }
        }
    }

    public void sendCommand(String command) {
        if (webSocketClient != null && webSocketClient.isOpen()) {
            try {
                JSONObject jsonCommand = new JSONObject();
                jsonCommand.put("command", command);
                webSocketClient.send(jsonCommand.toString());
                Log.d(TAG, "Sent command: " + command);
            } catch (Exception e) {
                Log.e(TAG, "Send command error: " + e.getMessage());
            }
        } else {
            Log.w(TAG, "Cannot send command - WebSocket not connected");
        }
    }

    public void disconnect() {
        if (webSocketClient != null) {
            webSocketClient.close();
            Log.i(TAG, "Disconnected manually");
        }
    }

    public boolean isConnected() {
        return webSocketClient != null && webSocketClient.isOpen();
    }
}
