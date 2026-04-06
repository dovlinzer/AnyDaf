import SwiftUI

struct SettingsView: View {
    @ObservedObject var bookmarkManager: BookmarkManager
    @AppStorage("quizMode") private var quizMode: QuizMode = .multipleChoice
    @AppStorage("sourceDisplayMode") private var sourceDisplayMode: SourceDisplayMode = .toggle
    @AppStorage("useWhiteBackground") private var useWhiteBackground: Bool = false
    @AppStorage("shiurShowSources") private var shiurShowSources: Bool = true
    @Environment(\.dismiss) private var dismiss

    let isReloading: Bool
    let onReload: () -> Void

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    Link(destination: URL(string: "https://wl.donorperfect.net/weblink/weblink.aspx?name=yctorah&id=2")!) {
                        HStack {
                            Text("Donate to YCT")
                                .foregroundStyle(.primary)
                            Spacer()
                            Image(systemName: "heart.fill")
                                .foregroundStyle(.red)
                        }
                    }
                } header: {
                    Text("Support AnyDaf")
                } footer: {
                    Text("AnyDaf is provided free by Yeshivat Chovevei Torah. Your donation supports Torah learning.")
                }

                Section {
                    ForEach(SourceDisplayMode.allCases, id: \.rawValue) { mode in
                        Button {
                            sourceDisplayMode = mode
                        } label: {
                            HStack {
                                VStack(alignment: .leading, spacing: 4) {
                                    Text(mode.displayName)
                                        .foregroundStyle(.primary)
                                    Text(mode.modeDescription)
                                        .font(.caption)
                                        .foregroundStyle(.secondary)
                                }
                                Spacer()
                                if sourceDisplayMode == mode {
                                    Image(systemName: "checkmark")
                                        .foregroundStyle(.blue)
                                        .fontWeight(.semibold)
                                }
                            }
                        }
                    }
                } header: {
                    Text("Translation Display")
                } footer: {
                    Text("How the original Hebrew/Aramaic source is shown alongside the English translation.")
                }

                Section {
                    ForEach(QuizMode.allCases, id: \.rawValue) { mode in
                        Button {
                            quizMode = mode
                        } label: {
                            HStack {
                                VStack(alignment: .leading, spacing: 4) {
                                    Text(mode.displayName)
                                        .foregroundStyle(.primary)
                                    Text(mode.modeDescription)
                                        .font(.caption)
                                        .foregroundStyle(.secondary)
                                }
                                Spacer()
                                if quizMode == mode {
                                    Image(systemName: "checkmark")
                                        .foregroundStyle(.blue)
                                        .fontWeight(.semibold)
                                }
                            }
                        }
                    }
                } header: {
                    Text("Quiz Mode")
                }

                Section {
                    Toggle("Include source text", isOn: $shiurShowSources)
                } header: {
                    Text("Shiur")
                } footer: {
                    Text("Show Hebrew/Aramaic sources embedded in lecture notes.")
                }

                Section {
                    Toggle("White Background", isOn: $useWhiteBackground)
                } header: {
                    Text("Appearance")
                } footer: {
                    Text("Replaces the blue background with white.")
                }

                Section {
                    Button {
                        onReload()
                    } label: {
                        HStack {
                            Text("Reload Episode Index")
                                .foregroundStyle(.primary)
                            Spacer()
                            if isReloading {
                                ProgressView()
                            } else {
                                Image(systemName: "arrow.clockwise")
                                    .foregroundStyle(.blue)
                            }
                        }
                    }
                    .disabled(isReloading)
                } footer: {
                    Text("Fetches the latest list of available audio episodes.")
                }

                Section {
                    NavigationLink {
                        BookmarkListView(bookmarkManager: bookmarkManager)
                    } label: {
                        HStack {
                            Text("Manage Bookmarks")
                            Spacer()
                            Text("\(bookmarkManager.bookmarks.count)")
                                .foregroundStyle(.secondary)
                        }
                    }
                } header: {
                    Text("Bookmarks")
                }
            }
            .navigationTitle("Settings")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Done") { dismiss() }
                }
            }
        }
    }
}
