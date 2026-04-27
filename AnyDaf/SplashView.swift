import SwiftUI

/// Splash screen shown immediately after the system launch screen.
/// Background and text colors match Launch Screen.storyboard exactly.
struct SplashView: View {
    // To change the color: update this AND the storyboard background.
    // #1B3A8A → R=0.106, G=0.227, B=0.541
    static let background = Color(red: 0.106, green: 0.227, blue: 0.541)

    @Environment(\.horizontalSizeClass) private var sizeClass

    var body: some View {
        GeometryReader { geo in
            let short = min(geo.size.width, geo.size.height)
            let isPad = sizeClass == .regular
            ZStack(alignment: .bottom) {
                SplashView.background.ignoresSafeArea()

                // Main content centered in the upper portion
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
                .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .center)

                // Logo pinned near the bottom
                Image("Image")
                    .resizable()
                    .scaledToFit()
                    .frame(width: short * (isPad ? 0.325 : 0.50))
                    .clipShape(RoundedRectangle(cornerRadius: 16))
                    .padding(.bottom, geo.size.height * 0.075)
            }
        }
        .ignoresSafeArea()
    }
}

#Preview {
    SplashView()
}
