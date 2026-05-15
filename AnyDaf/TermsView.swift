import SwiftUI

private struct BottomVisibleKey: PreferenceKey {
    static var defaultValue: CGFloat = 0
    static func reduce(value: inout CGFloat, nextValue: () -> CGFloat) {
        value = nextValue()
    }
}

struct TermsView: View {
    let onAccept: () -> Void
    @State private var hasScrolledToBottom = false

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    Text(termsText)
                        .font(.body)
                        .foregroundStyle(.primary)
                        .padding()

                    GeometryReader { geo in
                        Color.clear.preference(
                            key: BottomVisibleKey.self,
                            value: geo.frame(in: .global).maxY
                        )
                    }
                    .frame(height: 1)
                }
            }
            .onPreferenceChange(BottomVisibleKey.self) { maxY in
                if maxY > 0 && maxY <= UIScreen.main.bounds.height {
                    hasScrolledToBottom = true
                }
            }
            .navigationTitle("Terms of Service")
            .navigationBarTitleDisplayMode(.inline)
            .safeAreaInset(edge: .bottom) {
                Button(action: onAccept) {
                    Text("Accept & Continue")
                        .font(.headline)
                        .foregroundStyle(.white)
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(hasScrolledToBottom ? SplashView.background : Color.gray)
                        .clipShape(RoundedRectangle(cornerRadius: 12))
                }
                .disabled(!hasScrolledToBottom)
                .padding()
                .background(.ultraThinMaterial)
            }
        }
    }
}

private let termsText = """
Last updated: April 2026

Please read these Terms of Service carefully before using AnyDaf. By tapping "Accept & Continue," or by using AnyDaf or accessing its content, you agree to be bound by these terms.

1. PERSONAL USE ONLY

AnyDaf is provided for your personal, non-commercial Torah study. You may not use the app or any of its content for commercial purposes — including but not limited to resale, redistribution, institutional use, or inclusion in a paid product or service — without a written license from Yeshivat Chovevei Torah (YCT).

2. NO SCRAPING OR AUTOMATED ACCESS

You may not use bots, scrapers, crawlers, automated scripts, or any other tool to systematically access, download, copy, or harvest content from AnyDaf or its underlying data. All content must be accessed through the app interface only. You may not train any generative artificial product on the content of AnyDaf without an express written license from Rabbi Linzer.

3. INTELLECTUAL PROPERTY

All shiur content, transcriptions, summaries, and materials in AnyDaf are the property of Yeshivat Chovevei Torah and Rabbi Dov Linzer, and are protected by copyright law. You may not reproduce, distribute, publicly display, or create derivative works from this content without prior written permission from YCT.

4. COMMERCIAL LICENSING

Organizations or individuals seeking to use AnyDaf content for commercial purposes, institutional distribution, or any other use beyond personal study should contact YCT at dlinzer@yctorah.org.

5. DISCLAIMER

AnyDaf is provided "as is" without warranty of any kind, express or implied. YCT makes no representations regarding the accuracy, completeness, or availability of the content.

6. GOVERNING LAW AND EXCLUSIVE JURISDICTION

These Terms are governed by the laws of the State of New York, without regard to its conflict of law provisions. By using AnyDaf or accessing its content, you submit to the jurisdiction of, and venue in, the United States District Court for the S.D.N.Y., or if there is no subject matter jurisdiction in that court, to the Supreme Court, New York County.

7. CONTACT

Questions or licensing inquiries: dlinzer@yctorah.org
"""
