import SwiftUI

struct SettingsView: View {
    @ObservedObject var bookmarkManager: BookmarkManager
    @AppStorage("quizMode") private var quizMode: QuizMode = .multipleChoice
    @AppStorage("useWhiteBackground") private var useWhiteBackground: Bool = false
    @AppStorage("studyFontSize") private var studyFontSize: StudyFontSize = .medium
    @AppStorage("shiurShowSources") private var shiurShowSources: Bool = true
    @AppStorage("shiurAutoScrollToAmudA") private var shiurAutoScrollToAmudA: Bool = false
    @AppStorage("printFontSize") private var printFontSize: StudyFontSize = .small
    @AppStorage("printLineSpacing") private var printLineSpacing: Double = 1.15
    @Environment(\.dismiss) private var dismiss
    @Environment(\.openURL) private var openURL

    let isReloading: Bool
    let onReload: () -> Void
    var tractate: String = ""
    var daf: String = ""

    var body: some View {
        NavigationStack {
            Form {
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
                } 

                Section {
                    Toggle("Include source text", isOn: $shiurShowSources)
                    Toggle("Always start scrolled to Amud A", isOn: $shiurAutoScrollToAmudA)
                } header: {
                    Text("Shiur")
                } footer: {
                    Text("When on, opening a daf's shiur skips past any introduction and starts at the beginning of Amud A.")
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
                    HStack(spacing: 0) {
                        let pCases = StudyFontSize.allCases
                        let pIdx = pCases.firstIndex(of: printFontSize) ?? 1
                        Button {
                            if pIdx > 0 { printFontSize = pCases[pIdx - 1] }
                        } label: {
                            Text("A")
                                .font(.footnote.weight(.semibold))
                                .foregroundStyle(pIdx > 0 ? Color.accentColor : Color.secondary)
                                .frame(width: 36, height: 44)
                                .contentShape(Rectangle())
                        }
                        .buttonStyle(.plain)

                        HStack(spacing: 0) {
                            Spacer(minLength: 4)
                            ForEach(pCases.indices, id: \.self) { i in
                                let dotSize: CGFloat = 5 + CGFloat(i) * 2
                                Circle()
                                    .fill(i == pIdx ? Color.accentColor : Color.secondary.opacity(0.35))
                                    .frame(width: dotSize, height: dotSize)
                                    .animation(.spring(response: 0.25), value: printFontSize)
                                if i < pCases.count - 1 { Spacer(minLength: 4) }
                            }
                            Spacer(minLength: 4)
                        }
                        .frame(maxWidth: .infinity)

                        Button {
                            if pIdx < pCases.count - 1 { printFontSize = pCases[pIdx + 1] }
                        } label: {
                            Text("A")
                                .font(.title2.weight(.semibold))
                                .foregroundStyle(pIdx < pCases.count - 1 ? Color.accentColor : Color.secondary)
                                .frame(width: 36, height: 44)
                                .contentShape(Rectangle())
                        }
                        .buttonStyle(.plain)
                    }
                    .padding(.vertical, 2)
                    Text(printFontSize.displayName)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .frame(maxWidth: .infinity, alignment: .center)

                    Picker("Line Spacing", selection: $printLineSpacing) {
                        Text("1.15× (compact)").tag(1.15)
                        Text("1.5× (relaxed)").tag(1.5)
                        Text("2.0× (double)").tag(2.0)
                    }
                    .pickerStyle(.menu)
                } header: {
                    Text("Print")
                } footer: {
                    Text("Controls the font size and line spacing used when printing shiur text and translations.")
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
                    Button {
                        let dafLine = tractate.isEmpty ? "" : "Tractate/Daf: \(tractate) \(daf)\n\n"
                        let body = "\(dafLine)Feedback type:\n" +
                            "[ ] Bug report\n" +
                            "[ ] Shiur text correction\n" +
                            "[ ] Summary or quiz issue\n" +
                            "[ ] Resources suggestion\n" +
                            "[ ] Other\n\n" +
                            "Details:\n\n"
                        let subjectEnc = "AnyDaf Feedback"
                            .addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? "AnyDaf Feedback"
                        let bodyEnc = body
                            .addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? body
                        if let url = URL(string: "mailto:anydaf@yctorah.org?subject=\(subjectEnc)&body=\(bodyEnc)") {
                            openURL(url)
                        }
                    } label: {
                        HStack {
                            Image(systemName: "envelope")
                                .foregroundStyle(.blue)
                            Text("Send Feedback")
                                .foregroundStyle(.primary)
                        }
                    }
                } header: {
                    Text("Feedback")
                } footer: {
                    Text("Report bugs or send corrections and suggestions about shiur text, summaries, quizzes, or resources.")
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
