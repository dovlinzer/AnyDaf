import AVFoundation
import Combine
import MediaPlayer
import UIKit

@MainActor
class AudioPlayer: ObservableObject {
    @Published var isPlaying = false
    @Published var isBuffering = false
    @Published var isStopped = true   // true when no audio is loaded or after explicit stop/natural end
    @Published var currentTime: Double = 0
    @Published var duration: Double = 0
    @Published var playbackRate: Float = 1.0
    /// Set to true when SoundCloud stream resolution fails (e.g. expired client ID).
    /// ContentView observes this to trigger an automatic feed refresh + retry.
    @Published var resolutionFailed = false

    private var player: AVPlayer?
    private var timeObserver: Any?
    private var cancellables = Set<AnyCancellable>()
    private var nowPlayingTitle = ""
    private var routeChangeObserver: NSObjectProtocol?
    private var currentPlayTask: Task<Void, Never>?

    init() {
        setupRemoteCommands()
        setupAudioRouteChangeHandling()
    }

    // MARK: - Public API

    func play(url: URL, title: String = "") {
        stop()
        resolutionFailed = false
        isStopped = false
        nowPlayingTitle = title
        isBuffering = true

        if url.scheme == "soundcloud-track", let trackID = url.host {
            // Resolve signed stream URL at play time (CDN URLs expire, so we don't cache them)
            currentPlayTask = Task { @MainActor [weak self] in
                guard let self else { return }
                guard let resolved = await AudioPlayer.resolveStreamURL(trackID: trackID) else {
                    // Signal failure so ContentView can auto-refresh the feed and retry
                    self.resolutionFailed = true
                    self.stop()
                    return
                }
                // Bail if a subsequent stop() or play() already cancelled us
                guard !Task.isCancelled else { return }
                self.startPlayback(url: resolved)
            }
        } else {
            startPlayback(url: url)
        }
    }

    func togglePlayPause() {
        guard let player else { return }
        if isPlaying {
            player.pause()
            isPlaying = false
            UIApplication.shared.isIdleTimerDisabled = false
        } else {
            player.rate = playbackRate   // resume at the stored rate
            isPlaying = true
            UIApplication.shared.isIdleTimerDisabled = true
        }
        updateNowPlaying()
    }

    /// Change playback speed. Takes effect immediately if already playing.
    func setRate(_ rate: Float) {
        playbackRate = rate
        guard isPlaying, let player else {
            updateNowPlaying()
            return
        }
        // Pause then immediately resume at the new rate.  This forces Bluetooth
        // devices to renegotiate the stream at the correct speed; without it some
        // BT hardware silently ignores a mid-stream rate change.
        player.pause()
        player.rate = rate
        updateNowPlaying()
    }

    /// Seek forward (positive) or backward (negative) by the given number of seconds.
    func skip(by seconds: Double) {
        guard let player, duration > 0 else { return }
        let newTime = max(0, min(currentTime + seconds, duration))
        player.seek(to: CMTime(seconds: newTime, preferredTimescale: 600))
        currentTime = newTime
        updateNowPlayingTime()
    }

    func seek(to fraction: Double) {
        guard let player, duration > 0 else { return }
        let seconds = max(0, min(fraction * duration, duration))
        player.seek(to: CMTime(seconds: seconds, preferredTimescale: 600))
        updateNowPlayingTime()
    }

    func stop() {
        currentPlayTask?.cancel()
        currentPlayTask = nil
        NotificationCenter.default.removeObserver(self, name: .AVPlayerItemDidPlayToEndTime, object: nil)
        cancellables.removeAll()
        if let timeObserver {
            player?.removeTimeObserver(timeObserver)
            self.timeObserver = nil
        }
        player?.pause()
        player = nil
        isPlaying = false
        isBuffering = false
        isStopped = true
        currentTime = 0
        duration = 0
        UIApplication.shared.isIdleTimerDisabled = false
        MPNowPlayingInfoCenter.default().nowPlayingInfo = nil
    }

    // MARK: - Private

