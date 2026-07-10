import SwiftUI

struct DedicationBannerView: View {
    let dedication: Dedication
    let onDismiss: () -> Void
    @State private var sheetHeight: CGFloat = 500

    var body: some View {
        VStack(spacing: 24) {
            photoOrIcon

            Text(dedication.periodTitle)
                .font(.title2.bold())

            Text(dedication.formattedMessage)
                .multilineTextAlignment(.center)
                .foregroundStyle(.primary)
                .padding(.horizontal)

            Button("Continue Learning", action: onDismiss)
                .buttonStyle(.borderedProminent)
        }
        .padding(32)
        .frame(maxWidth: .infinity)
        .background(
            GeometryReader { geo in
                Color.clear
                    .onAppear { sheetHeight = geo.size.height }
                    .onChange(of: geo.size.height) { _, h in sheetHeight = h }
            }
        )
        .presentationDetents([.height(sheetHeight)])
    }

    @ViewBuilder
    private var photoOrIcon: some View {
        if let urlStr = dedication.photoURL {
            SupabaseStorageImage(urlString: urlStr)
                .frame(width: 160, height: 160)
                .clipShape(Circle())
                .overlay(Circle().stroke(Color(.systemGray5), lineWidth: 1))
        } else {
            bookIcon
        }
    }

    private var bookIcon: some View {
        Image(systemName: "book.fill")
            .font(.system(size: 44))
            .foregroundStyle(SplashView.background)
    }
}

/// Fetches a Supabase Storage image using the anon key so it works regardless
/// of whether the bucket's public-URL flag is enabled.
private struct SupabaseStorageImage: View {
    let urlString: String
    @State private var uiImage: UIImage? = nil

    var body: some View {
        Group {
            if let img = uiImage {
                Image(uiImage: img)
                    .resizable()
                    .scaledToFill()
            } else {
                Color.clear
            }
        }
        .task(id: urlString) {
            uiImage = await loadImage()
        }
    }

    private func loadImage() async -> UIImage? {
        // Convert the public-URL form to the authenticated endpoint form
        let authed = urlString.replacingOccurrences(
            of: "/storage/v1/object/public/",
            with: "/storage/v1/object/"
        )
        guard let url = URL(string: authed) else { return nil }
        var request = URLRequest(url: url)
        request.setValue(Secrets.supabaseAnonKey, forHTTPHeaderField: "apikey")
        request.setValue("Bearer \(Secrets.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
        guard let (data, response) = try? await URLSession.shared.data(for: request),
              (response as? HTTPURLResponse)?.statusCode == 200 else { return nil }
        return UIImage(data: data)
    }
}
