package com.example.cv_cam_android;

import android.content.SharedPreferences;
import android.os.Bundle;
import android.widget.EditText;
import android.widget.Button;
import androidx.appcompat.app.AppCompatActivity;

public class SettingsActivity extends AppCompatActivity {

    private EditText editUrl;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_settings);

        editUrl = findViewById(R.id.edit_url);
        Button btnSave = findViewById(R.id.btn_save);

        SharedPreferences prefs = getSharedPreferences("settings", MODE_PRIVATE);
        editUrl.setText(prefs.getString("stream_url", ""));

        btnSave.setOnClickListener(v -> {
            String url = editUrl.getText().toString();
            prefs.edit().putString("stream_url", url).apply();
            finish(); // закрыть настройки
        });
    }
}
