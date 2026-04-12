package com.anydaf.viewmodel

import android.content.Context
import android.content.Intent
import android.media.AudioAttributes
import android.media.AudioFocusRequest
import android.media.AudioManager
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.media3.common.MediaItem
import androidx.media3.common.Player
import androidx.media3.exoplayer.ExoPlayer
import com.anydaf.AnyDafApp
import com.anydaf.data.api.FeedManager
import com.anydaf.service.AudioPlaybackService
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONObject

class AudioViewModel : ViewModel() {

    private val _isPlaying = MutableStateFlow(false)
    val isPlaying: StateFlow<Boolean> = _isPlaying.asStateFlow()

    private val _isBuffering = MutableStateFlow(false)
    val isBuffering: StateFlow<Boolean> = _isBuffering.asStateFlow()

    private val _isStopped = MutableStateFlow(true)
    val isStopped: StateFlow<Boolean> = _isStopped.asStateFlow()

    private val _currentTime = MutableStateFlow(0f)
    val currentTime: StateFlow<Float> = _currentTime.asStateFlow()

    private val _duration = MutableStateFlow(0f)
    val duration: StateFlow<Float> = _duration.asStateFlow()

    private val _playbackRate = MutableStateFlow(1f)
    val playbackRate: StateFlow<Float> = _playbackRate.asStateFlow()

    private val _resolutionFailed = MutableStateFlow(false)
    val resolutionFailed: StateFlow<Boolean> = _resolutionFailed.asStateFlow()

    private val _currentTitle = MutableStateFlow("")
    val currentTitle: StateFlow<String> = _currentTitle.asStateFlow()

    private val context get() = AnyDafApp.context
    private val audioManager get() = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
    private val httpClient = OkHttpClient.Builder().build()

    private var player: ExoPlayer? = null
    private var audioFocusRequest: AudioFocusRequest? = null
    private var positionJob: kotlinx.coroutines.Job? = null
    private var resolveJob: kotlinx.coroutines.Job? = null

    private val focusListener = AudioManager.OnAudioFocusChangeListener { focusChange ->
        when (focusChange) {
            AudioManager.AUDIOFOCUS_LOSS,
            AudioManager.AUDIOFOCUS_LOSS_TRANSIENT -> pause()
            AudioManager.AUDIOFOCUS_GAIN -> if (!_isStopped.value) resume()
        }
    }

    fun play(urlString: String, title: String = "") {
        stop()
        _resolutionFailed.value = false
        _isStopped.value = false
        _isBuffering.value = true
        _currentTitle.value = title

        if (urlString.startsWith("soundcloud-track://")) {
            val trackId = urlString.removePrefix("soundcloud-track://")
            resolveJob = viewModelScope.launch {
                val resolved = resolveStreamUrl(trackId)
                if (!isActive) return@launch          // cancelled by a subsequent stop()/play()
                if (resolved != null) startPlayback(resolved)
                else { _resolutionFailed.value = true; _isBuffering.value = false; _isStopped.value = true }
            }
        } else {
            startPlayback(urlString)
        }
    }

    fun togglePlayPause() {
        if (_isPlaying.value) pause() else resume()
    }

    fun setRate(rate: Float) {
        _playbackRate.value = rate
        player?.setPlaybackSpeed(rate)
    }

    fun skip(bySeconds: Float) {
        val player = player ?: return
        val newPos = (player.currentPosition + (bySeconds * 1000).toLong())
            .coerceIn(0L, player.duration.takeIf { it > 0 } ?: 0L)
        player.seekTo(newPos)
    }

    fun seekTo(fraction: Float) {
        val player = player ?: return
        val dur = player.duration.takeIf { it > 0 } ?: return
        player.seekTo((fraction * dur).toLong())
    }

    fun seekToSeconds(secs: Float) {
        val player = player ?: return
        val dur = player.duration.takeIf { it > 0 } ?: return
        player.seekTo((secs * 1000L).toLong().coerceIn(0L, dur))
    }

    fun stop() {
        resolveJob?.cancel()
        resolveJob = null
        positionJob?.cancel()
        abandonAudioFocus()
        player?.release()
        player = null
        _isPlaying.value = false
        _isBuffering.value = false
        _isStopped.value = true
        _currentTime.value = 0f
        _duration.value = 0f
        startService(false)
    }

    private fun pause() {
        player?.pause()
        _isPlaying.value = false
    }

