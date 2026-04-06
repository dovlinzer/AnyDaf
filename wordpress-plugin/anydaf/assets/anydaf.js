/**
 * AnyDaf WordPress plugin — frontend player
 *
 * Reads configuration from window.AnyDafConfig (injected by PHP):
 *   { restBase, pagesUrl, tractates: [{name, start, end}, ...] }
 */
(function () {
  'use strict';

  // ── Config ───────────────────────────────────────────────────────────────────

  var cfg       = window.AnyDafConfig || {};
  var REST_BASE = cfg.restBase  || '';
  var PAGES_URL = cfg.pagesUrl  || '';
  var TRACTATES = cfg.tractates || [];

  // ── State ────────────────────────────────────────────────────────────────────

  var episodeIndex = {};   // { tractate: { "daf": url } }
  var pagesIndex   = {};   // { tractate: { "pageNum": driveFileId } }
  var isPlaying    = false;
  var currentSide  = 'a'; // 'a' or 'b'

  // ── DOM refs ─────────────────────────────────────────────────────────────────

  var audio         = document.getElementById('anydaf-audio');
  var tractateSel   = document.getElementById('anydaf-tractate-sel');
  var dafSel        = document.getElementById('anydaf-daf-sel');
  var playBtn       = document.getElementById('anydaf-play-btn');
  var playIcon      = document.getElementById('anydaf-play-icon');
  var playLabel     = document.getElementById('anydaf-play-label');
  var progressWrap  = document.getElementById('anydaf-progress-wrap');
  var progressFill  = document.getElementById('anydaf-progress-fill');
  var progressTrack = document.getElementById('anydaf-progress-track');
  var timeCur       = document.getElementById('anydaf-time-cur');
  var timeTot       = document.getElementById('anydaf-time-tot');
  var statusEl      = document.getElementById('anydaf-status');
  var amudA         = document.getElementById('anydaf-amud-a');
  var amudB         = document.getElementById('anydaf-amud-b');
  var pageImg       = document.getElementById('anydaf-page-img');
  var noImageEl     = document.getElementById('anydaf-no-image');

  // ── Picker initialisation ────────────────────────────────────────────────────

  function buildTractateOptions() {
    TRACTATES.forEach(function (t, i) {
      var opt = document.createElement('option');
      opt.value = i;
      opt.textContent = t.name;
      tractateSel.appendChild(opt);
    });
  }

  function buildDafOptions() {
    var t       = TRACTATES[+tractateSel.value];
    var current = +dafSel.value;
    dafSel.innerHTML = '';
    for (var d = t.start; d <= t.end; d++) {
      var opt = document.createElement('option');
      opt.value = d;
      opt.textContent = d;
      if (d === current) opt.selected = true;
      dafSel.appendChild(opt);
    }
    updatePlayButton();
    updatePageImage();
  }

  tractateSel.addEventListener('change', function () {
    stopAudio();
    buildDafOptions();
  });

  dafSel.addEventListener('change', function () {
    stopAudio();
    updatePlayButton();
    updatePageImage();
  });

  // ── Amud (side) toggle ───────────────────────────────────────────────────────

  amudA.addEventListener('click', function () {
    if (currentSide === 'a') return;
    currentSide = 'a';
    amudA.classList.add('anydaf-amud-active');
    amudB.classList.remove('anydaf-amud-active');
    updatePageImage();
  });

  amudB.addEventListener('click', function () {
    if (currentSide === 'b') return;
    currentSide = 'b';
    amudB.classList.add('anydaf-amud-active');
    amudA.classList.remove('anydaf-amud-active');
    updatePageImage();
  });

  // ── Page image ───────────────────────────────────────────────────────────────

  function updatePageImage() {
    var t        = TRACTATES[+tractateSel.value];
    var tractate = t.name;
    var daf      = +dafSel.value;
    var sideA    = currentSide === 'a';

    // Formula from TalmudPageManager.swift:
    //   page = (daf - 1) * 2 + (sideA ? 0 : 1)
    var pageNum = (daf - 1) * 2 + (sideA ? 0 : 1);

    var tractatePages = pagesIndex[tractate];
    if (!tractatePages || Object.keys(tractatePages).length === 0) {
      pageImg.style.display  = 'none';
      noImageEl.style.display = 'block';
      return;
    }

    var fileId = tractatePages[String(pageNum)];
    if (!fileId) {
      pageImg.style.display  = 'none';
      noImageEl.style.display = 'block';
      return;
    }

    noImageEl.style.display = 'none';
    pageImg.style.display   = 'block';
    pageImg.alt = tractate + ' ' + daf + (sideA ? 'a' : 'b');
    pageImg.src = 'https://drive.google.com/thumbnail?id=' + fileId + '&sz=w1200';
  }

  // ── Index loading ────────────────────────────────────────────────────────────

  function loadEpisodeIndex() {
    fetch(REST_BASE + 'index')
      .then(function (r) {
        if (!r.ok) throw new Error(r.statusText);
        return r.json();
      })
      .then(function (data) {
        episodeIndex = data;
        var total = Object.values(episodeIndex).reduce(function (s, v) {
          return s + Object.keys(v).length;
        }, 0);
        setStatus(total.toLocaleString() + ' episodes available');
        updatePlayButton();
      })
      .catch(function () {
        setStatus('Could not load episode index — check server configuration.');
      });
  }

  function loadPagesIndex() {
    if (!PAGES_URL) return;
    fetch(PAGES_URL)
      .then(function (r) { return r.json(); })
      .then(function (data) {
        pagesIndex = data;
        updatePageImage();
      })
      .catch(function () {
        // Pages index is optional; silently ignore errors.
      });
  }

  // ── Helpers ──────────────────────────────────────────────────────────────────

  function currentUrl() {
    var tractate = TRACTATES[+tractateSel.value].name;
    var daf      = String(dafSel.value);
    var dafs     = episodeIndex[tractate];
    return dafs ? (dafs[daf] || null) : null;
  }

  function updatePlayButton() {
    var url = currentUrl();
    if (!url) {
      playBtn.disabled = true;
      setPlayState(false);
      if (Object.keys(episodeIndex).length > 0) {
        var tractate = TRACTATES[+tractateSel.value].name;
        setStatus(
          episodeIndex[tractate]
            ? 'No recording found for this daf.'
            : 'No recordings available for this tractate.'
        );
      }
    } else {
      playBtn.disabled = false;
      var total = Object.values(episodeIndex).reduce(function (s, v) {
        return s + Object.keys(v).length;
      }, 0);
      setStatus(total.toLocaleString() + ' episodes available');
    }
  }

  // ── Playback ─────────────────────────────────────────────────────────────────

  playBtn.addEventListener('click', function () {
    if (isPlaying) {
      audio.pause();
      setPlayState(false);
      return;
    }

    // Resume if already loaded and paused mid-track.
    if (audio.src && audio.currentTime > 0 && audio.paused) {
      audio.play();
      setPlayState(true);
      return;
    }

    var url = currentUrl();
    if (!url) return;

    // soundcloud-track:// or soundcloud-track: — needs proxy resolution.
    if (url.indexOf('soundcloud-track:') === 0) {
      // Strip the scheme prefix (handles both "soundcloud-track://" and "soundcloud-track:").
      var trackId = url.replace(/^soundcloud-track:\/\//, '').replace(/^soundcloud-track:/, '');
      setStatus('Resolving audio\u2026');
      playBtn.disabled = true;

      fetch(REST_BASE + 'stream?track_id=' + encodeURIComponent(trackId))
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (!data.url) throw new Error('No URL returned');
          startPlayback(data.url);
        })
        .catch(function () {
          setStatus(
            'Could not load audio. <a href="https://soundcloud.com/yct-dafyomi" target="_blank">' +
            'Listen on SoundCloud \u2197</a>'
          );
          playBtn.disabled = false;
        });
      return;
    }

    startPlayback(url);
  });

  function startPlayback(url) {
    stopAudio();
    audio.src = url;
    audio.play()
      .then(function () {
        setPlayState(true);
        progressWrap.style.display = 'block';
        updatePlayButton();
      })
      .catch(function () {
        setStatus('Playback failed — the audio may have moved. Try refreshing.');
      });
  }

  function stopAudio() {
    audio.pause();
    audio.src = '';
    audio.currentTime = 0;
    setPlayState(false);
    progressWrap.style.display = 'none';
    progressFill.style.width   = '0%';
    timeCur.textContent = '0:00';
    timeTot.textContent = '0:00';
  }

  function setPlayState(playing) {
    isPlaying = playing;
    playIcon.innerHTML = playing
      ? '<path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/>'
      : '<path d="M8 5v14l11-7z"/>';
    playLabel.textContent = playing ? 'Pause' : 'Play';
  }

  // ── Audio events ─────────────────────────────────────────────────────────────

  audio.addEventListener('timeupdate', function () {
    if (!audio.duration) return;
    var pct = audio.currentTime / audio.duration * 100;
    progressFill.style.width = pct + '%';
    timeCur.textContent = fmt(audio.currentTime);
    timeTot.textContent = fmt(audio.duration);
  });

  audio.addEventListener('ended', function () { setPlayState(false); });

  audio.addEventListener('error', function () {
    setPlayState(false);
    setStatus('Playback error. The URL may have expired \u2014 try again later.');
  });

  progressTrack.addEventListener('click', function (e) {
    if (!audio.duration) return;
    var rect = progressTrack.getBoundingClientRect();
    audio.currentTime = ((e.clientX - rect.left) / rect.width) * audio.duration;
  });

  // ── Utilities ────────────────────────────────────────────────────────────────

  function fmt(s) {
    if (!isFinite(s)) return '0:00';
    var m   = Math.floor(s / 60);
    var sec = String(Math.floor(s % 60)).padStart(2, '0');
    return m + ':' + sec;
  }

  function setStatus(html) {
    statusEl.innerHTML = html;
  }

  // ── Boot ─────────────────────────────────────────────────────────────────────

  buildTractateOptions();
  buildDafOptions();
  loadEpisodeIndex();
  loadPagesIndex();

})();
