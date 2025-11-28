package com.example.cv_cam_android;

import android.content.SharedPreferences;
import android.os.Bundle;
import android.widget.Button;
import android.widget.EditText;
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
        String savedUrl = prefs.getString("stream_url", "");
        editUrl.setText(savedUrl);

        btnSave.setOnClickListener(v -> {
            String url = editUrl.getText().toString().trim();

            if (url.isEmpty()) {
                editUrl.setError("Введите URL сервера");
                return;
            }

            SharedPreferences.Editor editor = prefs.edit();
            editor.putString("stream_url", url);
            editor.apply();

            finish();
        });
    }
}