    private fun resume() {
        if (requestAudioFocus()) {
            player?.play()
            _isPlaying.value = true
        }
    }

    private fun startPlayback(url: String) {
        if (!requestAudioFocus()) {
            _isBuffering.value = false
            _isStopped.value = true
            return
        }

        val exo = ExoPlayer.Builder(context).build()
        player = exo

        exo.addListener(object : Player.Listener {
            override fun onPlaybackStateChanged(state: Int) {
                when (state) {
                    Player.STATE_READY -> {
                        _isBuffering.value = false
                        _duration.value = exo.duration.coerceAtLeast(0L) / 1000f
                        exo.setPlaybackSpeed(_playbackRate.value)
                        exo.play()
                        _isPlaying.value = true
                        startPositionUpdater()
                        startService(true)
                    }
                    Player.STATE_BUFFERING -> _isBuffering.value = true
                    Player.STATE_ENDED -> {
                        _isPlaying.value = false
                        _isStopped.value = true
                        _currentTime.value = 0f
                        positionJob?.cancel()
                        abandonAudioFocus()
                        startService(false)
                    }
                    else -> {}
                }
            }
        })

        exo.setMediaItem(MediaItem.fromUri(url))
        exo.prepare()
    }

    private fun startPositionUpdater() {
        positionJob?.cancel()
        positionJob = viewModelScope.launch {
            while (true) {
                delay(500)
                val pos = player?.currentPosition ?: 0L
                _currentTime.value = pos / 1000f
                val dur = player?.duration ?: 0L
                if (dur > 0) _duration.value = dur / 1000f
            }
        }
    }

    private fun requestAudioFocus(): Boolean {
        val req = AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN)
            .setAudioAttributes(
                AudioAttributes.Builder()
                    .setUsage(AudioAttributes.USAGE_MEDIA)
                    .setContentType(AudioAttributes.CONTENT_TYPE_MUSIC)
                    .build()
            )
            .setOnAudioFocusChangeListener(focusListener)
            .build()
        audioFocusRequest = req
        return audioManager.requestAudioFocus(req) == AudioManager.AUDIOFOCUS_REQUEST_GRANTED
    }

    private fun abandonAudioFocus() {
        audioFocusRequest?.let { audioManager.abandonAudioFocusRequest(it) }
        audioFocusRequest = null
    }

    private fun startService(playing: Boolean) {
        val intent = Intent(context, AudioPlaybackService::class.java)
        if (playing) {
            intent.putExtra(AudioPlaybackService.EXTRA_TITLE, _currentTitle.value)
            context.startForegroundService(intent)
        } else {
            context.stopService(intent)
        }
    }

    // SoundCloud two-step URL resolution (mirrors iOS)
    private suspend fun resolveStreamUrl(trackId: String): String? = withContext(Dispatchers.IO) {
        val clientId = FeedManager.SOUNDCLOUD_CLIENT_ID
        val trackUrl = "https://api-v2.soundcloud.com/tracks/$trackId?client_id=$clientId"

        val trackBody = try {
            httpClient.newCall(Request.Builder().url(trackUrl).build()).execute().body?.string()
        } catch (e: Exception) { null } ?: return@withContext null

        val trackJson = try { JSONObject(trackBody) } catch (e: Exception) { return@withContext null }
        val auth = trackJson.optString("track_authorization").ifEmpty { return@withContext null }
        val media = trackJson.optJSONObject("media") ?: return@withContext null
        val transcodings = media.optJSONArray("transcodings") ?: return@withContext null

        // Prefer progressive (direct MP3) over HLS
        var progressiveUrl: String? = null
        for (i in 0 until transcodings.length()) {
            val tc = transcodings.getJSONObject(i)
            val protocol = tc.optJSONObject("format")?.optString("protocol") ?: continue
            if (protocol == "progressive") {
                progressiveUrl = tc.optString("url").ifEmpty { null }
                break
            }
        }
        val tcUrl = progressiveUrl ?: return@withContext null
        val resolveUrl = "$tcUrl?client_id=$clientId&track_authorization=$auth"

        val streamBody = try {
            httpClient.newCall(Request.Builder().url(resolveUrl).build()).execute().body?.string()
        } catch (e: Exception) { null } ?: return@withContext null

        val streamJson = try { JSONObject(streamBody) } catch (e: Exception) { return@withContext null }
        streamJson.optString("url").ifEmpty { null }
    }

    override fun onCleared() {
        stop()
        super.onCleared()
    }
}
