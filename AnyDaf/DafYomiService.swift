import Foundation

/// Fetches today's Daf Yomi from the Sefaria Calendars API
/// and maps it to AnyDaf's canonical tractate names.
@MainActor
struct DafYomiService {

    /// Sefaria tractate name → AnyDaf canonical name (only entries that differ).
    private static let sefariaToAnyDaf: [String: String] = [
        "Eruvin":  "Eiruvin",
        "Taanit":  "Ta\u{2019}anit",
        "Chullin": "Hullin",
        "Middot":  "Middos",
    ]

    struct DafYomi {
        let tractateName: String   // AnyDaf canonical name
        let tractateIndex: Int     // index into allTractates
        let daf: Int
    }

    enum DafYomiError: LocalizedError {
        case networkError(Error)
        case notFound
        case parseError
        case unknownTractate(String)

        var errorDescription: String? {
            switch self {
            case .networkError(let e):       return "Network error: \(e.localizedDescription)"
            case .notFound:                  return "Daf Yomi not found in calendar"
            case .parseError:                return "Could not parse Daf Yomi data"
            case .unknownTractate(let name): return "Unknown tractate: \(name)"
            }
        }
    }

    /// Fetches today's Daf Yomi from Sefaria and returns the matching AnyDaf tractate + daf.
    static func fetchToday() async throws -> DafYomi {
        let url = URL(string: "https://www.sefaria.org/api/calendars")!

        let (data, _): (Data, URLResponse)
        do {
            (data, _) = try await URLSession.shared.data(from: url)
        } catch {
            throw DafYomiError.networkError(error)
        }

        guard let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let items = json["calendar_items"] as? [[String: Any]]
        else {
            throw DafYomiError.parseError
        }

        // Find the Daf Yomi entry
        guard let dafYomiItem = items.first(where: { item in
            guard let title = item["title"] as? [String: Any],
                  let en = title["en"] as? String
            else { return false }
            return en == "Daf Yomi"
        }) else {
            throw DafYomiError.notFound
        }

        // Parse tractate + daf from displayValue, e.g. "Menachot 60"
        guard let displayValue = dafYomiItem["displayValue"] as? [String: Any],
              let displayEn = displayValue["en"] as? String
        else {
            throw DafYomiError.parseError
        }

        let parts = displayEn.components(separatedBy: " ")
        guard parts.count >= 2,
              let dafNum = Int(parts.last!)
        else {
            throw DafYomiError.parseError
        }

        let sefariaName = parts.dropLast().joined(separator: " ")
        let anyDafName = sefariaToAnyDaf[sefariaName] ?? sefariaName

        guard let index = allTractates.firstIndex(where: { $0.name == anyDafName }) else {
            throw DafYomiError.unknownTractate(anyDafName)
        }

        return DafYomi(tractateName: anyDafName, tractateIndex: index, daf: dafNum)
    }
}
