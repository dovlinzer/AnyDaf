import SwiftUI

struct BookmarkEditSheet: View {
    @ObservedObject var bookmarkManager: BookmarkManager
    @Environment(\.dismiss) private var dismiss

    let tractateIndex: Int
    let daf: Int
    let amud: Int
    let studySectionIndex: Int?
    let existingBookmark: Bookmark?

    @State private var name: String = ""
    @State private var notes: String = ""

    private var isEditing: Bool { existingBookmark != nil }

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    TextField("Name", text: $name)
                } header: {
                    Text("Bookmark Name")
                }

                Section {
                    TextField("Add notes...", text: $notes, axis: .vertical)
                        .lineLimit(4...8)
                } header: {
                    Text("Notes")
                }

                Section {
                    LabeledContent("Tractate", value: allTractates[tractateIndex].name)
                    LabeledContent("Daf", value: "\(daf)")
                    LabeledContent("Amud", value: amud == 0 ? "א (a)" : "ב (b)")
                    if let sectionIdx = studySectionIndex {
                        LabeledContent("Study Section", value: "\(sectionIdx + 1)")
                    }
                } header: {
                    Text("Location")
                }
            }
            .navigationTitle(isEditing ? "Edit Bookmark" : "New Bookmark")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") {
                        if var existing = existingBookmark {
                            existing.name = name
                            existing.notes = notes
                            bookmarkManager.update(existing)
                        } else {
                            let bookmark = Bookmark(
                                id: UUID(),
                                name: name,
                                notes: notes,
                                tractateIndex: tractateIndex,
                                daf: daf,
                                amud: amud,
                                studySectionIndex: studySectionIndex,
                                createdAt: Date()
                            )
                            bookmarkManager.add(bookmark)
                        }
                        dismiss()
                    }
                    .disabled(name.trimmingCharacters(in: .whitespaces).isEmpty)
                }
            }
            .onAppear {
                if let existing = existingBookmark {
                    name = existing.name
                    notes = existing.notes
                } else {
                    name = Bookmark.defaultName(tractateIndex: tractateIndex, daf: daf, amud: amud)
                }
            }
        }
    }
}
