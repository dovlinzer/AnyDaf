import SwiftUI

struct ContentView: View {
    @StateObject private var feedManager = FeedManager()
    @StateObject private var audioPlayer = AudioPlayer()
    @StateObject private var studyManager = StudySessionManager()
    @StateObject private var readAloudManager = ReadAloudManager()
    @StateObject private var bookmarkManager = BookmarkManager()
    @StateObject private var shiurClient = ShiurClient.shared

    private let pageManager = TalmudPageManager.shared

    @AppStorage("lastTractateIndex") private var selectedTractateIndex = 0
    @AppStorage("lastDaf") private var selectedDaf: Double = 2.0
    @AppStorage("lastAmud") private var selectedSide: Int = 0
    @State private var imageDaf: Int = 2
    @State private var imageSide: Int = 0   // actual displayed amud; decoupled from picker
    @AppStorage("quizMode") private var quizMode: QuizMode = .multipleChoice
    @AppStorage("useWhiteBackground") private var useWhiteBackground: Bool = false
    @AppStorage("shiurShowSources") private var shiurShowSources: Bool = true
    @State private var showStudyMode = false
    @State private var showShiurText = false
    @State private var showSettings = false
    @State private var showBookmarkList = false
    @State private var showBookmarkEdit = false
    @State private var isFetchingDafYomi = false
    @State private var suppressTractateReset = false
    /// Prevents looping: only one automatic feed-refresh per play attempt.
    @State private var hasAutoRefreshedForAudio = false
    /// Podcasts-style tap feedback: press-down + expanding halo ring.
    /// rippleP is a 0→1 progress value where 1 = end state (transparent, invisible at rest).
    @State private var backSkipPressed  = false
    @State private var backRippleP: Double = 1   // rests at 1 (opacity 0, invisible)
    @State private var fwdSkipPressed   = false
    @State private var fwdRippleP: Double  = 1

    var tractate: Tractate { allTractates[selectedTractateIndex] }

    var currentAudioURL: URL? {
        feedManager.audioURL(tractate: tractate.name, daf: selectedDaf)
    }

