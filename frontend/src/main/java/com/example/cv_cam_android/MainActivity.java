package com.example.cv_cam_android;

import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.os.Bundle;
import android.os.Handler;
import android.util.Log;
import android.view.Menu;
import android.view.MenuItem;
import android.widget.Button;
import android.widget.ImageView;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;
import androidx.appcompat.widget.Toolbar;

public class MainActivity extends AppCompatActivity implements VideoClient.VideoFrameListener {

    private static final String TAG = "MainActivity";
    private VideoClient videoClient;
    private ImageView imageView;
    private Button btnStart, btnStop;
    private boolean isConnected = false;
    private long lastFrameTime = 0;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        initializeUI();
        initializeVideoClient();
    }

    private void initializeUI() {
        Toolbar toolbar = findViewById(R.id.toolbar);
        setSupportActionBar(toolbar);

        imageView = findViewById(R.id.image_view);
        btnStart = findViewById(R.id.btn_start);
        btnStop = findViewById(R.id.btn_stop);

        btnStart.setOnClickListener(v -> {
            if (isConnected) {
                videoClient.sendCommand("start_stream");
                showToast(getString(R.string.StreamInitializationMessage));
            } else {
                showToast(getString(R.string.NoServerConnectionMessage));
            }
        });

        btnStop.setOnClickListener(v -> {
            if (isConnected) {
                videoClient.sendCommand("stop_stream");
                showToast(getString(R.string.StreamStoppingMessage));

                imageView.setImageBitmap(null);
            }
        });

        updateButtonStates();
    }

    private void initializeVideoClient() {
        videoClient = new VideoClient(this);

        new Handler().postDelayed(this::connectToServer, 1000);
    }

    private void connectToServer() {
        SharedPreferences prefs = getSharedPreferences("settings", MODE_PRIVATE);
        String serverUrl = prefs.getString("stream_url", "");

        if (serverUrl.isEmpty()) {
            showToast(getString(R.string.UrlIsNotInitializedMessage));
            return;
        }

        String websocketUrl = serverUrl.replace("http://", "ws://").replace("https://", "wss://");
        if (!websocketUrl.startsWith("ws://") && !websocketUrl.startsWith("wss://")) {
            websocketUrl = "ws://" + websocketUrl;
        }

        Log.d(TAG, "Final WebSocket URL: " + websocketUrl);
        showToast(getString(R.string.ConnectionMessage));

        videoClient.connect(websocketUrl);
    }

    @Override
    public void onFrameReceived(byte[] frameData) {
        runOnUiThread(() -> {
            try {
                long currentTime = System.currentTimeMillis();
                long timeDiff = currentTime - lastFrameTime;
                lastFrameTime = currentTime;

                Log.d(TAG, "Displaying frame, size: " + frameData.length + " bytes, time since last: " + timeDiff + "ms");

                Bitmap bitmap = BitmapFactory.decodeByteArray(frameData, 0, frameData.length);
                if (bitmap != null) {
                    imageView.setImageBitmap(bitmap);
                    Log.d(TAG, "Frame displayed successfully");
                } else {
                    Log.e(TAG, "Failed to decode bitmap");
                    showToast(getString(R.string.FrameDecodeErrorMessage));
                }
            } catch (Exception e) {
                Log.e(TAG, "Error displaying frame: " + e.getMessage());
                showToast(getString(R.string.FrameShowErrorMessage));
            }
        });
    }

    @Override
    public void onConnectionStatusChanged(boolean connected) {
        runOnUiThread(() -> {
            isConnected = connected;
            updateButtonStates();

            if (connected) {
                showToast(getString(R.string.ConnectedToServerMessage));
                Log.i(TAG, "Successfully connected to server");

                new Handler().postDelayed(() -> {
                    if (isConnected) {
                        videoClient.sendCommand("start_stream");
                        showToast(getString(R.string.StreamAutoRequestMessage));
                    }
                }, 1000);
            } else {
                showToast(getString(R.string.DisconnectServerMessage));
                Log.i(TAG, "Disconnected from server");

                new Handler().postDelayed(() -> {
                    if (!isConnected) {
                        Log.i(TAG, "Attempting reconnect...");
                        connectToServer();
                    }
                }, 3000);
            }
        });
    }

    @Override
    public void onError(String error) {
        runOnUiThread(() -> {
            Log.e(TAG, "Client error: " + error);
            showToast(getString(R.string.GeneralErrorPrefixMessage) + error);
        });
    }

    private void updateButtonStates() {
        btnStart.setEnabled(isConnected);
        btnStop.setEnabled(isConnected);

        btnStart.setAlpha(isConnected ? 1.0f : 0.5f);
        btnStop.setAlpha(isConnected ? 1.0f : 0.5f);
    }

    private void showToast(String message) {
        Toast.makeText(this, message, Toast.LENGTH_SHORT).show();
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        if (videoClient != null) {
            videoClient.disconnect();
        }
    }

    @Override
    public boolean onCreateOptionsMenu(Menu menu) {
        getMenuInflater().inflate(R.menu.main_menu, menu);
        return true;
    }

    @Override
    public boolean onOptionsItemSelected(MenuItem item) {
        if (item.getItemId() == R.id.action_settings) {
            startActivity(new Intent(this, SettingsActivity.class));
            return true;
        }
        return super.onOptionsItemSelected(item);
    }
}