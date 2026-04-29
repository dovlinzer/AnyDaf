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
                DispatchQueue.main.asyncAfter(deadline: .now() + 2.0) {
                    withAnimation(.easeOut(duration: 0.5)) {
                        showSplash = false
                    }
                    if !hasAcceptedTerms {
                        showTerms = true
                    }
                }
            }
            .onChange(of: scenePhase) { phase in
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
                    if let url = URL(string: "https://wl.donorperfect.net/weblink/weblink.aspx?name=yctorah&id=2") {
                        UIApplication.shared.open(url)
                    }
                    didClickDonate = true
                    recordNudgeShown()
                    showDonationNudge = false
                } onDismiss: {
                    recordNudgeShown()
                    showDonationNudge = false
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