    /// Integer range for the current tractate augmented with half-daf entries from the episode index.
    var dafPickerItems: [Double] {
        var items: [Double] = []
        for n in tractate.dafRange {
            items.append(Double(n))
            let half = Double(n) + 0.5
            if feedManager.episodeIndex[tractate.name]?[half] != nil {
                items.append(half)
            }
        }
        return items
    }

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {

                // ── Pickers: hidden during study mode (study view uses full space) ──
                if !showStudyMode {
                HStack(alignment: .center, spacing: 0) {

                    // Tractate picker
                    Picker("Tractate", selection: $selectedTractateIndex) {
                        ForEach(allTractates.indices, id: \.self) { i in
                            Text(allTractates[i].name).tag(i)
                        }
                    }
                    .pickerStyle(.wheel)
                    .frame(maxWidth: .infinity)
                    .frame(height: 100)
                    .clipped()

                    // Daf picker
                    Picker("Daf", selection: $selectedDaf) {
                        ForEach(dafPickerItems, id: \.self) { daf in
                            Text(FeedManager.dafLabel(daf)).tag(daf)
                        }
                    }
                    .pickerStyle(.wheel)
                    .frame(width: 70)
                    .frame(height: 100)
                    .clipped()
                }
                .colorScheme(.light)   // force dark labels on the white picker background
                .background(
                    RoundedRectangle(cornerRadius: 14)
                        .fill(Color.white)
                        .shadow(color: .black.opacity(0.35), radius: 6, x: 0, y: 3)
                )
                .padding(.horizontal, 20)
                .padding(.top, 8)
                .onChange(of: selectedTractateIndex) { _, _ in
                    if suppressTractateReset {
                        suppressTractateReset = false
                    } else {
                        selectedDaf = Double(tractate.startDaf)
                        imageDaf = tractate.startDaf
                        imageSide = tractate.startAmud
                        selectedSide = tractate.startAmud
                        // Don't stop audio — if playing/paused, let it continue; if already stopped, no-op.
                    }
                }
                .onChange(of: selectedDaf) { _, newVal in
                    imageDaf = Int(newVal)
                    let isHalf = newVal.truncatingRemainder(dividingBy: 1) != 0
                    let side: Int
                    if isHalf {
                        side = 1  // half-daf entries are always b-side
                    } else {
                        side = (newVal == Double(tractate.startDaf)) ? tractate.startAmud : 0
                    }
                    imageSide = side
                    selectedSide = side
                    // Don't stop audio — if playing/paused, keep it going; play button will load the new daf when stopped.
                }
                } // end if !showStudyMode (pickers)

                // ── Daf page / Study mode: fills available space ─────────────
                ZStack {
                    if !showStudyMode {
                        VStack(spacing: 0) {
                            // Daf / Shiur toggle — visible only when lecture text is available
                            if shiurClient.shiurRewrite != nil {
                                Picker("View", selection: $showShiurText) {
                                    Text("Daf").tag(false)
                                    Text("Shiur").tag(true)
                                }
                                .pickerStyle(.segmented)
                                .padding(.horizontal, 20)
                                .padding(.vertical, 6)
                                .colorScheme(useWhiteBackground ? .light : .dark)
                            }

                            let shiurDisplayText = shiurShowSources
                                ? (shiurClient.shiurFinal ?? shiurClient.shiurRewrite)
                                : shiurClient.shiurRewrite
                            if showShiurText, let text = shiurDisplayText {
                                ShiurTextView(
                                    rewriteText: text,
                                    currentSegmentIndex: shiurClient.currentSegmentIndex,
                                    foreground: appFg,
                                    useWhiteBackground: useWhiteBackground
                                )
                                .frame(maxWidth: .infinity, maxHeight: .infinity)
                            } else if pageManager.hasPages(for: tractate.name) {
                                DafPageView(
                                    tractate: tractate,
                                    daf: $imageDaf,
                                    displaySide: $imageSide,
                                    selectedSide: $selectedSide,
                                    pageManager: pageManager
                                )
                                .frame(maxWidth: .infinity, maxHeight: .infinity)
                                .onLongPressGesture {
                                    showBookmarkEdit = true
                                }
                            } else {
                                Spacer()
                            }
                        }
                    } else {
                        StudyModeView(
                            manager: studyManager,
                            readAloudManager: readAloudManager,
                            onDismiss: {
//                                readAloudManager.stopReadAloud() // Read-Aloud (commented out)
                                withAnimation(.easeInOut(duration: 0.5)) {
                                    showStudyMode = false
                                }
                                studyManager.endSession()
                            }
                        )
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                        // Counter-rotate so text isn't mirrored after flip
                        .rotation3DEffect(
                            .degrees(180),
                            axis: (x: 0, y: 1, z: 0)
                        )
                    }
                }
                .rotation3DEffect(
                    .degrees(showStudyMode ? 180 : 0),
                    axis: (x: 0, y: 1, z: 0)
                )
                .animation(.easeInOut(duration: 0.6), value: showStudyMode)

                // ── Bottom controls: hidden during study mode ─────────────────
                if !showStudyMode {
                VStack(spacing: 0) {
                    Spacer().frame(height: 6)

                    if audioPlayer.isBuffering || feedManager.isLoading {
                        // ── Loading ──────────────────────────────────────────────
                        HStack(spacing: 0) {
                            Spacer()
                            ProgressView().frame(width: 38, height: 38)
                            Spacer()
                            studyButtonView
                            Spacer(minLength: 8)
                        }
                        .padding(.vertical, 8)

                    } else if audioPlayer.isStopped {
                        // ── Stopped: Listen (left) + Study (right) ───────────────
                        HStack(spacing: 0) {
                            Spacer()
                            VStack(spacing: 4) {
                                Button {
                                    if let url = currentAudioURL {
                                        hasAutoRefreshedForAudio = false
                                        audioPlayer.play(
                                            url: url,
                                            title: "\(tractate.name) \(FeedManager.dafLabel(selectedDaf))")
                                    }
                                } label: {
                                    Image(systemName: "play.circle.fill")
                                        .font(.system(size: 38))
                                        .foregroundStyle(canPlay
                                                         ? appFg
                                                         : appFg.opacity(0.3))
                                }
                                .disabled(!canPlay)
                                Text("Listen")
                                    .font(.caption2)
                                    .foregroundStyle(appFg.opacity(0.7))
                            }
                            Spacer()
                            studyButtonView
                            Spacer()
                        }
                        .padding(.vertical, 8)

                    } else {
                        // ── Playing / paused ─────────────────────────────────────
                        VStack(spacing: 2) {
                            // Full-width progress bar
                            Slider(
                                value: Binding(
                                    get: { audioPlayer.duration > 0
                                        ? audioPlayer.currentTime / audioPlayer.duration : 0 },
                                    set: { audioPlayer.seek(to: $0) }
                                )
                            )
                            .padding(.horizontal)
                            .onChange(of: audioPlayer.currentTime) { _, newTime in
                                shiurClient.updateCurrentSegment(currentTime: newTime)
                            }

                            // Chapter markers strip — only shown when segments are available
                            if !shiurClient.segments.isEmpty && audioPlayer.duration > 0 {
                                chapterStrip
                            }

                            // Playback controls row: elapsed | [⏪ ▶/⏸ ⏩ ⏹] | speed | total
                            HStack(alignment: .center, spacing: 0) {
                                Text(formatTime(audioPlayer.currentTime))
                                    .font(.caption.monospacedDigit())
                                    .foregroundStyle(appFg.opacity(0.7))
                                    .padding(.leading)

                                Spacer()

                                HStack(spacing: 8) {
                                    ZStack {
                                        Circle()
                                            .stroke(appFg.opacity(0.45 * (1.0 - backRippleP)),
                                                    lineWidth: 1.5)
                                            .scaleEffect(1.0 + CGFloat(backRippleP) * 0.5)
                                            .frame(width: 38, height: 38)
                                        Image(systemName: "gobackward.30")
                                            .font(.system(size: 24))
                                            .foregroundStyle(canSkip
                                                             ? appFg.opacity(0.8)
                                                             : appFg.opacity(0.3))
                                            .scaleEffect(backSkipPressed ? 0.82 : 1.0)
                                            .animation(.spring(response: 0.15, dampingFraction: 0.5),
                                                       value: backSkipPressed)
                                    }
                                    .onTapGesture {
                                        guard canSkip else { return }
                                        audioPlayer.skip(by: -30)
                                        backSkipPressed = true
                                        DispatchQueue.main.asyncAfter(deadline: .now() + 0.14) {
                                            backSkipPressed = false
                                        }
                                        backRippleP = 0
                                        DispatchQueue.main.async {
                                            withAnimation(.easeOut(duration: 0.4)) { backRippleP = 1 }
                                        }
                                    }

                                    Button {
                                        audioPlayer.togglePlayPause()
                                    } label: {
                                        Image(systemName: audioPlayer.isPlaying
                                              ? "pause.circle.fill"
                                              : "play.circle.fill")
                                            .font(.system(size: 38))
                                            .foregroundStyle(appFg)
                                    }

                                    ZStack {
                                        Circle()
                                            .stroke(appFg.opacity(0.45 * (1.0 - fwdRippleP)),
                                                    lineWidth: 1.5)
                                            .scaleEffect(1.0 + CGFloat(fwdRippleP) * 0.5)
                                            .frame(width: 38, height: 38)
                                        Image(systemName: "goforward.30")
                                            .font(.system(size: 24))
                                            .foregroundStyle(canSkip
                                                             ? appFg.opacity(0.8)
                                                             : appFg.opacity(0.3))
                                            .scaleEffect(fwdSkipPressed ? 0.82 : 1.0)
                                            .animation(.spring(response: 0.15, dampingFraction: 0.5),
                                                       value: fwdSkipPressed)
                                    }
                                    .onTapGesture {
                                        guard canSkip else { return }
                                        audioPlayer.skip(by: 30)
                                        fwdSkipPressed = true
                                        DispatchQueue.main.asyncAfter(deadline: .now() + 0.14) {
                                            fwdSkipPressed = false
                                        }
                                        fwdRippleP = 0
                                        DispatchQueue.main.async {
                                            withAnimation(.easeOut(duration: 0.4)) { fwdRippleP = 1 }
                                        }
                                    }

                                    Button {
                                        audioPlayer.stop()
                                    } label: {
                                        Image(systemName: "stop.circle.fill")
                                            .font(.system(size: 38))
                                            .foregroundStyle(appFg)
                                    }
                                    .padding(.leading, 14)
                                }

                                Spacer()

                                Menu {
                                    ForEach([Float(0.5), 0.75, 1.0, 1.25, 1.5, 1.75, 2.0], id: \.self) { rate in
                                        Button {
                                            audioPlayer.setRate(rate)
                                        } label: {
                                            if rate == audioPlayer.playbackRate {
                                                Label(formatSpeed(rate), systemImage: "checkmark")
                                            } else {
                                                Text(formatSpeed(rate))
                                            }
                                        }
                                    }
                                } label: {
                                    Text(formatSpeed(audioPlayer.playbackRate))
                                        .font(.caption.monospacedDigit().bold())
                                        .foregroundStyle(appFg)
                                        .padding(.horizontal, 7)
                                        .padding(.vertical, 3)
                                        .background(Capsule().fill(appFg.opacity(0.25)))
                                }
                                .padding(.trailing, 10)

                                Text(formatTime(audioPlayer.duration))
                                    .font(.caption.monospacedDigit())
                                    .foregroundStyle(appFg.opacity(0.7))
                                    .padding(.trailing)
                            }

                            // Study button — centered, with extra space below the controls row
                            studyButtonView
                                .frame(maxWidth: .infinity, alignment: .center)
                                .padding(.top, 20)
                        }
                        .padding(.bottom, 2)
                    }

                    // "No episode" notice
                    if !feedManager.isLoading && feedManager.hasIndex && currentAudioURL == nil {
                        Text("No audio episode found for this daf")
                            .font(.caption2)
                            .foregroundStyle(appFg.opacity(0.7))
                    }

                    Spacer().frame(height: 6)
                }
                } // end if !showStudyMode (bottom controls)
            }
            .background(appBg)
            .navigationTitle("AnyDaf")
            .navigationBarTitleDisplayMode(.inline)
            .toolbarBackground(appBg, for: .navigationBar)
            .toolbarBackground(.visible, for: .navigationBar)
            .toolbarColorScheme(useWhiteBackground ? .light : .dark, for: .navigationBar)
            .toolbar {
                if !showStudyMode {
                    ToolbarItem(placement: .topBarLeading) {
                        Image(systemName: "gearshape")
                            .foregroundStyle(appFg)
                            .onTapGesture { showSettings = true }
                    }
                    ToolbarItem(placement: .topBarLeading) {
                        Button {
                            Task { await syncToTodaysDaf() }
                        } label: {
                            if isFetchingDafYomi {
                                ProgressView()
                            } else {
                                VStack(spacing: 1) {
                                    Image(systemName: "calendar")
                                        .font(.system(size: 18))
                                    Text("דף יומי")
                                        .font(.system(size: 7.5, weight: .semibold))
                                }
                            }
                        }
                        .disabled(isFetchingDafYomi)
                    }
                    ToolbarItem(placement: .topBarTrailing) {
                        Button {
                            showBookmarkList = true
                        } label: {
                            Image(systemName: "list.star")
                                .font(.system(size: 16))
                        }
                    }
                    ToolbarItem(placement: .topBarTrailing) {
                        Button {
                            showBookmarkEdit = true
                        } label: {
                            Image(systemName: bookmarkManager.isBookmarked(
                                tractateIndex: selectedTractateIndex,
                                daf: imageDaf, amud: imageSide)
                                ? "bookmark.fill" : "bookmark")
                                .font(.system(size: 16))
                        }
                    }
                }
            }
        }
        .sheet(isPresented: $showSettings) {
            SettingsView(
                bookmarkManager: bookmarkManager,
                isReloading: feedManager.isLoading,
                onReload: { Task { await feedManager.forceRefresh() } }
            )
        }
        .sheet(isPresented: $showBookmarkEdit) {
            BookmarkEditSheet(
                bookmarkManager: bookmarkManager,
                tractateIndex: selectedTractateIndex,
                daf: imageDaf,
                amud: imageSide,
                studySectionIndex: showStudyMode ? studyManager.session?.currentSectionIndex : nil,
                existingBookmark: bookmarkManager.existing(
                    tractateIndex: selectedTractateIndex, daf: imageDaf, amud: imageSide)
            )
        }
        .sheet(isPresented: $showBookmarkList) {
            BookmarkListView(
                bookmarkManager: bookmarkManager,
                onNavigate: { bookmark in
                    if selectedTractateIndex != bookmark.tractateIndex {
                        suppressTractateReset = true
                        selectedTractateIndex = bookmark.tractateIndex
                    }
                    selectedDaf = Double(bookmark.daf)
                    imageDaf = bookmark.daf
                    imageSide = bookmark.amud
                    selectedSide = bookmark.amud
                }
            )
        }
        .onAppear {
            imageDaf = Int(selectedDaf)
            // Read-Aloud (commented out — re-enable when ready)
//            readAloudManager.studyManager = studyManager
//            readAloudManager.audioPlayer  = audioPlayer
            Task { await shiurClient.loadSegments(tractate: tractate.name, daf: selectedDaf) }
        }
        .onChange(of: selectedDaf) { _, newDaf in
            // Don't swap segments while audio is playing a different daf.
            guard audioPlayer.isStopped else { return }
            Task { await shiurClient.loadSegments(tractate: tractate.name, daf: newDaf) }
        }
        .onChange(of: selectedTractateIndex) { _, _ in
            guard audioPlayer.isStopped else { return }
            shiurClient.reset()
            Task { await shiurClient.loadSegments(tractate: tractate.name, daf: selectedDaf) }
        }
        .onChange(of: audioPlayer.isStopped) { _, isStopped in
            // When audio stops, sync segments to whatever daf the picker is now showing.
            guard isStopped else { return }
            shiurClient.reset()
            Task { await shiurClient.loadSegments(tractate: tractate.name, daf: selectedDaf) }
        }
        .onChange(of: shiurClient.shiurRewrite) { _, newValue in
            // If the new daf has no shiur text, fall back to Daf view automatically.
            if newValue == nil { showShiurText = false }
        }
        .onChange(of: audioPlayer.resolutionFailed) { _, failed in
            // When SoundCloud resolution fails, silently refresh the episode index and retry once.
            // A fresh fetch often converts soundcloud-track:// stubs into direct RSS MP3 URLs.
            guard failed, !hasAutoRefreshedForAudio else { return }
            hasAutoRefreshedForAudio = true
            Task {
                await feedManager.forceRefresh()
                // Re-look up the URL — it may now be a direct MP3 from the RSS feed
                if let url = feedManager.audioURL(tractate: tractate.name, daf: selectedDaf) {
                    audioPlayer.play(url: url, title: "\(tractate.name) \(FeedManager.dafLabel(selectedDaf))")
                }
            }
        }
        .task {
            await feedManager.refreshIfNeeded()
        }
    }

    private func syncToTodaysDaf() async {
        isFetchingDafYomi = true
        defer { isFetchingDafYomi = false }

        do {
            let dafYomi = try await DafYomiService.fetchToday()
            if selectedTractateIndex != dafYomi.tractateIndex {
                suppressTractateReset = true
                selectedTractateIndex = dafYomi.tractateIndex
            }
            selectedDaf = Double(dafYomi.daf)
            imageDaf = dafYomi.daf
            imageSide = 0
            selectedSide = 0
            audioPlayer.stop()
        } catch {
            print("Failed to fetch today's daf: \(error.localizedDescription)")
        }
    }

    // MARK: - Chapter Strip

    /// Horizontal scrolling row of chapter marker pills shown below the progress bar.
    /// Tapping a pill seeks to that chapter. The active chapter is highlighted.
    @ViewBuilder private var chapterStrip: some View {
        ScrollViewReader { proxy in
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 6) {
                    ForEach(Array(shiurClient.segments.enumerated()), id: \.element.id) { idx, seg in
                        let isActive = idx == shiurClient.currentSegmentIndex
                        Button {
                            audioPlayer.seek(to: seg.seconds / audioPlayer.duration)
                        } label: {
                            Text(seg.displayTitle)
                                .font(.caption2)
                                .lineLimit(1)
                                .padding(.horizontal, 8)
                                .padding(.vertical, 4)
                                .background(
                                    Capsule()
                                        .fill(isActive
                                              ? appFg.opacity(0.85)
                                              : appFg.opacity(0.15))
                                )
                                .foregroundStyle(isActive
                                                 ? (useWhiteBackground ? .white : SplashView.background)
                                                 : appFg.opacity(0.8))
                        }
                        .id(idx)
                    }
                }
                .padding(.horizontal)
            }
            .onChange(of: shiurClient.currentSegmentIndex) { _, newIdx in
                withAnimation { proxy.scrollTo(newIdx, anchor: .center) }
            }
        }
        .frame(height: 30)
    }

    @ViewBuilder private var studyButtonView: some View {
        VStack(spacing: 4) {
            Button {
                withAnimation(.easeInOut(duration: 0.6)) { showStudyMode = true }
                Task {
                    await studyManager.startSession(
                        tractate: tractate.name, daf: Int(selectedDaf), mode: .facts, quizMode: quizMode)
                }
            } label: {
                Image(systemName: "book.circle.fill")
                    .font(.system(size: 38))
                    .foregroundStyle(appFg)
            }
            .disabled(showStudyMode)
            Text("Study")
                .font(.caption2)
                .foregroundStyle(appFg.opacity(0.7))
        }
    }

    private var appBg: Color { useWhiteBackground ? .white : SplashView.background }
    private var appFg: Color { useWhiteBackground ? Color(.label) : .white }

    private var canPlay: Bool {
        currentAudioURL != nil && !feedManager.isLoading && !audioPlayer.isBuffering
    }

    private var canSkip: Bool {
        audioPlayer.duration > 0 && !audioPlayer.isBuffering
    }

    private func formatSpeed(_ rate: Float) -> String {
        switch rate {
        case 0.5:  return "0.5×"
        case 0.75: return "0.75×"
        case 1.0:  return "1×"
        case 1.25: return "1.25×"
        case 1.5:  return "1.5×"
        case 1.75: return "1.75×"
        case 2.0:  return "2×"
        default:   return String(format: "%.2g×", rate)
        }
    }

    private func formatTime(_ seconds: Double) -> String {
        guard seconds.isFinite, seconds >= 0 else { return "0:00" }
        let mins = Int(seconds) / 60
        let secs = Int(seconds) % 60
        return "\(mins):\(String(format: "%02d", secs))"
    }
}

