import SwiftUI
import PDFKit

// MARK: - PDF Daf Page View

/// Displays a tractate PDF page using PDFKit.
/// When the PDF is not yet cached locally it shows a download prompt.
/// After downloading, it opens the PDF and jumps to the correct page
/// based on the selected daf and amud.
struct PDFDafPageView: View {
    let tractate: Tractate
    @Binding var daf: Int
    @Binding var selectedSide: Int          // 0 = amud aleph (a), 1 = amud bet (b)

    @ObservedObject private var pdfManager = PDFPageManager.shared
    @State private var pdfDocument: PDFDocument?

    var body: some View {
        VStack(spacing: 0) {
            amudPicker

            Group {
                if let doc = pdfDocument {
                    let pageIndex = pdfManager.pdfPage(
                        daf: daf, amud: selectedSide, tractate: tractate.name) - 1
                    PDFKitView(
                        document: doc,
                        pageIndex: max(0, pageIndex),
                        onSwipeLeft:  advanceAmud,
                        onSwipeRight: retreatAmud
                    )
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .padding(.horizontal, 12)
                    .padding(.bottom, 8)
                } else if pdfManager.isDownloading {
                    downloadingView
                } else if let error = pdfManager.downloadError {
                    errorView(message: error)
                } else {
                    downloadPromptView
                }
            }
        }
        .task { loadDocument() }
        .onChange(of: tractate.name) { _, _ in
            pdfDocument = nil
            pdfManager.clearError()
            loadDocument()
        }
    }

    // MARK: - Amud picker

    private var amudPicker: some View {
        Picker("Amud", selection: $selectedSide) {
            Text("Amud א (a)").tag(0)
            Text("Amud ב (b)").tag(1)
        }
        .pickerStyle(.segmented)
        .padding(.horizontal, 28)
        .padding(.vertical, 6)
        .background(
            RoundedRectangle(cornerRadius: 12)
                .fill(Color.white)
                .shadow(color: .black.opacity(0.3), radius: 5, x: 0, y: 2)
        )
        .padding(.horizontal, 20)
        .padding(.top, 8)
        .padding(.bottom, 8)
    }

    // MARK: - State views

    private var downloadPromptView: some View {
        VStack(spacing: 20) {
            Spacer()
            Image(systemName: "arrow.down.doc")
                .font(.system(size: 50))
                .foregroundStyle(.white.opacity(0.5))
            Text("\(tractate.name) PDF")
                .font(.title3.bold())
                .foregroundStyle(.white)
            Text("Download the full tractate once for instant, offline page navigation.")
                .font(.subheadline)
                .foregroundStyle(.white.opacity(0.6))
                .multilineTextAlignment(.center)
                .padding(.horizontal, 32)
            Button("Download PDF") {
                Task {
                    await pdfManager.download(tractate: tractate.name)
                    loadDocument()
                }
            }
            .buttonStyle(.borderedProminent)
            Spacer()
        }
    }

    private var downloadingView: some View {
        VStack(spacing: 16) {
            Spacer()
            ProgressView()
                .tint(.white)
                .scaleEffect(1.4)
            Text("Downloading \(tractate.name)…")
                .font(.headline)
                .foregroundStyle(.white)
            Text("Large file — this may take a minute")
                .font(.caption)
                .foregroundStyle(.white.opacity(0.5))
            Spacer()
        }
    }

    private func errorView(message: String) -> some View {
        VStack(spacing: 16) {
            Spacer()
            Image(systemName: "exclamationmark.triangle")
                .font(.largeTitle)
                .foregroundStyle(.yellow)
            Text(message)
                .foregroundStyle(.white.opacity(0.8))
                .multilineTextAlignment(.center)
                .padding(.horizontal)
            Button("Try Again") {
                pdfManager.clearError()
                Task {
                    await pdfManager.download(tractate: tractate.name)
                    loadDocument()
                }
            }
            .buttonStyle(.borderedProminent)
            Spacer()
        }
    }

    // MARK: - Helpers

    private func loadDocument() {
        guard pdfManager.isCached(tractate.name) else { return }
        pdfDocument = PDFDocument(url: pdfManager.localURL(for: tractate.name))
    }

    private func advanceAmud() {
        if selectedSide == 0 {
            selectedSide = 1
        } else if daf < tractate.endDaf {
            daf += 1
            selectedSide = 0
        }
    }

    private func retreatAmud() {
        if selectedSide == 1 {
            selectedSide = 0
        } else if daf > tractate.startDaf {
            daf -= 1
            selectedSide = 1
        }
    }
}

// MARK: - PDFKit UIViewRepresentable

/// Wraps a PDFView in SwiftUI.
/// Displays a single page at a time and delegates left/right swipe to the parent.
struct PDFKitView: UIViewRepresentable {
    let document: PDFDocument
    let pageIndex: Int      // 0-based
    var onSwipeLeft:  () -> Void
    var onSwipeRight: () -> Void

    func makeUIView(context: Context) -> PDFView {
        let pdfView = PDFView()
        pdfView.displayMode      = .singlePage
        pdfView.displayDirection = .horizontal
        pdfView.autoScales       = true
        // Match the app's dark background
        pdfView.backgroundColor  = UIColor(
            red: 0.106, green: 0.227, blue: 0.541, alpha: 1)

        // Swipe gesture recognizers (separate from PDFView's internal pan/zoom)
        let leftSwipe = UISwipeGestureRecognizer(
            target: context.coordinator, action: #selector(Coordinator.handleLeft))
        leftSwipe.direction = .left
        pdfView.addGestureRecognizer(leftSwipe)

        let rightSwipe = UISwipeGestureRecognizer(
            target: context.coordinator, action: #selector(Coordinator.handleRight))
        rightSwipe.direction = .right
        pdfView.addGestureRecognizer(rightSwipe)

        return pdfView
    }

    func updateUIView(_ pdfView: PDFView, context: Context) {
        // Update callbacks so coordinator always holds the latest closures
        context.coordinator.onSwipeLeft  = onSwipeLeft
        context.coordinator.onSwipeRight = onSwipeRight

        // Replace document only if it changed (avoids jarring reloads)
        if pdfView.document !== document {
            pdfView.document = document
        }

        // Jump to the correct page when daf/amud changes
        if let targetPage = document.page(at: pageIndex),
           pdfView.currentPage !== targetPage {
            pdfView.go(to: targetPage)
        }
    }

    func makeCoordinator() -> Coordinator { Coordinator() }

    final class Coordinator: NSObject {
        var onSwipeLeft:  () -> Void = {}
        var onSwipeRight: () -> Void = {}

        @objc func handleLeft()  { onSwipeLeft() }
        @objc func handleRight() { onSwipeRight() }
    }
}
