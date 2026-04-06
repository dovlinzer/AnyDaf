import SwiftUI

/// Splash screen shown immediately after the system launch screen.
/// Background and text colors match Launch Screen.storyboard exactly.
struct SplashView: View {
    // To change the color: update this AND the storyboard background.
    // #1B3A8A → R=0.106, G=0.227, B=0.541
    static let background = Color(red: 0.106, green: 0.227, blue: 0.541)

    var body: some View {
        GeometryReader { geo in
            ZStack {
                SplashView.background.ignoresSafeArea()

                // Title stack — matches storyboard centerY offset of -30
                VStack(spacing: 16) {
                    Text("AnyDaf")
                        .font(.system(size: 42, weight: .bold))
                        .foregroundStyle(.white)
                    Image("RabbiLinzer")
                        .resizable()
                        .scaledToFit()
                        .frame(width: 100, height: 100)
                    Text("Learn any daf with Rabbi Dov Linzer")
                        .font(.system(size: 17))
                        .foregroundStyle(Color(red: 0.75, green: 0.85, blue: 1))
                    Text("Powered by YCT and Sefaria")
                        .font(.system(size: 14).italic())
                        .foregroundStyle(Color(red: 0.75, green: 0.85, blue: 1).opacity(0.75))
                }
                .position(x: geo.size.width / 2,
                          y: geo.size.height / 2 - 30)

                // YCT logo — matches storyboard centerY offset of +165, width = 50%
                Image("Image")
                    .resizable()
                    .scaledToFit()
                    .frame(width: geo.size.width * 0.5)
                    .position(x: geo.size.width / 2,
                              y: geo.size.height / 2 + 210)
            }
        }
        .ignoresSafeArea()
    }
}

#Preview {
    SplashView()
}
