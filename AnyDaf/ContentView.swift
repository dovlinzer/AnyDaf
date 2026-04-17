import SwiftUI

/// Which content the iPad right column displays when study mode is not active.
private enum IPadRightPanel: String {
    case shiur = "shiur"
    case study = "study"
}

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
    @State private var backSkipPressed  = false
    @State private var backRippleP: Double = 1
    @State private var fwdSkipPressed   = false
    @State private var fwdRippleP: Double  = 1

    @Environment(\.horizontalSizeClass) private var horizontalSizeClass

    /// iPad split divider position — fraction of total width given to the left (daf) column.
    @State private var splitFraction: CGFloat = 0.5
    @GestureState private var splitDragOffset: CGFloat = 0
    /// iPad right-panel mode — persisted so the user's preference is remembered.
    @AppStorage("iPadRightPanel") private var iPadRightPanel: IPadRightPanel = .shiur

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
            Group {
                if horizontalSizeClass == .regular {
                    iPadLayout
                } else {
                    iPhoneLayout
                }
            }
            .background(appBg)
            .navigationTitle("AnyDaf")
            .navigationBarTitleDisplayMode(.inline)
            .toolbarBackground(appBg, for: .navigationBar)
            .toolbarBackground(.visible, for: .navigationBar)
            .toolbarColorScheme(useWhiteBackground ? .light : .dark, for: .navigationBar)
            .toolbar {
                // On iPad, always show toolbar — study mode is a side panel, not full-screen.
                if !showStudyMode || horizontalSizeClass == .regular {
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
            Task { await shiurClient.loadSegments(tractate: tractate.name, daf: selectedDaf) }
            // iPad: if last session was in study mode, auto-start the study panel on launch
            if horizontalSizeClass == .regular && iPadRightPanel == .study {
                Task {
                    await studyManager.startSession(
                        tractate: tractate.name, daf: Int(selectedDaf), mode: .facts, quizMode: quizMode)
                }
            }
        }
        .onChange(of: selectedDaf) { _, newDaf in
            guard audioPlayer.isStopped else { return }
            Task { await shiurClient.loadSegments(tractate: tractate.name, daf: newDaf) }
            if horizontalSizeClass == .regular && iPadRightPanel == .study {
                Task {
                    await studyManager.startSession(
                        tractate: tractate.name, daf: Int(newDaf), mode: .facts, quizMode: quizMode)
                }
            }
        }
        .onChange(of: selectedTractateIndex) { _, _ in
            guard audioPlayer.isStopped else { return }
            shiurClient.reset()
            Task { await shiurClient.loadSegments(tractate: tractate.name, daf: selectedDaf) }
            if horizontalSizeClass == .regular && iPadRightPanel == .study {
                Task {
                    await studyManager.startSession(
                        tractate: tractate.name, daf: Int(selectedDaf), mode: .facts, quizMode: quizMode)
                }
            }
        }
        .onChange(of: audioPlayer.isStopped) { _, isStopped in
            guard isStopped else { return }
            shiurClient.reset()
            Task { await shiurClient.loadSegments(tractate: tractate.name, daf: selectedDaf) }
        }
        .onChange(of: shiurClient.shiurRewrite) { _, newValue in
            if newValue == nil { showShiurText = false }
            // Panel selection persists across dafs; iPadRightContent shows placeholder when nil.
        }
        .onChange(of: audioPlayer.resolutionFailed) { _, failed in
            guard failed, !hasAutoRefreshedForAudio else { return }
            hasAutoRefreshedForAudio = true
            Task {
                await feedManager.forceRefresh()
                if let url = feedManager.audioURL(tractate: tractate.name, daf: selectedDaf) {
                    audioPlayer.play(url: url, title: "\(tractate.name) \(FeedManager.dafLabel(selectedDaf))")
                }
            }
        }
        .task {
            await feedManager.refreshIfNeeded()
        }
    }

    // MARK: - iPad Two-Column Layout

    private var iPadLayout: some View {
        GeometryReader { geo in
            let totalWidth = geo.size.width
            let dividerWidth: CGFloat = 24
            let contentWidth = totalWidth - dividerWidth
            let rawFraction = splitFraction + splitDragOffset / contentWidth
            let clampedFraction = max(0.3, min(0.7, rawFraction))
            let leftWidth = contentWidth * clampedFraction
            let isPortrait = geo.size.height > geo.size.width
            let portraitTopPad: CGFloat = isPortrait ? 20 : 0

            // Compute image height so audio sits right below the image rather than
            // being pinned to the bottom of a fixed section (visible gap in portrait).
            // Daf pages are ~A4 ratio (height ≈ width × 1.41). Cap at available space
            // so the image never overflows in landscape.
            let dafImageAspect: CGFloat = 1.41       // height / width
            let pickerH: CGFloat = 80                // wheel picker row (76pt + 4pt top pad)
            let amudH: CGFloat = 40                  // segmented amud picker
            let audioH: CGFloat = 120                // fixed audio section
            let overhead = portraitTopPad + pickerH + 10 + amudH + audioH
            let naturalImageH = leftWidth * dafImageAspect
            let imageHeight = min(naturalImageH, max(10, geo.size.height - overhead))

            HStack(spacing: 0) {
                // Left column: daf selector → amud picker → image → audio (→ spacer)
                VStack(spacing: 0) {
                    Spacer().frame(height: portraitTopPad)
                    pickerRow
                    Spacer().frame(height: 10)

                    // Amud picker + daf image as one visual unit
                    iPadAmudPicker
                    dafOnlyView
                        .frame(width: leftWidth, height: imageHeight)

                    // Audio controls sit directly below the image
                    bottomControls
                        .frame(height: audioH)

                    Spacer(minLength: 0)  // absorbs remaining space at the bottom
                }
                .frame(width: leftWidth)

                // Drag handle
                ZStack {
                    Rectangle()
                        .fill(appFg.opacity(0.18))
                        .frame(width: 1)
                    VStack(spacing: 5) {
                        ForEach(0..<3, id: \.self) { _ in
                            Circle()
                                .fill(appFg.opacity(0.45))
                                .frame(width: 5, height: 5)
                        }
                    }
                    .padding(.vertical, 10)
                    .padding(.horizontal, 8)
                    .background(
                        Capsule()
                            .fill(appBg.opacity(0.9))
                            .shadow(color: .black.opacity(0.25), radius: 3, x: 0, y: 1)
                    )
                }
                .frame(width: dividerWidth)
                .contentShape(Rectangle())
                .gesture(
                    DragGesture(minimumDistance: 0)
                        .updating($splitDragOffset) { value, state, _ in
                            state = value.translation.width
                        }
                        .onEnded { value in
                            let newFraction = splitFraction + value.translation.width / contentWidth
                            splitFraction = max(0.3, min(0.7, newFraction))
                        }
                )

                // Right column: Shiur/Study picker always anchored at top + content below
                VStack(spacing: 0) {
                    Spacer().frame(height: portraitTopPad)
                    Picker("Right Panel", selection: $iPadRightPanel) {
                        Text("Shiur").tag(IPadRightPanel.shiur)
                        Text("Study").tag(IPadRightPanel.study)
                    }
                    .pickerStyle(.segmented)
                    .padding(.horizontal, 16)
                    .padding(.vertical, 8)
                    .colorScheme(useWhiteBackground ? .light : .dark)
                    .onChange(of: iPadRightPanel) { _, newPanel in
                        if newPanel == .study {
                            Task {
                                await studyManager.startSession(
                                    tractate: tractate.name, daf: Int(selectedDaf),
                                    mode: .facts, quizMode: quizMode)
                            }
                        }
                    }
                    ZStack {
                        if iPadRightPanel == .study {
                            studyModeContent
                                .frame(maxWidth: .infinity, maxHeight: .infinity)
                                .transition(.asymmetric(
                                    insertion: .move(edge: .trailing).combined(with: .opacity),
                                    removal:   .move(edge: .trailing).combined(with: .opacity)
                                ))
                        } else {
                            iPadRightContent
                                .frame(maxWidth: .infinity, maxHeight: .infinity)
                                .transition(.asymmetric(
                                    insertion: .move(edge: .leading).combined(with: .opacity),
                                    removal:   .move(edge: .leading).combined(with: .opacity)
                                ))
                        }
                    }
                    .animation(.easeInOut(duration: 0.35), value: iPadRightPanel)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                }
                .frame(maxWidth: .infinity)
            }
        }
    }

    /// Amud a/b segmented picker for the iPad left column — sits between the daf selectors and the image.
    private var iPadAmudPicker: some View {
        Picker("Amud", selection: $selectedSide) {
            Text("Amud א (a)").tag(0)
            Text("Amud ב (b)").tag(1)
        }
        .pickerStyle(.segmented)
        .padding(.horizontal, 20)
        .padding(.vertical, 4)
        .frame(maxWidth: 400)
        .frame(maxWidth: .infinity)
        .colorScheme(useWhiteBackground ? .light : .dark)
        .onChange(of: selectedSide) { _, newVal in imageSide = newVal }
    }

    /// Daf page only — no shiur toggle (iPad left column; shiur lives in the right column).
    @ViewBuilder private var dafOnlyView: some View {
        if pageManager.hasPages(for: tractate.name) {
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

    /// Right column shiur panel — only rendered when iPadRightPanel == .shiur.
    @ViewBuilder private var iPadRightContent: some View {
        if let text = shiurDisplayText {
            VStack(spacing: 0) {
                // Shiur header — tractate + daf (no a/b, since shiur covers the full daf)
                Text("\(tractate.name) \(Int(selectedDaf))")
                    .font(.headline)
                    .foregroundStyle(appFg)
                    .padding(.horizontal)
                    .padding(.vertical, 10)
                ShiurTextView(
                    rewriteText: text,
                    currentSegmentIndex: shiurClient.currentSegmentIndex,
                    foreground: appFg,
                    useWhiteBackground: useWhiteBackground
                )
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        } else {
            VStack(spacing: 16) {
                Spacer()
                Image(systemName: "book.closed")
                    .font(.system(size: 44))
                    .foregroundStyle(appFg.opacity(0.15))
                Text("No written shiur available on this daf")
                    .font(.callout)
                    .foregroundStyle(appFg.opacity(0.3))
                    .multilineTextAlignment(.center)
                Spacer()
            }
            .frame(maxWidth: .infinity)
        }
    }

    // MARK: - iPhone Layout (existing full-screen flip behaviour)

    private var iPhoneLayout: some View {
        VStack(spacing: 0) {
            if !showStudyMode { pickerRow }

            ZStack {
                if !showStudyMode {
                    dafAndShiurView
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                } else {
                    studyModeContent
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
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

            if !showStudyMode { bottomControls }
        }
    }

    // MARK: - Picker Row

    @ViewBuilder private var pickerRow: some View {
        HStack(alignment: .center, spacing: 0) {

            Picker("Tractate", selection: $selectedTractateIndex) {
                ForEach(allTractates.indices, id: \.self) { i in
                    Text(allTractates[i].name)
                        .font(horizontalSizeClass == .regular ? .body : .subheadline)
                        .tag(i)
                }
            }
            .pickerStyle(.wheel)
            .frame(maxWidth: .infinity)
            .frame(height: 76)
            .clipped()

            Picker("Daf", selection: $selectedDaf) {
                ForEach(dafPickerItems, id: \.self) { daf in
                    Text(FeedManager.dafLabel(daf))
                        .font(horizontalSizeClass == .regular ? .body : .subheadline)
                        .tag(daf)
                }
            }
            .pickerStyle(.wheel)
            .frame(width: 70)
            .frame(height: 76)
            .clipped()
        }
        .colorScheme(.light)
        .background(
            RoundedRectangle(cornerRadius: 14)
                .fill(Color.white)
                .shadow(color: .black.opacity(0.35), radius: 6, x: 0, y: 3)
        )
        .padding(.horizontal, 20)
        .padding(.top, 4)
        // On iPad, cap picker card width and center it
        .frame(maxWidth: horizontalSizeClass == .regular ? 520 : .infinity)
        .frame(maxWidth: .infinity)
        .onChange(of: selectedTractateIndex) { _, _ in
            if suppressTractateReset {
                suppressTractateReset = false
            } else {
                selectedDaf = Double(tractate.startDaf)
                imageDaf = tractate.startDaf
                imageSide = tractate.startAmud
                selectedSide = tractate.startAmud
            }
        }
        .onChange(of: selectedDaf) { _, newVal in
            imageDaf = Int(newVal)
            let isHalf = newVal.truncatingRemainder(dividingBy: 1) != 0
            let side: Int
            if isHalf {
                side = 1
            } else {
                side = (newVal == Double(tractate.startDaf)) ? tractate.startAmud : 0
            }
            imageSide = side
            selectedSide = side
        }
    }

    private var shiurDisplayText: String? {
        shiurShowSources
            ? (shiurClient.shiurFinal ?? shiurClient.shiurRewrite)
            : shiurClient.shiurRewrite
    }

    // MARK: - Daf / Shiur Content (iPhone — on iPad the toggle lives in the right column)

    @ViewBuilder private var dafAndShiurView: some View {
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
                .frame(maxWidth: .infinity)
            }

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
    }

    // MARK: - Study Mode Content

    @ViewBuilder private var studyModeContent: some View {
        StudyModeView(
            manager: studyManager,
            readAloudManager: readAloudManager,
            onDismiss: {
                if horizontalSizeClass == .regular {
                    // iPad: Back switches to shiur panel if available; otherwise stays in study
                    if shiurClient.shiurRewrite != nil {
                        withAnimation(.easeInOut(duration: 0.35)) { iPadRightPanel = .shiur }
                    }
                } else {
                    withAnimation(.easeInOut(duration: 0.5)) { showStudyMode = false }
                    studyManager.endSession()
                }
            }
        )
    }

    // MARK: - Bottom Controls (audio player)

    @ViewBuilder private var bottomControls: some View {
        VStack(spacing: 0) {
            if horizontalSizeClass != .regular {
                Spacer().frame(height: 6)
            }

            if audioPlayer.isBuffering || feedManager.isLoading {
                // ── Loading ──────────────────────────────────────────────
                HStack(spacing: 0) {
                    Spacer()
                    ProgressView().frame(width: 38, height: 38)
                    Spacer()
                    if horizontalSizeClass != .regular {
                        studyButtonView
                        Spacer(minLength: 8)
                    }
                }
                .padding(.vertical, 8)

            } else if audioPlayer.isStopped {
                // ── Stopped: Listen + (on iPhone) Study button ───────────
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
                    if horizontalSizeClass != .regular {
                        studyButtonView
                        Spacer()
                    }
                }
                .padding(.vertical, 8)

            } else if !audioPlayer.isStopped {
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
        // On iPad the Shiur/Study picker in the left column replaces this button.
        if horizontalSizeClass != .regular {
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

    @Environment(\.horizontalSizeClass) private var horizontalSizeClass

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
            VStack(spacing: 0) {
                // Amud picker: above the image on iPhone; on iPad it lives outside DafPageView.
                if horizontalSizeClass != .regular {
                    amudPicker
                        .padding(.top, 8)
                        .padding(.bottom, 6)
                }

                ZStack {
                    ZoomableAsyncImage(
                        url: url,
                        onSwipeLeft: advanceAmud,
                        onSwipeRight: retreatAmud
                    )
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .clipShape(RoundedRectangle(cornerRadius: 26))
                    .shadow(color: .black.opacity(0.35), radius: 8, x: 0, y: 4)
                    .padding(.horizontal, 12)
                    .padding(.bottom, 8)

                    // ── Edge navigation arrows ─────────────────────────────
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
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
        } else {
            VStack(spacing: 0) {
                amudPicker
                    .padding(.top, 8)
                Spacer()
                Text("No image for daf \(daf)\(sideA ? "a" : "b")")
                    .font(.caption)
                    .foregroundStyle(.white.opacity(0.7))
                Spacer()
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
    }

    /// Amud (a/b) segmented picker — constrained width on iPad and centered.
    private var amudPicker: some View {
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
        // On iPad, cap picker width and center it
        .frame(maxWidth: horizontalSizeClass == .regular ? 400 : .infinity)
        .frame(maxWidth: .infinity)
        .onChange(of: selectedSide) { _, newVal in
            displaySide = newVal
        }
    }
}

#Preview {
    ContentView()
}
