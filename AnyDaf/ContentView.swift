import SwiftUI

/// Which content the iPad right column displays when study mode is not active.
private enum IPadRightPanel: String {
    case shiur = "shiur"
    case study = "study"
}

/// Which content the iPhone main panel displays (replaces the old showShiurText Bool).
private enum MainContentMode: String {
    case daf, text, shiur
}

struct ContentView: View {
    @StateObject private var feedManager = FeedManager()
    @State private var audioPlayer = AudioPlayer()
    @StateObject private var studyManager = StudySessionManager()
    @StateObject private var readAloudManager = ReadAloudManager()
    @StateObject private var bookmarkManager = BookmarkManager()
    @StateObject private var shiurClient = ShiurClient.shared

    private let pageManager = TalmudPageManager.shared

    @AppStorage("lastTractateIndex") private var storedTractateIndex = 0
    @AppStorage("lastDaf") private var storedDaf: Double = 2.0
    @AppStorage("lastAmud") private var storedSide: Int = 0
    @State private var selectedTractateIndex: Int = UserDefaults.standard.integer(forKey: "lastTractateIndex")
    @State private var selectedDaf: Double = {
        let v = UserDefaults.standard.double(forKey: "lastDaf"); return v > 0 ? v : 2.0
    }()
    @State private var selectedSide: Int = UserDefaults.standard.integer(forKey: "lastAmud")
    @State private var imageDaf: Int = 2
    @State private var imageSide: Int = 0   // actual displayed amud; decoupled from picker
    @AppStorage("quizMode") private var quizMode: QuizMode = .multipleChoice
    @AppStorage("useWhiteBackground") private var useWhiteBackground: Bool = false
    @AppStorage("shiurShowSources") private var shiurShowSources: Bool = true
    @State private var showStudyMode = false
    @AppStorage("lastContentMode") private var mainContentMode: MainContentMode = .daf
    // Persisted text-mode position — only valid when tractate+daf match the current selection.
    @AppStorage("lastTextSectionIndex") private var lastTextSectionIndex: Int = 0
    @AppStorage("lastTextTractate") private var lastTextTractate: String = ""
    @AppStorage("lastTextDaf") private var lastTextDaf: Double = 0
    // Persisted shiur-mode position — only valid when tractate+daf match the current selection.
    @AppStorage("lastShiurSegmentIndex") private var lastShiurSegmentIndex: Int = 0
    @AppStorage("lastShiurTractate") private var lastShiurTractate: String = ""
    @AppStorage("lastShiurDaf") private var lastShiurDaf: Double = 0
    // One-shot flag: true once we've applied the initial shiur position restore on this launch.
    @State private var shiurInitialRestoreDone = false
    @State private var showSettings = false
    @State private var showBookmarkList = false
    @State private var showBookmarkEdit = false
    @State private var isFetchingDafYomi = false
    @State private var suppressTractateReset = false
    /// Guards against re-running picker-driven side effects when selectedDaf/selectedSide are
    /// set programmatically to mirror Study Mode's own daf/amud navigation (Prev Daf/Next Daf,
    /// or crossing the amud A/B boundary while paging through sections). Without these, the
    /// generic onChange(of: selectedDaf/selectedSide) handlers would redundantly restart the
    /// study session (clobbering the position Study Mode just navigated to) or nudge shiur/audio
    /// position, which Study Mode navigation should never touch.
    @State private var suppressDafSessionSync = false
    @State private var suppressSideSessionSync = false
    /// Prevents looping: only one automatic feed-refresh per play attempt.
    @State private var hasAutoRefreshedForAudio = false
    /// Tractate/daf frozen at the moment audio starts — stays fixed while picker freely moves.
    @State private var audioLockedTractateIndex: Int = 0
    @State private var audioLockedDaf: Double = 2.0
    /// Nil-reset binding used to force-scroll ShiurTextView to a specific segment on every pill tap.
    @State private var shiurForceScrollIndex: Int? = nil

    @Environment(\.horizontalSizeClass) private var horizontalSizeClass

    /// iPad split divider position — fraction of total width given to the left (daf) column.
    @AppStorage("iPadSplitFraction") private var splitFraction: Double = 0.5
    @GestureState private var splitDragDelta: CGFloat = 0
    /// "none" | "left" (left panel collapsed) | "right" (right panel collapsed)
    @AppStorage("iPadCollapsedSide") private var collapsedSide: String = "none"
    /// iPad right-panel mode — persisted so the user's preference is remembered.
    @AppStorage("iPadRightPanel") private var iPadRightPanel: IPadRightPanel = .shiur

    var tractate: Tractate { allTractates[selectedTractateIndex] }

    /// Study session's current daf + amud side, used to keep the picker readout
    /// (selectedDaf/selectedSide) in sync with Study Mode's own navigation.
    private struct StudyDafSide: Equatable { let daf: Int; let side: Int }
    private var studySessionDafSide: StudyDafSide? {
        guard let s = studyManager.session else { return nil }
        let onAmudB = s.amudBSectionIndex.map { s.currentSectionIndex >= $0 } ?? false
        return StudyDafSide(daf: s.daf, side: onAmudB ? 1 : 0)
    }

