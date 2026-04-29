import SwiftUI

struct TermsView: View {
    let onAccept: () -> Void

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    Text(termsText)
                        .font(.body)
                        .foregroundStyle(.primary)
                        .padding()
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
                        .background(SplashView.background)
                        .clipShape(RoundedRectangle(cornerRadius: 12))
                }
                .padding()
                .background(.ultraThinMaterial)
            }
        }
    }
}

private let termsText = """
Last updated: April 2026

Please read these Terms of Service carefully before using AnyDaf. By tapping "Accept & Continue," you agree to be bound by these terms.

1. PERSONAL USE ONLY

AnyDaf is provided for your personal, non-commercial Torah study. You may not use the app or any of its content for commercial purposes — including but not limited to resale, redistribution, institutional use, or inclusion in a paid product or service — without a written license from Yeshivat Chovevei Torah (YCT).

2. NO SCRAPING OR AUTOMATED ACCESS

You may not use bots, scrapers, crawlers, automated scripts, or any other tool to systematically access, download, copy, or harvest content from AnyDaf or its underlying data. All content must be accessed through the app interface only.

3. INTELLECTUAL PROPERTY

All shiur content, transcriptions, summaries, and materials in AnyDaf are the property of Yeshivat Chovevei Torah and Rabbi Dov Linzer, and are protected by copyright law. You may not reproduce, distribute, publicly display, or create derivative works from this content without prior written permission from YCT.

4. COMMERCIAL LICENSING

Organizations or individuals seeking to use AnyDaf content for commercial purposes, institutional distribution, or any other use beyond personal study should contact YCT at dlinzer@yctorah.org.

5. DISCLAIMER

AnyDaf is provided "as is" without warranty of any kind, express or implied. YCT makes no representations regarding the accuracy, completeness, or availability of the content.

6. GOVERNING LAW

These Terms are governed by the laws of the State of New York, without regard to its conflict of law provisions.

7. CONTACT

Questions or licensing inquiries: dlinzer@yctorah.org
"""
