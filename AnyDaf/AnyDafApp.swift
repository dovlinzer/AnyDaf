import SwiftUI
import AVFoundation

private let kEngagementNudgeThreshold: Double = 3 * 3600   // 3 hours of cumulative use
private let kNudgeMinIntervalSeconds: Double = 60 * 86400  // 60 days between nudges

@main
struct AnyDafApp: App {
    @State private var showSplash = true
    @State private var showDonationNudge = false
    @State private var sessionStart: Date?
    @State private var nudgeCheckedThisSession = false
    @Environment(\.scenePhase) private var scenePhase
    @AppStorage("totalEngagementSeconds") private var totalEngagementSeconds: Double = 0
    @AppStorage("lastDonationNudgeTimestamp") private var lastDonationNudgeTimestamp: Double = 0

    init() {
        try? AVAudioSession.sharedInstance().setCategory(.playback, mode: .default)
        try? AVAudioSession.sharedInstance().setActive(true)
        // Remove any YCT Library cache entries older than 7 days.
        ResourcesDiskCache.evictExpired()
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
                }
            }
            .onChange(of: scenePhase) { phase in
                handleScenePhase(phase)
            }
            .sheet(isPresented: $showDonationNudge) {
                DonationNudgeView {
                    if let url = URL(string: "https://wl.donorperfect.net/weblink/weblink.aspx?name=yctorah&id=2") {
                        UIApplication.shared.open(url)
                    }
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
        guard totalEngagementSeconds >= kEngagementNudgeThreshold else { return false }
        let elapsed = Date().timeIntervalSince1970 - lastDonationNudgeTimestamp
        return elapsed >= kNudgeMinIntervalSeconds
    }

    private func recordNudgeShown() {
        lastDonationNudgeTimestamp = Date().timeIntervalSince1970
    }
}
