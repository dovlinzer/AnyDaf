import SwiftUI

struct BookmarkListView: View {
    @ObservedObject var bookmarkManager: BookmarkManager
    @Environment(\.dismiss) private var dismiss

    /// Called when the user taps a bookmark to navigate to it. Nil in settings context.
    var onNavigate: ((Bookmark) -> Void)?

    @State private var searchText = ""
    @State private var editingBookmark: Bookmark?

    private var filteredBookmarks: [Bookmark] {
        if searchText.isEmpty { return bookmarkManager.bookmarks }
        return bookmarkManager.bookmarks.filter { $0.matches(searchText) }
    }

    var body: some View {
        NavigationStack {
            Group {
                if bookmarkManager.bookmarks.isEmpty {
                    ContentUnavailableView(
                        "No Bookmarks",
                        systemImage: "bookmark",
                        description: Text("Tap the bookmark icon to save a daf for later.")
                    )
                } else if filteredBookmarks.isEmpty {
                    ContentUnavailableView.search(text: searchText)
                } else {
                    List {
                        ForEach(filteredBookmarks) { bookmark in
                            Button {
                                if let onNavigate {
                                    onNavigate(bookmark)
                                    dismiss()
                                }
                            } label: {
                                BookmarkRow(bookmark: bookmark)
                            }
                            .swipeActions(edge: .trailing) {
                                Button(role: .destructive) {
                                    bookmarkManager.delete(bookmark)
                                } label: {
                                    Label("Delete", systemImage: "trash")
                                }
                                Button {
                                    editingBookmark = bookmark
                                } label: {
                                    Label("Edit", systemImage: "pencil")
                                }
                                .tint(.blue)
                            }
                        }
                    }
                }
            }
            .searchable(text: $searchText, prompt: "Search bookmarks")
            .navigationTitle("Bookmarks")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Done") { dismiss() }
                }
            }
            .sheet(item: $editingBookmark) { bookmark in
                BookmarkEditSheet(
                    bookmarkManager: bookmarkManager,
                    tractateIndex: bookmark.tractateIndex,
                    daf: bookmark.daf,
                    amud: bookmark.amud,
                    studySectionIndex: bookmark.studySectionIndex,
                    existingBookmark: bookmark
                )
            }
        }
    }
}

// MARK: - Row

private struct BookmarkRow: View {
    let bookmark: Bookmark

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(bookmark.name)
                .font(.headline)
                .foregroundStyle(.primary)
            Text(bookmark.subtitle)
                .font(.subheadline)
                .foregroundStyle(.secondary)
            if !bookmark.notes.isEmpty {
                Text(bookmark.notes)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .lineLimit(2)
            }
            Text(bookmark.createdAt, style: .relative)
                .font(.caption2)
                .foregroundStyle(.tertiary)
        }
        .padding(.vertical, 2)
    }
}