    /// The shiur segment to highlight when switching Text→Shiur. Prefers studyManager's
    /// activeSefariaIndex (the segment explicitly navigated to via a pill tap — see
    /// StudySessionManager.activeSefariaIndex), as long as it's still within [start, end): the
    /// user may have tapped a specific segment anchored mid-section, and switching to Shiur
    /// should land on exactly that one, not just whatever governs the section's start. Falls
    /// back to a point lookup at `start` — the last genuinely-`matched` segment whose own
    /// sefariaIndex is ≤ that position — for the "nothing specific was tapped" case (a section
    /// reached by scrolling or by Prev/Next, not a pill tap); several matched segments can share
    /// one coarse section (e.g. Hullin 3's first section spans four of them), and a fresh look at
    /// the top of that section should resolve to the first of them, not whichever anchors last.
    /// `matched == nil` (not yet computed) stays eligible in the fallback.
    /// Mirrors the reverse scan in SectionStudyView.activeShiurSegmentIndex (StudyModeView.swift).
    private func shiurSegmentIndex(forRangeStarting start: Int, endingBefore end: Int) -> Int? {
        if let activeIdx = studyManager.activeSefariaIndex, activeIdx >= start, activeIdx < end,
           let segIdx = shiurClient.segments.firstIndex(where: { $0.sefariaIndex == activeIdx && $0.matched == true }) {
            return segIdx
        }
        var best: Int? = nil
        for (idx, seg) in shiurClient.segments.enumerated() {
            guard seg.matched != false, let sIdx = seg.sefariaIndex, sIdx <= start else { continue }
            best = idx
        }
        return best
    }

