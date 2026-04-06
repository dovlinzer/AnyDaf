import SwiftUI

/// Loads an image from a URL using AsyncImage and supports pinch-to-zoom,
/// double-tap to zoom in/out, and horizontal swipe to navigate pages.
/// Swipe gestures only fire when the image is at 1× scale (not panned/zoomed).
/// Pan is clamped so the image cannot be dragged completely off-screen.
struct ZoomableAsyncImage: View {
    let url: URL?
    var onSwipeLeft:  (() -> Void)? = nil   // swipe left  → advance one amud
    var onSwipeRight: (() -> Void)? = nil   // swipe right → go back one amud

    @State private var scale: CGFloat = 1.0
    @State private var lastScale: CGFloat = 1.0
    @State private var offset: CGSize = .zero
    @State private var lastOffset: CGSize = .zero
    @State private var viewSize: CGSize = .zero

    var body: some View {
        GeometryReader { geo in
            AsyncImage(url: url) { phase in
                switch phase {
                case .success(let image):
                    image
                        .resizable()
                        .aspectRatio(contentMode: .fit)
                        .scaleEffect(scale)
                        .offset(offset)
                        // Frame is set BEFORE gestures so SwiftUI's hit testing is
                        // bounded by the frame rectangle, not the visually-scaled area.
                        // This prevents the zoomed image from stealing touches that
                        // belong to the tractate/daf pickers above.
                        .frame(width: geo.size.width, height: geo.size.height)
                        .contentShape(Rectangle())
                        .gesture(
                            SimultaneousGesture(
                                MagnificationGesture()
                                    .onChanged { value in
                                        scale = max(1.0, lastScale * value)
                                    }
                                    .onEnded { _ in
                                        scale = max(1.0, min(scale, 6.0))
                                        lastScale = scale
                                        if scale == 1.0 {
                                            withAnimation(.spring()) { offset = .zero }
                                            lastOffset = .zero
                                        } else {
                                            // Re-clamp after scale settles
                                            let clamped = clampedOffset(offset, in: geo.size)
                                            withAnimation(.spring()) { offset = clamped }
                                            lastOffset = clamped
                                        }
                                    },
                                DragGesture(minimumDistance: 20)
                                    .onChanged { value in
                                        guard scale > 1.0 else { return }
                                        let proposed = CGSize(
                                            width:  lastOffset.width  + value.translation.width,
                                            height: lastOffset.height + value.translation.height
                                        )
                                        offset = clampedOffset(proposed, in: geo.size)
                                    }
                                    .onEnded { value in
                                        if scale > 1.0 {
                                            lastOffset = offset
                                        } else {
                                            // At 1× scale: detect a horizontal swipe
                                            let dx = value.translation.width
                                            let dy = value.translation.height
                                            if abs(dx) > 60 && abs(dx) > abs(dy) {
                                                if dx < 0 { onSwipeLeft?() }
                                                else       { onSwipeRight?() }
                                            }
                                        }
                                    }
                            )
                        )
                        .onTapGesture(count: 2) {
                            withAnimation(.spring()) {
                                if scale > 1.0 {
                                    scale = 1.0
                                    lastScale = 1.0
                                    offset = .zero
                                    lastOffset = .zero
                                } else {
                                    scale = 3.0
                                    lastScale = 3.0
                                }
                            }
                        }

                case .failure:
                    VStack(spacing: 8) {
                        Image(systemName: "photo.slash")
                            .font(.largeTitle)
                            .foregroundStyle(.secondary)
                        Text("Image unavailable")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                    .frame(maxWidth: .infinity, maxHeight: .infinity)

                default:
                    VStack(spacing: 8) {
                        ProgressView()
                        Text("Loading page…")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                }
            }
        }
        .onChange(of: url) { _, _ in
            scale = 1.0
            lastScale = 1.0
            offset = .zero
            lastOffset = .zero
        }
    }

    /// Clamps `proposed` so the image edge cannot travel past the view's center.
    /// At scale `s`, the maximum pan in each axis is `viewDimension * (s - 1) / 2`.
    private func clampedOffset(_ proposed: CGSize, in size: CGSize) -> CGSize {
        let maxX = size.width  * (scale - 1) / 2
        let maxY = size.height * (scale - 1) / 2
        return CGSize(
            width:  max(-maxX, min(maxX, proposed.width)),
            height: max(-maxY, min(maxY, proposed.height))
        )
    }
}
