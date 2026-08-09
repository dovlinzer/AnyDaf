import SwiftUI
import AVFoundation

private class _PlayerContainer: UIView {
    let player = AVPlayer()
    private var playerLayer: AVPlayerLayer?

    override func layoutSubviews() {
        super.layoutSubviews()
        playerLayer?.frame = bounds
    }

    func configure(url: URL) {
        player.replaceCurrentItem(with: AVPlayerItem(url: url))
        player.isMuted = true
        let layer = AVPlayerLayer(player: player)
        // yct_splash.mp4 is a square (1:1) video with its rounded corners already
        // baked in (matted to the splash blue). Rounding via CALayer/clipShape on
        // AVPlayerLayer's hardware-composited content isn't reliable, and previously
        // the video's non-square source meant .resizeAspect letterboxed it inside
        // the square frame anyway, leaving the video's own sharp rectangle visible.
        layer.videoGravity = .resizeAspect
        self.layer.addSublayer(layer)
        playerLayer = layer
        player.play()
    }
}

private struct YCTLogoAnimated: UIViewRepresentable {
    func makeUIView(context: Context) -> _PlayerContainer {
        let view = _PlayerContainer()
        view.backgroundColor = .clear
        if let url = Bundle.main.url(forResource: "yct_splash", withExtension: "mp4") {
            view.configure(url: url)
        }
        return view
    }
    func updateUIView(_ uiView: _PlayerContainer, context: Context) {}
}

/// Splash screen shown immediately after the system launch screen.
/// Background and text colors match Launch Screen.storyboard exactly.
struct SplashView: View {
    // To change the color: update this AND the storyboard background.
    // #1B3A8A → R=0.106, G=0.227, B=0.541
    static let background = Color(red: 0.106, green: 0.227, blue: 0.541)

    // yct_splash.mp4 is cropped to the YCT logo's own proportions (836×514) so the
    // rounded box matches the logo's shape instead of leaving empty space above/below it.
    private static let logoAspectRatio: CGFloat = 836.0 / 514.0

    @Environment(\.horizontalSizeClass) private var sizeClass

    var body: some View {
        GeometryReader { geo in
            let short = min(geo.size.width, geo.size.height)
            let isPad = sizeClass == .regular
            let isLandscape = geo.size.width > geo.size.height
            // Matches AnyTorah's fixed 260pt logo size (AnyTorah isn't proportional to
            // screen width) on a typical iPhone; iPad keeps the same relative scale-down.
            let logoWidth = short * (isPad ? 0.42 : 0.65)
            let logoHeight = logoWidth / Self.logoAspectRatio
            let logoBottomPad = geo.size.height * 0.075
            // On iPad landscape the short screen height crowds the main content against
            // the logo pinned at the bottom, so instead of centering in the full height,
            // it centers within just the space above the logo (equal gap above the block
            // and between the block and the logo).
            let topSectionHeight = geo.size.height - logoHeight - logoBottomPad
            ZStack(alignment: .bottom) {
                SplashView.background.ignoresSafeArea()

                // Main content — centered normally, but on iPad landscape it's centered
                // within the space above the logo instead of the full screen height.
                VStack(spacing: 14) {
                    Text("AnyDaf")
                        .font(.system(size: 42, weight: .bold))
                        .foregroundStyle(.white)
                    Image("RabbiLinzer")
                        .resizable()
                        .scaledToFit()
                        .frame(width: short * (isPad ? 0.21 : 0.28), height: short * (isPad ? 0.21 : 0.28))
                    Text("Learn any daf with Rabbi Dov Linzer")
                        .font(.system(size: 17))
                        .foregroundStyle(Color(red: 0.75, green: 0.85, blue: 1))
                        .multilineTextAlignment(.center)
                    Text("Powered by YCT and Sefaria")
                        .font(.system(size: 13).italic())
                        .foregroundStyle(Color(red: 0.75, green: 0.85, blue: 1).opacity(0.75))
                }
                .padding(.horizontal, 32)
                .frame(maxWidth: .infinity,
                       maxHeight: (isPad && isLandscape) ? topSectionHeight : .infinity,
                       alignment: .center)
                .frame(maxWidth: .infinity, maxHeight: .infinity,
                       alignment: (isPad && isLandscape) ? .top : .center)

                // Logo pinned near the bottom
                YCTLogoAnimated()
                    .frame(width: logoWidth, height: logoHeight)
                    .clipShape(RoundedRectangle(cornerRadius: 16))
                    .padding(.bottom, logoBottomPad)
            }
        }
        .ignoresSafeArea()
    }
}

#Preview {
    SplashView()
}
