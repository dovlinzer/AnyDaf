import SwiftUI

struct DonationNudgeView: View {
    let onDismiss: () -> Void

    var body: some View {
        VStack(spacing: 24) {
            Spacer()

            VStack(spacing: 12) {
                Image(systemName: "heart.fill")
                    .font(.system(size: 44))
                    .foregroundStyle(.red)

                Text("Support AnyDaf")
                    .font(.title2.bold())

                Text("AnyDaf is provided free by Yeshivat Chovevei Torah. If you find it valuable, please consider supporting Torah learning at YCT.")
                    .multilineTextAlignment(.center)
                    .foregroundStyle(.secondary)
                    .padding(.horizontal)
            }

            Button("Close", action: onDismiss)
                .foregroundStyle(.secondary)

            Spacer()
        }
        .padding(32)
        .presentationDetents([.medium])
    }
}
