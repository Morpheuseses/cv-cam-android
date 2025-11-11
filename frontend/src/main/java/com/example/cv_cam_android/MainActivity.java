package com.example.cv_cam_android;

import android.os.Bundle;
import android.util.Log;
import androidx.appcompat.app.AlertDialog;
import androidx.appcompat.app.AppCompatActivity;
import androidx.navigation.NavController;
import androidx.navigation.Navigation;
import androidx.navigation.ui.AppBarConfiguration;
import androidx.navigation.ui.NavigationUI;
import androidx.media3.common.MediaItem;
import androidx.media3.common.Player;
import androidx.media3.common.PlaybackException;
import androidx.media3.exoplayer.ExoPlayer;
import com.example.cv_cam_android.databinding.ActivityMainBinding;
import com.google.android.material.snackbar.Snackbar;
import java.util.Arrays;
import java.util.List;

public class MainActivity extends AppCompatActivity {

    private ActivityMainBinding binding;
    private AppBarConfiguration appBarConfiguration;

    private ExoPlayer player;
    private int currentVideoIndex = 0;
    private long playbackPosition = 0;

    private final List<String> videoUrls = Arrays.asList(
            "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4",
            "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ElephantsDream.mp4",
            "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/Sintel.mp4"
    );

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        binding = ActivityMainBinding.inflate(getLayoutInflater());
        setContentView(binding.getRoot());
        setSupportActionBar(binding.toolbar);

        // Навигация
        NavController navController = Navigation.findNavController(this, R.id.nav_host_fragment_content_main);
        appBarConfiguration = new AppBarConfiguration.Builder(navController.getGraph()).build();
        NavigationUI.setupActionBarWithNavController(this, navController, appBarConfiguration);

        // FAB
        binding.fab.setOnClickListener(view ->
                Snackbar.make(view, "Wanna some?", Snackbar.LENGTH_LONG)
                        .setAnchorView(R.id.fab)
                        .setAction("Action", null)
                        .show()
        );
    }

    // ---- ExoPlayer ----

    private void initializePlayer() {
        if (player == null) {
            Log.d("PLAYER", "Initializing player");
            player = new ExoPlayer.Builder(this).build();
            binding.playerView.setPlayer(player);

            MediaItem mediaItem = MediaItem.fromUri(videoUrls.get(currentVideoIndex));
            player.setMediaItem(mediaItem);
            player.prepare();
            player.seekTo(playbackPosition);
            player.play();

            player.addListener(new Player.Listener() {
                @Override
                public void onPlaybackStateChanged(int state) {
                    if (state == Player.STATE_ENDED) {
                        showCompletionDialog();
                    }
                }

                @Override
                public void onPlayerError(PlaybackException error) {
                    Log.e("PLAYER_ERROR", "Error: " + error.getMessage(), error);
                }
            });
        }
    }

    private void releasePlayer() {
        if (player != null) {
            playbackPosition = player.getCurrentPosition();
            player.release();
            player = null;
        }
    }

    private void showCompletionDialog() {
        new AlertDialog.Builder(this)
                .setTitle("Playback Finished!")
                .setMessage("Want to replay or play next video?")
                .setIcon(android.R.drawable.ic_media_play)
                .setPositiveButton("Replay", (dialog, i) -> {
                    player.seekTo(0);
                    player.play();
                })
                .setNegativeButton("Next", (dialog, i) -> {
                    currentVideoIndex = (currentVideoIndex + 1) % videoUrls.size();
                    playbackPosition = 0;
                    initializePlayer();
                })
                .create()
                .show();
    }

    // ---- Жизненный цикл ----

    @Override
    protected void onStart() {
        super.onStart();
        initializePlayer();
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (player != null) player.play();
    }

    @Override
    protected void onPause() {
        super.onPause();
        if (player != null) player.pause();
    }

    @Override
    protected void onStop() {
        super.onStop();
        releasePlayer();
    }

    @Override
    public boolean onSupportNavigateUp() {
        NavController navController = Navigation.findNavController(this, R.id.nav_host_fragment_content_main);
        return NavigationUI.navigateUp(navController, appBarConfiguration)
                || super.onSupportNavigateUp();
    }
}
