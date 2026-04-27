import SwiftUI

/// Which content the iPad right column displays when study mode is not active.
private enum IPadRightPanel: String {
    case shiur = "shiur"
    case study = "study"
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
    @State private var showShiurText = false
    @State private var showSettings = false
    @State private var showBookmarkList = false
    @State private var showBookmarkEdit = false
    @State private var isFetchingDafYomi = false
    @State private var suppressTractateReset = false
    /// Prevents looping: only one automatic feed-refresh per play attempt.
    @State private var hasAutoRefreshedForAudio = false
    /// Tractate/daf frozen at the moment audio starts — stays fixed while picker freely moves.
    @State private var audioLockedTractateIndex: Int = 0
    @State private var audioLockedDaf: Double = 2.0

    @Environment(\.horizontalSizeClass) private var horizontalSizeClass

    /// iPad split divider position — fraction of total width given to the left (daf) column.
    @AppStorage("iPadSplitFraction") private var splitFraction: Double = 0.5
    @GestureState private var splitDragDelta: CGFloat = 0
    /// "none" | "left" (left panel collapsed) | "right" (right panel collapsed)
    @AppStorage("iPadCollapsedSide") private var collapsedSide: String = "none"
    /// iPad right-panel mode — persisted so the user's preference is remembered.
    @AppStorage("iPadRightPanel") private var iPadRightPanel: IPadRightPanel = .shiur

    var tractate: Tractate { allTractates[selectedTractateIndex] }

    /// Tractate/daf to use for locked display and study sessions when audio is playing.
    private var playingTractate: Tractate { allTractates[audioLockedTractateIndex] }
    private var playingDaf: Double { audioLockedDaf }

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
            if !isStopped {
                audioLockedTractateIndex = selectedTractateIndex
                audioLockedDaf = selectedDaf
                return
            }
            shiurClient.reset()
            Task { await shiurClient.loadSegments(tractate: tractate.name, daf: selectedDaf) }
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
                        .onChange(of: iPadRightPanel) { _, newPanel in
                            if newPanel == .study {
                                let sessionTractate = audioPlayer.isStopped ? tractate.name : playingTractate.name
                                let sessionDaf = audioPlayer.isStopped ? Int(selectedDaf) : Int(playingDaf)
                                Task {
                                    await studyManager.startSession(
                                        tractate: sessionTractate, daf: sessionDaf,
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
                // Shiur header — tractate + daf (lock icon when audio is playing)
                HStack(spacing: 6) {
                    if !audioPlayer.isStopped {
                        Image(systemName: "lock.fill")
                            .font(.footnote)
                            .foregroundStyle(appFg.opacity(0.55))
                    }
                    let headerTractate = audioPlayer.isStopped ? tractate : playingTractate
                    let headerDaf = audioPlayer.isStopped ? selectedDaf : playingDaf
                    Text("\(headerTractate.name) \(Int(headerDaf))")
                        .font(.headline)
                        .foregroundStyle(appFg)
                }
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

            if shiurClient.shiurRewrite != nil {
                HStack(spacing: 0) {
                    ForEach([(false, "Daf"), (true, "Shiur")], id: \.0) { val, label in
                        Button {
                            showShiurText = val
                        } label: {
                            Text(label)
                                .font(.footnote)
                                .padding(.horizontal, 6)
                                .padding(.vertical, 4)
                                .background(
                                    RoundedRectangle(cornerRadius: 14, style: .continuous)
                                        .fill(showShiurText == val ? appFg.opacity(0.25) : Color.clear)
                                )
                        }
                        .buttonStyle(.plain)
                        .foregroundStyle(appFg)
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

            if !audioPlayer.isStopped {
                Button {
                    withAnimation(.easeInOut(duration: 0.6)) { showStudyMode = true }
                    Task {
                        await studyManager.startSession(
                            tractate: playingTractate.name, daf: Int(playingDaf), mode: .facts, quizMode: quizMode)
                    }
                } label: {
                    Image(systemName: "book.circle.fill")
                        .font(.system(size: 38))
                        .foregroundStyle(appFg)
                }
            }
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
            }

        }
        .tint(appFg)
        .colorScheme(useWhiteBackground ? .light : .dark)
    }

    private var shiurDisplayText: String? {
        shiurShowSources
            ? (shiurClient.shiurFinal ?? shiurClient.shiurRewrite)
            : shiurClient.shiurRewrite
    }

    // MARK: - Daf / Shiur Content (iPhone — on iPad the toggle lives in the right column)

    @ViewBuilder private var dafAndShiurView: some View {
        VStack(spacing: 0) {
            if showShiurText, let text = shiurDisplayText {
                if !audioPlayer.isStopped {
                    HStack(spacing: 6) {
                        Image(systemName: "lock.fill")
                            .font(.caption2)
                            .foregroundStyle(appFg.opacity(0.55))
                        Text("\(playingTractate.name) \(Int(playingDaf))")
                            .font(.caption2)
                            .foregroundStyle(appFg.opacity(0.55))
                        Spacer()
                    }
                    .padding(.horizontal, 18)
                    .padding(.vertical, 5)
                }
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

            if !shiurClient.segments.isEmpty && audioPlayer.duration > 0 {
                chapterStrip
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