    // Resolves a SoundCloud track ID to a playable CDN URL via two API calls.
    // Static so it can run off the main actor.
    private static func resolveStreamURL(trackID: String) async -> URL? {
        let clientID = FeedManager.soundcloudClientID
        print("[AudioPlayer] Resolving trackID: \(trackID)")

        // Step 1: fetch track metadata to get the transcoding URL and auth token
        guard let trackAPIURL = URL(string: "https://api-v2.soundcloud.com/tracks/\(trackID)?client_id=\(clientID)")
        else { print("[AudioPlayer] ✗ Bad track URL"); return nil }

        let trackData: Data
        do {
            let (data, response) = try await URLSession.shared.data(from: trackAPIURL)
            let status = (response as? HTTPURLResponse)?.statusCode ?? 0
            print("[AudioPlayer] Step 1 HTTP \(status) for \(trackID)")
            if status != 200 {
                print("[AudioPlayer] ✗ Step 1 body: \(String(data: data, encoding: .utf8) ?? "<unreadable>")")
                return nil
            }
            trackData = data
        } catch {
            print("[AudioPlayer] ✗ Step 1 network error: \(error)")
            return nil
        }

        guard let json = try? JSONSerialization.jsonObject(with: trackData) as? [String: Any]
        else { print("[AudioPlayer] ✗ Step 1 JSON parse failed"); return nil }

        guard let auth = json["track_authorization"] as? String,
              let media = json["media"] as? [String: Any],
              let transcodings = media["transcodings"] as? [[String: Any]]
        else { print("[AudioPlayer] ✗ Step 1 missing fields (auth/media/transcodings)"); return nil }

        // Prefer progressive (direct MP3) over HLS
        let progressive = transcodings.first {
            ($0["format"] as? [String: Any])?["protocol"] as? String == "progressive"
        }
        guard let tcURLStr = progressive?["url"] as? String,
              let tcURL = URL(string: "\(tcURLStr)?client_id=\(clientID)&track_authorization=\(auth)")
        else { print("[AudioPlayer] ✗ No progressive transcoding found"); return nil }

        // Step 2: resolve transcoding URL → actual CDN URL
        let streamData: Data
        do {
            let (data, response) = try await URLSession.shared.data(from: tcURL)
            let status = (response as? HTTPURLResponse)?.statusCode ?? 0
            print("[AudioPlayer] Step 2 HTTP \(status)")
            if status != 200 {
                print("[AudioPlayer] ✗ Step 2 body: \(String(data: data, encoding: .utf8) ?? "<unreadable>")")
                return nil
            }
            streamData = data
        } catch {
            print("[AudioPlayer] ✗ Step 2 network error: \(error)")
            return nil
        }

        guard let streamJSON = try? JSONSerialization.jsonObject(with: streamData) as? [String: Any],
              let streamURLStr = streamJSON["url"] as? String,
              let streamURL = URL(string: streamURLStr)
        else { print("[AudioPlayer] ✗ Step 2 JSON parse / URL construction failed"); return nil }

        print("[AudioPlayer] ✓ Resolved to \(streamURL)")
        return streamURL
    }

    private func startPlayback(url: URL) {
        let item = AVPlayerItem(url: url)
        // .timeDomain preserves pitch like .spectral but is lower-overhead and
        // more compatible with Bluetooth audio stacks.
        item.audioTimePitchAlgorithm = .timeDomain
        let p = AVPlayer(playerItem: item)
        player = p

        // Detect when the system silently resets our rate (common when a
        // Bluetooth device connects or renegotiates mid-playback) and re-apply.
        p.publisher(for: \.rate)
            .receive(on: RunLoop.main)
            .sink { [weak self] newRate in
                guard let self,
                      self.isPlaying,
                      newRate != 0,
                      newRate != self.playbackRate else { return }
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.2) { [weak self] in
                    guard let self, self.isPlaying else { return }
                    self.player?.rate = self.playbackRate
                }
            }
            .store(in: &cancellables)

        // Watch for ready-to-play
        item.publisher(for: \.status)
            .receive(on: RunLoop.main)
            .sink { [weak self] status in
                guard let self else { return }
                if status == .readyToPlay {
                    self.isBuffering = false
                    let secs = item.duration.seconds
                    self.duration = secs.isFinite ? secs : 0
                    p.rate = self.playbackRate   // start at stored rate (non-zero = plays)
                    self.isPlaying = true
                    UIApplication.shared.isIdleTimerDisabled = true
                    self.updateNowPlaying()
                }
            }
            .store(in: &cancellables)

        // Update duration once it's known (it may be 0 initially)
        item.publisher(for: \.duration)
            .receive(on: RunLoop.main)
            .sink { [weak self] time in
                let secs = time.seconds
                if secs.isFinite && secs > 0 {
                    self?.duration = secs
                    self?.updateNowPlaying()
                }
            }
            .store(in: &cancellables)

