import Foundation

struct Bookmark: Codable, Identifiable {
    let id: UUID
    var name: String
    var notes: String
    let tractateIndex: Int
    let daf: Int
    let amud: Int                   // 0 = amud a, 1 = amud b
    let studySectionIndex: Int?     // nil if bookmarked from main view
    let createdAt: Date

    var tractate: Tractate { allTractates[tractateIndex] }
    var amudLabel: String { amud == 0 ? "a" : "b" }
    var subtitle: String { "\(tractate.name) Daf \(daf)\(amudLabel)" }

    static func defaultName(tractateIndex: Int, daf: Int, amud: Int) -> String {
        "\(allTractates[tractateIndex].name) \(daf)\(amud == 0 ? "a" : "b")"
    }

    /// Returns true if this bookmark's name or notes contain the query (case-insensitive).
    func matches(_ query: String) -> Bool {
        let q = query.lowercased()
        return name.lowercased().contains(q) || notes.lowercased().contains(q)
    }
}
