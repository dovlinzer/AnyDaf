import SwiftUI
import AVFoundation

// Regular user thresholds
private let kRegularEngagementHours: Double = 20          // 20 hours since last nudge
private let kRegularIntervalDays: Double = 30             // 30 days since last nudge
// "Donor" thresholds (user clicked Donate — we can't confirm payment completed)
private let kDonorEngagementHours: Double = 60
private let kDonorIntervalDays: Double = 90

@main
struct AnyDafApp: App {
    @State private var showSplash = true
    @State private var showDonationNudge = false
    @State private var showTerms = false
    @AppStorage("hasAcceptedTerms") private var hasAcceptedTerms: Bool = false
    @State private var sessionStart: Date?
    @State private var nudgeCheckedThisSession = false
    @Environment(\.scenePhase) private var scenePhase
    @AppStorage("totalEngagementSeconds") private var totalEngagementSeconds: Double = 0
    @AppStorage("lastDonationNudgeTimestamp") private var lastDonationNudgeTimestamp: Double = 0
    @AppStorage("engagementSecondsAtLastNudge") private var engagementSecondsAtLastNudge: Double = 0
    @AppStorage("didClickDonate") private var didClickDonate: Bool = false
    @State private var dedication: Dedication? = nil        // sheet item — non-nil = sheet visible
    @State private var dedicationPending: Dedication? = nil // fetched during splash, shown after
    @AppStorage("lastDedicationDateShown") private var lastDedicationDateShown: String = ""

    init() {
        try? AVAudioSession.sharedInstance().setCategory(.playback, mode: .default)
        try? AVAudioSession.sharedInstance().setActive(true)
        // Remove any YCT Library cache entries older than 7 days.
        ResourcesDiskCache.evictExpired()
        // Crash-loop guard: if the app crashed before reaching foreground last time,
        // reset the persisted daf to avoid a repeated crash on the same content.
        let defaults = UserDefaults.standard
        if defaults.bool(forKey: "launchInProgress") {
            // Previous launch never reached foreground (crashed) — reset to safety.
            defaults.set(2.0, forKey: "lastDaf")
            defaults.set(0, forKey: "lastAmud")
            defaults.removeObject(forKey: "iPadRightPanel")  // cleared → @AppStorage falls back to .shiur
        }
        defaults.set(true, forKey: "launchInProgress")
    }

    var body: some Scene {
        WindowGroup {
            ZStack {
                ContentView()

                if showSplash {
                    SplashView()
                        .transition(.opacity)
                }
            }
            .onAppear {
                DispatchQueue.main.asyncAfter(deadline: .now() + 4.2) {
                    withAnimation(.easeOut(duration: 0.5)) {
                        showSplash = false
                    }
                    if !hasAcceptedTerms {
                        showTerms = true
                    }
                    // Promote any dedication fetched during the splash delay
                    if let pending = dedicationPending {
                        dedication = pending
                        dedicationPending = nil
                    }
                }
            }
            .onChange(of: scenePhase) { _, phase in
                handleScenePhase(phase)
            }
            .fullScreenCover(isPresented: $showTerms) {
                TermsView {
                    hasAcceptedTerms = true
                    showTerms = false
                }
            }
            .sheet(isPresented: $showDonationNudge) {
                DonationNudgeView {
                    recordNudgeShown()
                    showDonationNudge = false
                }
            }
            .sheet(item: $dedication) { ded in
                DedicationBannerView(dedication: ded) {
                    dedication = nil
                }
            }
        }
    }

    private func handleScenePhase(_ phase: ScenePhase) {
        switch phase {
        case .active:
            // App reached foreground successfully — clear the crash-loop sentinel.
            UserDefaults.standard.set(false, forKey: "launchInProgress")
            sessionStart = Date()
            if !nudgeCheckedThisSession {
                nudgeCheckedThisSession = true
                if shouldShowNudge() {
                    showDonationNudge = true
                }
            }
            let today = DedicationService.todayDateString()
            if today != lastDedicationDateShown {
                Task {
                    if let ded = await DedicationService.fetch() {
                        lastDedicationDateShown = today  // only mark when a dedication is found
                        if showSplash {
                            // Hold until splash finishes; onAppear callback will promote it
                            dedicationPending = ded
                        } else {
                            // Splash already gone (re-foreground) — show immediately
                            dedication = ded
                        }
                    }
                    // If nil, don't mark — we'll check again on the next open.
                }
            }
        case .background:
            if let start = sessionStart {
                totalEngagementSeconds += Date().timeIntervalSince(start)
                sessionStart = nil
            }
            nudgeCheckedThisSession = false
        case .inactive:
            break
        @unknown default:
            break
        }
    }

    private func shouldShowNudge() -> Bool {
        let hoursThreshold = didClickDonate ? kDonorEngagementHours : kRegularEngagementHours
        let daysThreshold  = didClickDonate ? kDonorIntervalDays    : kRegularIntervalDays
        let hoursSinceLastNudge = (totalEngagementSeconds - engagementSecondsAtLastNudge) / 3600
        guard lastDonationNudgeTimestamp > 0 else {
            return hoursSinceLastNudge >= hoursThreshold
        }
        let daysSinceLastNudge = (Date().timeIntervalSince1970 - lastDonationNudgeTimestamp) / 86400
        return hoursSinceLastNudge >= hoursThreshold || daysSinceLastNudge >= daysThreshold
    }

    private func recordNudgeShown() {
        lastDonationNudgeTimestamp = Date().timeIntervalSince1970
        engagementSecondsAtLastNudge = totalEngagementSeconds
    }
}