        // Periodic time updates
        let interval = CMTime(seconds: 0.5, preferredTimescale: 600)
        timeObserver = p.addPeriodicTimeObserver(forInterval: interval, queue: .main) { [weak self] time in
            let seconds = time.seconds
            Task { @MainActor [weak self] in
                guard let self else { return }
                self.currentTime = seconds
                self.updateNowPlayingTime()
            }
        }

        // End of playback
        NotificationCenter.default.addObserver(
            self,
            selector: #selector(didFinishPlaying),
            name: .AVPlayerItemDidPlayToEndTime,
            object: item
        )
    }

    @objc private func didFinishPlaying() {
        isPlaying = false
        isStopped = true
        currentTime = 0
        UIApplication.shared.isIdleTimerDisabled = false
        MPNowPlayingInfoCenter.default().nowPlayingInfo = nil
    }

    // MARK: - Bluetooth / Route-Change Robustness

    private func setupAudioRouteChangeHandling() {
        routeChangeObserver = NotificationCenter.default.addObserver(
            forName: AVAudioSession.routeChangeNotification,
            object: nil,
            queue: .main
        ) { [weak self] notification in
            Task { @MainActor [weak self] in
                self?.handleAudioRouteChange(notification)
            }
        }
    }

    private func handleAudioRouteChange(_ notification: Notification) {
        guard
            let reasonValue = notification.userInfo?[AVAudioSessionRouteChangeReasonKey] as? UInt,
            let reason = AVAudioSession.RouteChangeReason(rawValue: reasonValue),
            isPlaying
        else { return }

        switch reason {
        case .newDeviceAvailable,   // e.g. BT headphones connected
             .oldDeviceUnavailable, // e.g. BT headphones disconnected → fallback route
             .categoryChange,
             .override:
            // Give the audio system ~0.5 s to finish route negotiation,
            // then re-stamp our desired rate.
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) { [weak self] in
                guard let self, self.isPlaying else { return }
                self.player?.rate = self.playbackRate
            }
        default:
            break
        }
    }

    // MARK: - Now Playing & Remote Commands

    private func setupRemoteCommands() {
        let cc = MPRemoteCommandCenter.shared()

        cc.playCommand.addTarget { [weak self] _ in
            Task { @MainActor [weak self] in self?.togglePlayPause() }
            return .success
        }
        cc.pauseCommand.addTarget { [weak self] _ in
            Task { @MainActor [weak self] in self?.togglePlayPause() }
            return .success
        }
        cc.togglePlayPauseCommand.addTarget { [weak self] _ in
            Task { @MainActor [weak self] in self?.togglePlayPause() }
            return .success
        }

        cc.skipForwardCommand.preferredIntervals = [15]
        cc.skipForwardCommand.addTarget { [weak self] event in
            if let e = event as? MPSkipIntervalCommandEvent {
                Task { @MainActor [weak self] in self?.skip(by: e.interval) }
            }
            return .success
        }

        cc.skipBackwardCommand.preferredIntervals = [15]
        cc.skipBackwardCommand.addTarget { [weak self] event in
            if let e = event as? MPSkipIntervalCommandEvent {
                Task { @MainActor [weak self] in self?.skip(by: -e.interval) }
            }
            return .success
        }
    }

    private func updateNowPlaying() {
        guard duration > 0 else { return }
        MPNowPlayingInfoCenter.default().nowPlayingInfo = [
            MPMediaItemPropertyTitle:                    nowPlayingTitle.isEmpty ? "AnyDaf" : nowPlayingTitle,
            MPNowPlayingInfoPropertyElapsedPlaybackTime: currentTime,
            MPMediaItemPropertyPlaybackDuration:         duration,
            MPNowPlayingInfoPropertyPlaybackRate:        isPlaying ? Double(playbackRate) : 0.0,
            MPNowPlayingInfoPropertyDefaultPlaybackRate: Double(playbackRate)
        ]
    }

    private func updateNowPlayingTime() {
        guard var info = MPNowPlayingInfoCenter.default().nowPlayingInfo else { return }
        info[MPNowPlayingInfoPropertyElapsedPlaybackTime] = currentTime
        info[MPNowPlayingInfoPropertyPlaybackRate]        = isPlaying ? Double(playbackRate) : 0.0
        MPNowPlayingInfoCenter.default().nowPlayingInfo   = info
    }
}