// MARK: - Daf Page Viewer

struct DafPageView: View {
    let tractate: Tractate
    @Binding var daf: Int
    @Binding var displaySide: Int   // actual displayed amud — lives in ContentView so daf+side updates are coalesced
    @Binding var selectedSide: Int  // picker selection only — does not change on swipe/arrow
    let pageManager: TalmudPageManager

    private func advanceAmud() {
        if displaySide == 0 {
            displaySide = 1
        } else if daf < tractate.endDaf {
            daf += 1
            displaySide = 0
        }
    }

    private func retreatAmud() {
        if displaySide == 1 {
            displaySide = 0
        } else if daf > tractate.startDaf {
            daf -= 1
            displaySide = 1
        }
    }

    var body: some View {
        let sideA = displaySide == 0
        if let url = pageManager.imageURL(tractate: tractate.name, daf: daf, sideA: sideA) {
            ZStack(alignment: .top) {
                // Transparent spacer + image in a VStack so the image starts below the picker overlay.
                // The picker (below) overlays the Color.clear gap — no image is hidden underneath it.
                VStack(spacing: 0) {
                    Color.clear.frame(height: 60)   // 8pt top-pad + 6+32+6 pt picker area + ~8pt breathing room
                    ZoomableAsyncImage(
                        url: url,
                        onSwipeLeft: advanceAmud,
                        onSwipeRight: retreatAmud
                    )
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .clipShape(RoundedRectangle(cornerRadius: 26))
                }

                // Amud picker — overlaid at top of ZStack so it is always in front of the image
                // for hit testing (same pattern as the edge-nav arrows, which always work).
                // Previously above the ZStack in a VStack, but scaleEffect on the image caused
                // the zoomed image's gesture area to intercept taps in the picker's region.
                Picker("Amud", selection: $selectedSide) {
                    Text("Amud א (a)").tag(0)
                    Text("Amud ב (b)").tag(1)
                }
                .pickerStyle(.segmented)
                .padding(.horizontal, 28)
                .padding(.vertical, 6)
                .background(
                    RoundedRectangle(cornerRadius: 12)
                        .fill(Color.white)
                        .shadow(color: .black.opacity(0.3), radius: 5, x: 0, y: 2)
                )
                .padding(.horizontal, 20)
                .padding(.top, 8)
                // Sync display when user taps picker or ContentView resets it (daf/tractate change)
                .onChange(of: selectedSide) { _, newVal in
                    displaySide = newVal
                }

                // ── Edge navigation arrows at ~40% from top ─────────────
                // 2 spacers above : 3 spacers below  →  40% / 60%
                VStack(spacing: 0) {
                    Spacer()
                    Spacer()
                    HStack {
                        Button(action: retreatAmud) {
                            Image(systemName: "chevron.left.circle.fill")
                                .font(.system(size: 30))
                                .foregroundStyle(.white.opacity(0.55))
                                .shadow(color: .black.opacity(0.45), radius: 3, x: 0, y: 1)
                        }
                        .padding(.leading, 8)

                        Spacer()

                        Button(action: advanceAmud) {
                            Image(systemName: "chevron.right.circle.fill")
                                .font(.system(size: 30))
                                .foregroundStyle(.white.opacity(0.55))
                                .shadow(color: .black.opacity(0.45), radius: 3, x: 0, y: 1)
                        }
                        .padding(.trailing, 8)
                    }
                    Spacer()
                    Spacer()
                    Spacer()
                }
            }
            .mask(
                RoundedRectangle(cornerRadius: 28)
                    .padding(.horizontal, 1)
                    .padding(.bottom, 2)
            )
            .shadow(color: .black.opacity(0.35), radius: 8, x: 0, y: 4)
            .padding(.horizontal, 12)
            .padding(.bottom, 8)
        } else {
            VStack(spacing: 0) {
                // Show the picker even when there's no image so the user can return to amud a
                Picker("Amud", selection: $selectedSide) {
                    Text("Amud א (a)").tag(0)
                    Text("Amud ב (b)").tag(1)
                }
                .pickerStyle(.segmented)
                .padding(.horizontal, 28)
                .padding(.vertical, 6)
                .background(
                    RoundedRectangle(cornerRadius: 12)
                        .fill(Color.white)
                        .shadow(color: .black.opacity(0.3), radius: 5, x: 0, y: 2)
                )
                .padding(.horizontal, 20)
                .padding(.top, 8)
                .onChange(of: selectedSide) { _, newVal in
                    displaySide = newVal
                }

                Spacer()
                Text("No image for daf \(daf)\(sideA ? "a" : "b")")
                    .font(.caption)
                    .foregroundStyle(.white.opacity(0.7))
                Spacer()
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
    }
}

#Preview {
    ContentView()
}
