import SwiftUI

struct AboutView: View {
    var body: some View {
        List {
            Section {
                VStack(alignment: .leading, spacing: 12) {
                    Text("AnyDaf makes it easy to learn any daf of Talmud with Rabbi Dov Linzer's guidance — featuring shiurim, translations, summaries, study tools and resources for every page.")
                        .font(.subheadline)
                }
                .padding(.vertical, 4)
            } header: {
                Text("About AnyDaf")
            }

            Section {
                HStack {
                    Spacer()
                    Image("RabbiLinzer")
                        .resizable()
                        .scaledToFill()
                        .frame(width: 80, height: 80)
                        .clipShape(Circle())
                    Spacer()
                }
                .padding(.top, 4)

                VStack(alignment: .leading, spacing: 8) {
                    Text("Rabbi Dov Linzer is the Rosh HaYeshiva and President of Yeshivat Chovevei Torah (YCT). A leading rabbinic voice in the Modern Orthodox community for over 35 years, Rabbi Linzer teaches Torah widely and serves as the religious mentor and posek for hundreds of rabbis and communities worldwide. He is a prolific teacher and author dedicated to making Torah accessible to all.")
                        .font(.subheadline)
                }
                .padding(.vertical, 4)

                Link(destination: URL(string: "https://www.yctorah.org/faculty/rabbi-dov-linzer/")!) {
                    HStack {
                        Text("Rabbi Linzer's bio")
                        Spacer()
                        Image(systemName: "arrow.up.right")
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                    }
                }
            } header: {
                Text("Rabbi Dov Linzer")
            }

            Section {
                HStack {
                    Spacer()
                    Image("Image")
                        .resizable()
                        .scaledToFit()
                        .frame(height: 60)
                    Spacer()
                }
                .padding(.top, 4)

                VStack(alignment: .leading, spacing: 8) {
                    Text("Yeshivat Chovevei Torah is a leading Modern Orthodox rabbinical school, with over 160 of its ordained rabbis serving worldwide and 60 Israeli rabbis and rabbaniyot, alumni of its Rikmah program, serving in Israel. YCT serves as the spiritual home or an open and inclusive Orthodoxy, promoting  visionary rabbinic leadership, inclusive communities, a Torah that speaks to our lives, and a halakha that meets every individual where they are at.")
                        .font(.subheadline)
                }
                .padding(.vertical, 4)

                Link(destination: URL(string: "https://www.yctorah.org")!) {
                    HStack {
                        Text("yctorah.org")
                        Spacer()
                        Image(systemName: "arrow.up.right")
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                    }
                }
            } header: {
                Text("Yeshivat Chovevei Torah")
            }
        }
        .navigationTitle("About")
        .navigationBarTitleDisplayMode(.inline)
    }
}

#Preview {
    NavigationStack {
        AboutView()
    }
}
