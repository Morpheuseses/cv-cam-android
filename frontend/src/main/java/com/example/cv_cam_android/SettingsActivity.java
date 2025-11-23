package com.example.cv_cam_android;

import android.content.SharedPreferences;
import android.os.Bundle;
import android.widget.Button;
import android.widget.EditText;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;

public class SettingsActivity extends AppCompatActivity {

    private EditText editIp;
    private EditText editPort;
    private Button btnSave;

    private static final String PREFS_NAME = "app_settings";
    private static final String KEY_IP = "ip";
    private static final String KEY_PORT = "port";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_settings);

        editIp = findViewById(R.id.edit_ip);
        editPort = findViewById(R.id.edit_port);
        btnSave = findViewById(R.id.btn_save);

        // Загружаем сохранённые значения
        SharedPreferences prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE);
        editIp.setText(prefs.getString(KEY_IP, ""));
        editPort.setText(prefs.getString(KEY_PORT, ""));

        btnSave.setOnClickListener(v -> {
            String ip = editIp.getText().toString().trim();
            String port = editPort.getText().toString().trim();

            if (ip.isEmpty() || port.isEmpty()) {
                Toast.makeText(this, "IP и порт не могут быть пустыми", Toast.LENGTH_SHORT).show();
                return;
            }

            // Сохраняем значения
            SharedPreferences.Editor editor = prefs.edit();
            editor.putString(KEY_IP, ip);
            editor.putString(KEY_PORT, port);
            editor.apply();

            Toast.makeText(this, "Сохранено", Toast.LENGTH_SHORT).show();
        });
    }
}
