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
                    Toggle("White Background", isOn: $useWhiteBackground)
                    HStack(spacing: 0) {
                        let cases = StudyFontSize.displayCases
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

                        HStack(spacing: 0) {
                            Spacer(minLength: 4)
                            ForEach(cases.indices, id: \.self) { i in
                                let dotSize: CGFloat = 5 + CGFloat(i) * 2
                                Circle()
                                    .fill(i == idx ? Color.accentColor : Color.secondary.opacity(0.35))
                                    .frame(width: dotSize, height: dotSize)
                                    .animation(.spring(response: 0.25), value: studyFontSize)
                                if i < cases.count - 1 { Spacer(minLength: 4) }
                            }
                            Spacer(minLength: 4)
                        }
                        .frame(maxWidth: .infinity)

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
                    Picker("Translation Display", selection: $sourceDisplayMode) {
                        ForEach(SourceDisplayMode.allCases, id: \.rawValue) { mode in
                            Text(mode.displayName).tag(mode)
                        }
                    }
                    .pickerStyle(.menu)
                } header: {
                    Text("Translation Display")
                }

                Section {
                    Toggle("Include source text", isOn: $shiurShowSources)
                } header: {
                    Text("Shiur")
                }

                Section {
                    Picker("Quiz Mode", selection: $quizMode) {
                        ForEach(QuizMode.allCases, id: \.rawValue) { mode in
                            Text(mode.displayName).tag(mode)
                        }
                    }
                    .pickerStyle(.menu)
                } header: {
                    Text("Quiz Mode")
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
                        AboutView()
                    } label: {
                        Text("About AnyDaf")
                            .foregroundStyle(.blue)
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
