import SwiftUI

struct SettingsView: View {
    @ObservedObject var bookmarkManager: BookmarkManager
    @AppStorage("quizMode") private var quizMode: QuizMode = .multipleChoice
    @AppStorage("sourceDisplayMode") private var sourceDisplayMode: SourceDisplayMode = .toggle
    @AppStorage("useWhiteBackground") private var useWhiteBackground: Bool = false
    @AppStorage("studyFontSize") private var studyFontSize: StudyFontSize = .medium
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
                                Text(mode.displayName)
                                    .foregroundStyle(.primary)
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
                }

                Section {
                    ForEach(QuizMode.allCases, id: \.rawValue) { mode in
                        Button {
                            quizMode = mode
                        } label: {
                            HStack {
                                Text(mode.displayName)
                                    .foregroundStyle(.primary)
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
                }

                Section {
                    Toggle("White Background", isOn: $useWhiteBackground)
                    HStack(spacing: 0) {
                        // Tap small A to decrease
                        let cases = StudyFontSize.allCases
                        let idx = cases.firstIndex(of: studyFontSize) ?? 1
                        Button {
                            if idx > 0 { studyFontSize = cases[idx - 1] }
                        } label: {
                            Text("A")
                                .font(.footnote.weight(.semibold))
                                .foregroundStyle(idx > 0 ? Color.accentColor : Color.secondary)
                                .frame(width: 36, height: 44)
                                .contentShape(Rectangle())
                        }
                        .buttonStyle(.plain)

                        // Step dots — each dot is sized to match the font size it represents,
                        // and they span the full space between the two A buttons.
                        HStack(spacing: 0) {
                            Spacer(minLength: 4)
                            ForEach(cases.indices, id: \.self) { i in
                                let dotSize: CGFloat = 5 + CGFloat(i) * 2  // 5, 7, 9, 11
                                Circle()
                                    .fill(i == idx ? Color.accentColor : Color.secondary.opacity(0.35))
                                    .frame(width: dotSize, height: dotSize)
                                    .animation(.spring(response: 0.25), value: studyFontSize)
                                if i < cases.count - 1 { Spacer(minLength: 4) }
                            }
                            Spacer(minLength: 4)
                        }
                        .frame(maxWidth: .infinity)

                        // Tap large A to increase
                        Button {
                            if idx < cases.count - 1 { studyFontSize = cases[idx + 1] }
                        } label: {
                            Text("A")
                                .font(.title2.weight(.semibold))
                                .foregroundStyle(idx < cases.count - 1 ? Color.accentColor : Color.secondary)
                                .frame(width: 36, height: 44)
                                .contentShape(Rectangle())
                        }
                        .buttonStyle(.plain)
                    }
                    .padding(.vertical, 2)
                    Text(studyFontSize.displayName)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .frame(maxWidth: .infinity, alignment: .center)
                } header: {
                    Text("Appearance")
                } footer: {
                    Text("Study text size applies to translations, summaries, shiur, and quiz content.")
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
                } header: {
                    Text("Audio")
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

                Section {
                    NavigationLink {
                        AboutView()
                    } label: {
                        Text("About AnyDaf")
                    }
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