    /// Exclusive upper bound of the Sefaria range the current text section covers — the next
    /// section's firstSegmentIndex, or unbounded if this is the last section.
    private func currentSectionRangeEnd() -> Int {
        guard let session = studyManager.session else { return Int.max }
        let nextIndex = session.currentSectionIndex + 1
        return nextIndex < session.sections.count ? session.sections[nextIndex].firstSegmentIndex : Int.max
    }

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
                    // Compact pickers in the toolbar centre — only when right panel is collapsed.
                    if horizontalSizeClass == .regular && collapsedSide == "right" {
                        ToolbarItem(placement: .principal) {
                            compactPickers
                        }
                    }
                }
            }
        }
        .sheet(isPresented: $showSettings) {
            SettingsView(
                bookmarkManager: bookmarkManager,
                isReloading: feedManager.isLoading,
                onReload: { Task { await feedManager.forceRefresh() } },
                tractate: tractate.name,
                daf: selectedDaf == Double(Int(selectedDaf))
                    ? "\(Int(selectedDaf))" : "\(selectedDaf)"
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
                        storedTractateIndex = bookmark.tractateIndex
                    }
                    selectedDaf = Double(bookmark.daf)
                    storedDaf = Double(bookmark.daf)
                    imageDaf = bookmark.daf
                    imageSide = bookmark.amud
                    selectedSide = bookmark.amud
                    storedSide = bookmark.amud
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
            // iPhone: restore text mode session if last mode was text
            if horizontalSizeClass != .regular && mainContentMode == .text {
                let sameDaf = lastTextTractate == tractate.name && lastTextDaf == selectedDaf
                Task {
                    await studyManager.startSession(
                        tractate: tractate.name, daf: Int(selectedDaf), mode: .facts, quizMode: quizMode,
                        startAtAmudB: !sameDaf && selectedSide == 1,
                        startAtSectionIndex: sameDaf ? lastTextSectionIndex : nil)
                }
            }
        }
        .onChange(of: selectedDaf) { _, newDaf in
            shiurInitialRestoreDone = true  // daf change is not a launch restore
            Task { await shiurClient.loadSegments(tractate: tractate.name, daf: newDaf) }
            if suppressDafSessionSync {
                suppressDafSessionSync = false
            } else if (horizontalSizeClass == .regular && iPadRightPanel == .study)
                || (horizontalSizeClass != .regular && mainContentMode == .text) {
                Task {
                    await studyManager.startSession(
                        tractate: tractate.name, daf: Int(newDaf), mode: .facts, quizMode: quizMode,
                        startAtAmudB: selectedSide == 1)
                }
            }
        }
        // Keep the picker readout (selectedDaf/selectedSide) in sync with Study Mode's own
        // navigation — crossing a daf boundary via Prev Daf/Next Daf, or crossing the amud A/B
        // boundary while paging through sections within the same daf.
        //
        // selectedDaf here must stay a whole daf number, never daf+0.5 for "amud b" — the .5
        // suffix is reserved for genuine half-daf *audio episodes* (see dafPickerItems, which
        // only appends daf+0.5 when feedManager.episodeIndex actually has an entry there).
        // Study Mode sessions always key on a whole daf (StudySession.daf: Int); amud is carried
        // separately via selectedSide. Setting selectedDaf to an arbitrary daf+0.5 that isn't a
        // real episode entry made it fall outside dafPickerItems, and the picker's UIKit-backed
        // .menu style then rendered the daf number blank — reproduced by Prev Daf landing on
        // amud b, and by paging Next across the amud a/b boundary within the same daf.
        .onChange(of: studySessionDafSide) { _, newValue in
            guard let newValue else { return }
            let newSelectedDaf = Double(newValue.daf)
            let dafChanged = newValue.daf != Int(selectedDaf)
            let sideChanged = newValue.side != selectedSide
            guard dafChanged || sideChanged else { return }
            if dafChanged { suppressDafSessionSync = true }
            if sideChanged { suppressSideSessionSync = true }
            selectedDaf = newSelectedDaf
            storedDaf = newSelectedDaf
            imageDaf = newValue.daf
            imageSide = newValue.side
            selectedSide = newValue.side
            storedSide = newValue.side
        }
        .onChange(of: selectedTractateIndex) { _, _ in
            shiurInitialRestoreDone = true  // tractate change is not a launch restore
            if audioPlayer.isStopped { shiurClient.reset() }
            Task { await shiurClient.loadSegments(tractate: tractate.name, daf: selectedDaf) }
            if (horizontalSizeClass == .regular && iPadRightPanel == .study)
                || (horizontalSizeClass != .regular && mainContentMode == .text) {
                Task {
                    await studyManager.startSession(
                        tractate: tractate.name, daf: Int(selectedDaf), mode: .facts, quizMode: quizMode,
                        startAtAmudB: selectedSide == 1)
                }
            }
        }
        .onChange(of: audioPlayer.isStopped) { _, isStopped in
            if !isStopped {
                audioLockedTractateIndex = selectedTractateIndex
                audioLockedDaf = selectedDaf
                shiurClient.snapshotAudioSegments()
            }
        }
        // Mirror audio position into shiur/text only when viewing the same daf that is playing.
        .onChange(of: shiurClient.audioCurrentSegmentIndex) { _, newIdx in
            guard !audioPlayer.isStopped,
                  selectedTractateIndex == audioLockedTractateIndex,
                  selectedDaf == audioLockedDaf else { return }
            shiurClient.currentSegmentIndex = newIdx
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
        // Sync the a/b picker and content position when switching modes on iPhone.
        // A direct Shiur↔Text switch carries the exact position across via sefariaIndex;
        // any other transition (e.g. from the Daf image, or on launch) keeps restoring each
        // mode's own last-remembered position, same as before.
        //
        // studySessionIsCurrent guards against a stale studyManager.session: Shiur mode does
        // not restart the study session on a daf change (only Text mode does — see the
        // onChange(of: selectedDaf) handler above), so if the user changes daf while in Shiur
        // mode, studyManager.session can still point at whatever daf they were last actually
        // in Text mode for. Without this guard, a direct Shiur→Text switch would jump within
        // that stale session — showing the wrong daf's text while the (always-fresh-per-daf)
        // shiur pill strip correctly shows the current daf's titles.
        .onChange(of: mainContentMode) { oldMode, newMode in
            let studySessionIsCurrent = studyManager.session?.tractate == tractate.name
                && studyManager.session?.daf == Int(selectedDaf)
            if newMode == .shiur {
                if oldMode == .text, studySessionIsCurrent,
                   let sefariaIdx = studyManager.session?.currentSection?.firstSegmentIndex,
                   let segIdx = shiurSegmentIndex(
                       forRangeStarting: sefariaIdx, endingBefore: currentSectionRangeEnd()) {
                    shiurClient.currentSegmentIndex = segIdx
                }
                if let bIdx = shiurClient.amudBSegmentIndex {
                    // Sync picker to shiur's current position (reflects the jump above too).
                    let newSide = shiurClient.currentSegmentIndex >= bIdx ? 1 : 0
                    selectedSide = newSide
                    storedSide = newSide
                }
            } else if newMode == .text {
                if oldMode == .shiur, studySessionIsCurrent,
                   shiurClient.currentSegmentIndex < shiurClient.segments.count,
                   let sefariaIdx = shiurClient.segments[shiurClient.currentSegmentIndex].sefariaIndex {
                    studyManager.jumpToSection(containing: sefariaIdx)
                } else {
                    let sessionMatchesDaf = studyManager.session != nil
                        && lastTextTractate == tractate.name
                        && lastTextDaf == selectedDaf
                    if sessionMatchesDaf {
                        if lastTextSectionIndex > 0 {
                            let count = studyManager.session?.sections.count ?? 0
                            studyManager.session?.currentSectionIndex = min(lastTextSectionIndex, count - 1)
                        } else if selectedSide == 1, let bIdx = studyManager.session?.amudBSectionIndex {
                            studyManager.session?.currentSectionIndex = bIdx
                        }
                    } else if !studyManager.isLoadingText {
                        Task {
                            await studyManager.startSession(
                                tractate: tractate.name, daf: Int(selectedDaf), mode: .facts, quizMode: quizMode,
                                startAtAmudB: selectedSide == 1)
                        }
                    }
                }
            }
        }
        // Keep the a/b picker in sync as audio plays through the daf (both iPad and iPhone).
        .onChange(of: shiurClient.currentSegmentIndex) { _, newIdx in
            guard let bIdx = shiurClient.amudBSegmentIndex else { return }
            let shiurVisible = horizontalSizeClass == .regular || mainContentMode == .shiur
            guard shiurVisible else { return }
            let newSide = newIdx >= bIdx ? 1 : 0
            if newSide != selectedSide { selectedSide = newSide; storedSide = newSide }
        }
        // Save text-mode position so we can restore to the exact section on relaunch.
        .onChange(of: studyManager.session?.currentSectionIndex) { _, newIdx in
            guard mainContentMode == .text, let idx = newIdx else { return }
            lastTextSectionIndex = idx
            lastTextTractate = tractate.name
            lastTextDaf = selectedDaf
        }
        // Save shiur segment position continuously so we can restore the exact spot on relaunch.
        .onChange(of: shiurClient.currentSegmentIndex) { _, newIdx in
            guard mainContentMode == .shiur || horizontalSizeClass == .regular else { return }
            lastShiurSegmentIndex = newIdx
            lastShiurTractate = tractate.name
            lastShiurDaf = selectedDaf
        }
        // On first segment load after launch, restore shiur position.
        // shiurInitialRestoreDone prevents this from re-firing on subsequent daf changes.
        .onChange(of: shiurClient.amudBSegmentIndex) { _, bIdx in
            guard !shiurInitialRestoreDone else { return }
            shiurInitialRestoreDone = true
            guard mainContentMode == .shiur || horizontalSizeClass == .regular else { return }
            guard shiurClient.currentSegmentIndex == 0 else { return }
            let sameDaf = lastShiurTractate == tractate.name && lastShiurDaf == selectedDaf
            if sameDaf && lastShiurSegmentIndex > 0 {
                shiurClient.currentSegmentIndex = lastShiurSegmentIndex
            } else if selectedSide == 1, let bIdx {
                shiurClient.currentSegmentIndex = bIdx
            }
        }
    }

    // MARK: - iPad Two-Column Layout

    private var iPadLayout: some View {
        GeometryReader { geo in
            let totalWidth = geo.size.width
            // Handle is narrower when a panel is collapsed (just a restore button).
            let handleWidth: CGFloat = collapsedSide == "none" ? 24 : 20
            let contentWidth = totalWidth - handleWidth

            // Live left width — unclamped during drag so the user can reach either edge.
            let leftWidth: CGFloat = {
                switch collapsedSide {
                case "left":  return 0
                case "right": return contentWidth
                default:
                    let raw = CGFloat(splitFraction) + splitDragDelta / contentWidth
                    return contentWidth * max(0, min(1, raw))
                }
            }()

            let isPortrait = geo.size.height > geo.size.width
            let portraitTopPad: CGFloat = isPortrait ? 20 : 0

            // Daf image fills the full left-column height.
            // Audio controls float over the bottom of the image as a pill overlay.
            let audioH: CGFloat = 120

            HStack(spacing: 0) {

                // ── Left column ──────────────────────────────────────────────────
                if collapsedSide != "left" {
                    VStack(spacing: 0) {
                        // Split mode: compact menu pickers aligned with the right panel's Shiur/Study picker.
                        if collapsedSide != "right" {
                            Spacer().frame(height: portraitTopPad)
                            compactPickers
                                .padding(.horizontal, 16)
                                .padding(.vertical, 8)
                                .background(
                                    RoundedRectangle(cornerRadius: 10, style: .continuous)
                                        .fill(appFg.opacity(0.07))
                                        .stroke(appFg.opacity(0.25), lineWidth: 1)
                                )
                                .padding(.horizontal, 12)
                        }
                        ZStack(alignment: .bottom) {
                            dafOnlyView
                                .frame(maxWidth: .infinity, maxHeight: .infinity)
                            bottomControls
                                .frame(height: audioH)
                                .background(
                                    RoundedRectangle(cornerRadius: 16, style: .continuous)
                                        .fill(appBg.opacity(0.92))
                                        .shadow(color: .black.opacity(0.2), radius: 8, x: 0, y: -2)
                                )
                                .padding(.horizontal, 12)
                                .padding(.bottom, 6)
                        }
                    }
                    .frame(width: leftWidth)
                    .clipped()
                }

                // ── Divider / collapse handle ────────────────────────────────────
                if collapsedSide == "left" {
                    // Left panel is collapsed — show a thin expand handle on the left edge.
                    Button {
                        withAnimation(.easeInOut(duration: 0.3)) { collapsedSide = "none" }
                    } label: {
                        VStack {
                            Spacer()
                            Image(systemName: "chevron.right")
                                .font(.caption)
                                .foregroundStyle(appFg.opacity(0.7))
                            Spacer()
                        }
                    }
                    .frame(width: handleWidth)
                    .background(appFg.opacity(0.08))
                    .contentShape(Rectangle())

                } else if collapsedSide == "right" {
                    // Right panel is collapsed — show a thin expand handle on the right edge.
                    Button {
                        withAnimation(.easeInOut(duration: 0.3)) { collapsedSide = "none" }
                    } label: {
                        VStack {
                            Spacer()
                            Image(systemName: "chevron.left")
                                .font(.caption)
                                .foregroundStyle(appFg.opacity(0.7))
                            Spacer()
                        }
                    }
                    .frame(width: handleWidth)
                    .background(appFg.opacity(0.08))
                    .contentShape(Rectangle())

                } else {
                    // Normal draggable divider — dots pill on a faint line.
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
                    .frame(width: handleWidth)
                    .contentShape(Rectangle())
                    .gesture(
                        DragGesture(minimumDistance: 0)
                            .updating($splitDragDelta) { value, state, _ in
                                state = value.translation.width
                            }
                            .onEnded { value in
                                let predicted = CGFloat(splitFraction) + value.predictedEndTranslation.width / contentWidth
                                let actual    = CGFloat(splitFraction) + value.translation.width / contentWidth
                                let moved     = abs(value.translation.width)

                                // Collapse by deliberate drag: finger reached past 20 % / 80 %.
                                // Collapse by fast flick:  predicted end is past 15 % / 85 %
                                //   AND the finger moved ≥ 60 pt — guards against a tiny
                                //   fast tap on the handle triggering an accidental snap.
                                // Otherwise: normal resize, clamped to 20 %–80 %.
                                if actual < 0.2 || (predicted < 0.15 && moved > 60) {
                                    withAnimation(.easeInOut(duration: 0.3)) { collapsedSide = "left" }
                                } else if actual > 0.8 || (predicted > 0.85 && moved > 60) {
                                    withAnimation(.easeInOut(duration: 0.3)) { collapsedSide = "right" }
                                } else {
                                    splitFraction = Double(max(0.2, min(0.8, actual)))
                                }
                            }
                    )
                }

                // ── Right column ──────────────────────────────────────────────────
                if collapsedSide != "right" {
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
                        // Same direct-switch-only sync as the iPhone mainContentMode handler
                        // above — iPad's Study panel defaults to the Translation tab, so this
                        // toggle is the direct equivalent of iPhone's Shiur/Text switch.
                        .onChange(of: iPadRightPanel) { oldPanel, newPanel in
                            if newPanel == .study {
                                let sefariaIdx = (oldPanel == .shiur
                                    && shiurClient.currentSegmentIndex < shiurClient.segments.count)
                                    ? shiurClient.segments[shiurClient.currentSegmentIndex].sefariaIndex
                                    : nil
                                Task {
                                    await studyManager.startSession(
                                        tractate: tractate.name, daf: Int(selectedDaf),
                                        mode: .facts, quizMode: quizMode)
                                    if let sefariaIdx {
                                        studyManager.jumpToSection(containing: sefariaIdx)
                                    }
                                }
                            } else if newPanel == .shiur, oldPanel == .study,
                                      studyManager.session?.tractate == tractate.name,
                                      studyManager.session?.daf == Int(selectedDaf),
                                      let sefariaIdx = studyManager.session?.currentSection?.firstSegmentIndex,
                                      let segIdx = shiurSegmentIndex(
                                          forRangeStarting: sefariaIdx, endingBefore: currentSectionRangeEnd()) {
                                shiurClient.currentSegmentIndex = segIdx
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
    }

    /// Daf page only — no shiur toggle (iPad left column; shiur lives in the right column).
    @ViewBuilder private var dafOnlyView: some View {
        if pageManager.hasPages(for: tractate.name) {
            DafPageView(
                tractate: tractate,
                daf: $imageDaf,
                displaySide: $imageSide,
                selectedSide: $selectedSide,
                pageManager: pageManager,
                foregroundColor: appFg
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
                // Shiur header — tractate + daf + print
                HStack(spacing: 6) {
                    Text("\(tractate.name) \(Int(selectedDaf))")
                        .font(.headline)
                        .foregroundStyle(appFg)
                    Spacer()
                    Button {
                        PrintManager.present(.shiur(
                            tractate: tractate.name,
                            daf: FeedManager.dafLabel(selectedDaf),
                            text: text
                        ))
                    } label: {
                        Image(systemName: "printer")
                            .font(.callout)
                            .foregroundStyle(appFg.opacity(0.55))
                    }
                }
                .padding(.horizontal)
                .padding(.vertical, 10)
                shiurNavigationStrip
                ShiurTextView(
                    rewriteText: text,
                    currentSegmentIndex: shiurClient.currentSegmentIndex,
                    foreground: appFg,
                    useWhiteBackground: useWhiteBackground,
                    amudBSegmentIndex: shiurClient.amudBSegmentIndex,
                    amudBMicroTitle: shiurClient.amudBMicroTitle,
                    scrollRequest: $shiurForceScrollIndex,
                    onSegmentVisible: { idx in shiurClient.currentSegmentIndex = idx }
                )
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        } else {
            VStack(spacing: 16) {
                Spacer()
                Image(systemName: "book.closed")
                    .font(.system(size: 44))
                    .foregroundStyle(appFg.opacity(0.35))
                Text("No written shiur available on this daf")
                    .font(.callout)
                    .foregroundStyle(appFg)
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
                    Group {
                        if mainContentMode == .text {
                            mainTextContent
                        } else {
                            dafAndShiurView
                        }
                    }
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

            if !showStudyMode {
                bottomControls
                    .padding(.horizontal, 8)
            }
        }
    }

    // MARK: - Picker Row (all form factors)

    @ViewBuilder private var pickerRow: some View {
        HStack(spacing: 8) {
            compactPickers
                .padding(.horizontal, 8)
                .padding(.vertical, 4)
                .background(
                    RoundedRectangle(cornerRadius: 20, style: .continuous)
                        .fill(appFg.opacity(0.07))
                        .stroke(appFg.opacity(0.25), lineWidth: 1)
                )
                .layoutPriority(1)

            HStack(spacing: 0) {
                contentModeButton("Daf",  mode: .daf)
                contentModeButton("Text", mode: .text)
                if shiurClient.shiurRewrite != nil {
                    contentModeButton("Shiur", mode: .shiur)
                }
            }
            .padding(.horizontal, 4)
            .padding(.vertical, 4)
            .background(
                RoundedRectangle(cornerRadius: 20, style: .continuous)
                    .fill(appFg.opacity(0.07))
                    .stroke(appFg.opacity(0.25), lineWidth: 1)
            )

        }
        .padding(.horizontal, 8)
        .padding(.top, 4)
        .padding(.bottom, 8)
    }

    // MARK: - Compact Pickers (all form factors)

    /// Width of the daf picker button — constant at 3-digit size so UIKit has
    /// enough room to render any daf label without wrapping.
    private var dafPickerWidth: CGFloat {
        let attrs = [NSAttributedString.Key.font: UIFont.preferredFont(forTextStyle: .caption1)]
        return ceil(("000" as NSString).size(withAttributes: attrs).width) + 32
    }

    @ViewBuilder private var compactPickers: some View {
        HStack(spacing: 2) {
            Picker(selection: $selectedTractateIndex) {
                ForEach(allTractates.indices, id: \.self) { i in
                    Text(allTractates[i].name).font(.caption).tag(i)
                }
            } label: {
                Text(tractate.name)
                    .font(.caption)
                    .lineLimit(1)
            }
            .pickerStyle(.menu)
            .menuIndicator(.hidden)
            .font(.caption)
            .fixedSize()
            .onChange(of: selectedTractateIndex) { _, newIdx in
                storedTractateIndex = newIdx
                if suppressTractateReset {
                    suppressTractateReset = false
                } else {
                    selectedDaf = Double(tractate.startDaf)
                    storedDaf = Double(tractate.startDaf)
                    imageDaf = tractate.startDaf
                    imageSide = tractate.startAmud
                    selectedSide = tractate.startAmud
                    storedSide = tractate.startAmud
                }
            }

            Picker(selection: $selectedDaf) {
                ForEach(dafPickerItems, id: \.self) { daf in
                    Text(FeedManager.dafLabel(daf)).font(.caption).tag(daf)
                }
            } label: {
                Text(FeedManager.dafLabel(selectedDaf))
                    .font(.caption)
                    .lineLimit(1)
            }
            .pickerStyle(.menu)
            .menuIndicator(.hidden)
            .font(.caption)
            .frame(width: dafPickerWidth)
            .onChange(of: selectedDaf) { _, newVal in
                storedDaf = newVal
                imageDaf = Int(newVal)
                // Skip re-deriving the amud side here when it was just set explicitly by the
                // Study Mode sync (see onChange(of: studySessionDafSide)) — otherwise this
                // handler's own isHalf/startDaf inference can override it (e.g. for a tractate
                // whose startAmud == 1, landing back on that daf would force side back to 1).
                guard !suppressDafSessionSync else { return }
                let isHalf = newVal.truncatingRemainder(dividingBy: 1) != 0
                let side = isHalf ? 1 : (newVal == Double(tractate.startDaf) ? tractate.startAmud : 0)
                imageSide = side
                selectedSide = side
                storedSide = side
            }

            Picker("Amud", selection: $selectedSide) {
                Text("a").tag(0)
                Text("b").tag(1)
            }
            .pickerStyle(.segmented)
            .font(.footnote)
            .frame(width: 40)
            .onChange(of: selectedSide) { _, newVal in
                storedSide = newVal
                imageSide = newVal
                if suppressSideSessionSync {
                    suppressSideSessionSync = false
                    return
                }
                // Jump the text view to the correct amud when the picker changes.
                if mainContentMode == .text {
                    Task {
                        if newVal == 1 { await studyManager.jumpToAmudB() }
                        else           { await studyManager.jumpToAmudA() }
                    }
                }
                if let bIdx = shiurClient.amudBSegmentIndex {
                    // Guard against the feedback loop: tapping a pill changes currentSegmentIndex,
                    // which syncs selectedSide as a side-effect, which would then reset
                    // currentSegmentIndex back to bIdx/0. Only navigate if the segment is NOT
                    // already on the correct side — meaning this is a genuine user picker tap.
                    let currentSide = shiurClient.currentSegmentIndex >= bIdx ? 1 : 0
                    if currentSide != newVal {
                        shiurClient.currentSegmentIndex = (newVal == 1) ? bIdx : 0
                    }
                    let isSameDaf = !audioPlayer.isStopped
                        && selectedTractateIndex == audioLockedTractateIndex
                        && selectedDaf == audioLockedDaf
                    if isSameDaf {
                        if newVal == 1 {
                            let secs = shiurClient.amudBSeconds
                                ?? (bIdx < shiurClient.segments.count ? shiurClient.segments[bIdx].seconds : nil)
                            if let secs {
                                audioPlayer.seek(to: secs / audioPlayer.duration)
                            }
                        } else {
                            audioPlayer.skip(by: -audioPlayer.currentTime)
                        }
                    }
                }
            }

        }
        .tint(appFg)
        .colorScheme(useWhiteBackground ? .light : .dark)
    }

    /// Button used in the iPhone Daf/Text/Shiur toggle row.
    private func contentModeButton(_ label: String, mode: MainContentMode) -> some View {
        Button {
            mainContentMode = mode
            if mode == .text, studyManager.session == nil, !studyManager.isLoadingText {
                Task {
                    await studyManager.startSession(
                        tractate: tractate.name, daf: Int(selectedDaf), mode: .facts, quizMode: quizMode,
                        startAtAmudB: selectedSide == 1)
                }
            }
        } label: {
            Text(label)
                .font(.footnote)
                .padding(.horizontal, 6)
                .padding(.vertical, 4)
                .background(
                    RoundedRectangle(cornerRadius: 14, style: .continuous)
                        .fill(mainContentMode == mode ? appFg.opacity(0.25) : Color.clear)
                )
        }
        .buttonStyle(.plain)
        .foregroundStyle(appFg)
    }

    private var shiurDisplayText: String? {
        shiurShowSources
            ? (shiurClient.shiurFinal ?? shiurClient.shiurRewrite)
            : shiurClient.shiurRewrite
    }

    // MARK: - Shiur Chapter Navigation Strip (shown when reading shiur without audio)

    /// Chip strip for navigating shiur segments without audio playback.
    /// Tapping a chip scrolls the shiur text to that macro segment.
    /// Chip strip for navigating shiur segments without audio playback.
    /// Tapping a chip scrolls the shiur text to that macro segment.
    @ViewBuilder private var shiurNavigationStrip: some View {
        if !shiurClient.segments.isEmpty {
            HStack(spacing: 0) {
                ScrollViewReader { proxy in
                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack(spacing: 6) {
                            ForEach(Array(shiurClient.segments.enumerated()), id: \.offset) { idx, seg in
                                let isActive = idx == shiurClient.currentSegmentIndex
                                Button {
                                    shiurClient.currentSegmentIndex = idx
                                    shiurForceScrollIndex = idx
                                    // Seek audio to this segment when the same daf is playing.
                                    let isSameDaf = !audioPlayer.isStopped
                                        && selectedTractateIndex == audioLockedTractateIndex
                                        && selectedDaf == audioLockedDaf
                                    if isSameDaf && audioPlayer.duration > 0 {
                                        audioPlayer.seek(to: seg.seconds / audioPlayer.duration)
                                        shiurClient.jumpToAudioSegment(idx)
                                    }
                                } label: {
                                    Text(seg.displayTitle)
                                        .font(.caption2)
                                        .lineLimit(1)
                                        .padding(.horizontal, 8)
                                        .padding(.vertical, 4)
                                        .background(Capsule().fill(isActive ? appFg.opacity(0.85) : appFg.opacity(0.15)))
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
                    .onAppear {
                        proxy.scrollTo(shiurClient.currentSegmentIndex, anchor: .center)
                    }
                }

                // Print button — right of the segment pills, with breathing room
                if let text = shiurDisplayText {
                    Button {
                        PrintManager.present(.shiur(
                            tractate: tractate.name,
                            daf: FeedManager.dafLabel(selectedDaf),
                            text: text
                        ))
                    } label: {
                        Image(systemName: "printer")
                            .font(.callout)
                            .foregroundStyle(appFg.opacity(0.55))
                    }
                    .padding(.leading, 6)
                    .padding(.trailing, 10)
                }
            }
            .frame(height: 30)
        }
    }

    // MARK: - Daf / Shiur Content (iPhone — on iPad the toggle lives in the right column)

    @ViewBuilder private var dafAndShiurView: some View {
        VStack(spacing: 0) {
            if mainContentMode == .shiur, let text = shiurDisplayText {
                shiurNavigationStrip
                ShiurTextView(
                    rewriteText: text,
                    currentSegmentIndex: shiurClient.currentSegmentIndex,
                    foreground: appFg,
                    useWhiteBackground: useWhiteBackground,
                    amudBSegmentIndex: shiurClient.amudBSegmentIndex,
                    amudBMicroTitle: shiurClient.amudBMicroTitle,
                    scrollRequest: $shiurForceScrollIndex,
                    onSegmentVisible: { idx in shiurClient.currentSegmentIndex = idx }
                )
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else if pageManager.hasPages(for: tractate.name) {
                DafPageView(
                    tractate: tractate,
                    daf: $imageDaf,
                    displaySide: $imageSide,
                    selectedSide: $selectedSide,
                    pageManager: pageManager,
                    foregroundColor: appFg
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

    // MARK: - Main Page Text Content (iPhone only — Text tab moved here from Study page)

    /// Shows the Sefaria daf text (with Source/Translation sub-tabs) in the main content area.
    @ViewBuilder private var mainTextContent: some View {
        VStack(spacing: 0) {
            StudyModeView(
                manager: studyManager,
                readAloudManager: readAloudManager,
                isAudioPlaying: !audioPlayer.isStopped,
                textOnly: true,
                onDismiss: { }
            )
        }
    }

    // MARK: - Study Mode Content

    @ViewBuilder private var studyModeContent: some View {
        StudyModeView(
            manager: studyManager,
            readAloudManager: readAloudManager,
            isAudioPlaying: !audioPlayer.isStopped,
            onDismiss: {
                if horizontalSizeClass == .regular {
                    // iPad: Back switches to shiur panel if available; otherwise stays in study
                    if shiurClient.shiurRewrite != nil {
                        withAnimation(.easeInOut(duration: 0.35)) { iPadRightPanel = .shiur }
                    }
                } else {
                    withAnimation(.easeInOut(duration: 0.5)) { showStudyMode = false }
                    if mainContentMode == .text {
                        // Text mode owns the session — restart it so the main page text view stays live
                        Task {
                            await studyManager.startSession(
                                tractate: tractate.name, daf: Int(selectedDaf), mode: .facts, quizMode: quizMode)
                        }
                    } else {
                        studyManager.endSession()
                    }
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
                                let segs = shiurClient.segments
                                let idx = shiurClient.currentSegmentIndex
                                let startAt = (idx > 0 && idx < segs.count) ? segs[idx].seconds : 0
                                audioPlayer.play(
                                    url: url,
                                    title: "\(tractate.name) \(FeedManager.dafLabel(selectedDaf))",
                                    startAt: startAt)
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
                AudioPlayingControls(
                    audioPlayer: audioPlayer,
                    shiurClient: shiurClient,
                    appFg: appFg,
                    useWhiteBackground: useWhiteBackground
                )
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
                storedTractateIndex = dafYomi.tractateIndex
            }
            selectedDaf = Double(dafYomi.daf)
            storedDaf = Double(dafYomi.daf)
            imageDaf = dafYomi.daf
            imageSide = 0
            selectedSide = 0
            storedSide = 0
            audioPlayer.stop()
        } catch {
            print("Failed to fetch today's daf: \(error.localizedDescription)")
        }
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

// MARK: - Audio Playing Controls
// Separate struct so only this view re-renders on currentTime ticks, not ContentView.
@MainActor
struct AudioPlayingControls: View {
    let audioPlayer: AudioPlayer
    @ObservedObject var shiurClient: ShiurClient
    let appFg: Color
    let useWhiteBackground: Bool

    @State private var backSkipPressed = false
    @State private var backRippleP: Double = 1
    @State private var fwdSkipPressed  = false
    @State private var fwdRippleP: Double = 1

    private var canSkip: Bool { audioPlayer.duration > 0 && !audioPlayer.isBuffering }

    var body: some View {
        VStack(spacing: 2) {
            Slider(
                value: Binding(
                    get: { audioPlayer.duration > 0 ? audioPlayer.currentTime / audioPlayer.duration : 0 },
                    set: { audioPlayer.seek(to: $0) }
                )
            )
            .padding(.horizontal)

            if !shiurClient.audioSegments.isEmpty && audioPlayer.duration > 0 {
                chapterStrip
            }

            if !audioPlayer.nowPlayingTitle.isEmpty {
                Text(audioPlayer.nowPlayingTitle)
                    .font(.caption2)
                    .foregroundStyle(appFg.opacity(0.55))
                    .lineLimit(1)
                    .padding(.top, 2)
            }

            HStack(alignment: .center, spacing: 0) {
                Text(formatTime(audioPlayer.currentTime))
                    .font(.caption.monospacedDigit())
                    .foregroundStyle(appFg.opacity(0.7))
                    .padding(.leading)

                Spacer()

                HStack(spacing: 8) {
                    ZStack {
                        Circle()
                            .stroke(appFg.opacity(0.45 * (1.0 - backRippleP)), lineWidth: 1.5)
                            .scaleEffect(1.0 + CGFloat(backRippleP) * 0.5)
                            .frame(width: 38, height: 38)
                        Image(systemName: "gobackward.30")
                            .font(.system(size: 24))
                            .foregroundStyle(canSkip ? appFg.opacity(0.8) : appFg.opacity(0.3))
                            .scaleEffect(backSkipPressed ? 0.82 : 1.0)
                            .animation(.spring(response: 0.15, dampingFraction: 0.5), value: backSkipPressed)
                    }
                    .onTapGesture {
                        guard canSkip else { return }
                        audioPlayer.skip(by: -30)
                        backSkipPressed = true
                        DispatchQueue.main.asyncAfter(deadline: .now() + 0.14) { backSkipPressed = false }
                        backRippleP = 0
                        DispatchQueue.main.async { withAnimation(.easeOut(duration: 0.4)) { backRippleP = 1 } }
                    }

                    Button { audioPlayer.togglePlayPause() } label: {
                        Image(systemName: audioPlayer.isPlaying ? "pause.circle.fill" : "play.circle.fill")
                            .font(.system(size: 38))
                            .foregroundStyle(appFg)
                    }

                    ZStack {
                        Circle()
                            .stroke(appFg.opacity(0.45 * (1.0 - fwdRippleP)), lineWidth: 1.5)
                            .scaleEffect(1.0 + CGFloat(fwdRippleP) * 0.5)
                            .frame(width: 38, height: 38)
                        Image(systemName: "goforward.30")
                            .font(.system(size: 24))
                            .foregroundStyle(canSkip ? appFg.opacity(0.8) : appFg.opacity(0.3))
                            .scaleEffect(fwdSkipPressed ? 0.82 : 1.0)
                            .animation(.spring(response: 0.15, dampingFraction: 0.5), value: fwdSkipPressed)
                    }
                    .onTapGesture {
                        guard canSkip else { return }
                        audioPlayer.skip(by: 30)
                        fwdSkipPressed = true
                        DispatchQueue.main.asyncAfter(deadline: .now() + 0.14) { fwdSkipPressed = false }
                        fwdRippleP = 0
                        DispatchQueue.main.async { withAnimation(.easeOut(duration: 0.4)) { fwdRippleP = 1 } }
                    }

                    Button { audioPlayer.stop() } label: {
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
        }
        .padding(.bottom, 2)
    }

    @ViewBuilder private var chapterStrip: some View {
        ScrollViewReader { proxy in
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 6) {
                    ForEach(Array(shiurClient.audioSegments.enumerated()), id: \.offset) { idx, seg in
                        let isActive = idx == shiurClient.audioCurrentSegmentIndex
                        Button {
                            audioPlayer.seek(to: seg.seconds / audioPlayer.duration)
                            shiurClient.jumpToAudioSegment(idx)
                        } label: {
                            Text(seg.displayTitle)
                                .font(.caption2)
                                .lineLimit(1)
                                .padding(.horizontal, 8)
                                .padding(.vertical, 4)
                                .background(Capsule().fill(isActive ? appFg.opacity(0.85) : appFg.opacity(0.15)))
                                .foregroundStyle(isActive
                                                 ? (useWhiteBackground ? .white : SplashView.background)
                                                 : appFg.opacity(0.8))
                        }
                        .id(idx)
                    }
                }
                .padding(.horizontal)
            }
            .onChange(of: shiurClient.audioCurrentSegmentIndex) { _, newIdx in
                withAnimation { proxy.scrollTo(newIdx, anchor: .center) }
            }
        }
        .frame(height: 30)
    }

}

// MARK: - Daf Page Viewer

struct DafPageView: View {
    let tractate: Tractate
    @Binding var daf: Int
    @Binding var displaySide: Int   // actual displayed amud — lives in ContentView so daf+side updates are coalesced
    @Binding var selectedSide: Int  // picker selection only — does not change on swipe/arrow
    let pageManager: TalmudPageManager
    var foregroundColor: Color = .white

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
                ZStack {
                    ZoomableAsyncImage(
                        url: url,
                        onSwipeLeft: advanceAmud,
                        onSwipeRight: retreatAmud,
                        foregroundColor: foregroundColor
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
