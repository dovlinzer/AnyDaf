import Foundation

struct Dedication: Identifiable {
    var id: String { "\(date.timeIntervalSince1970)-\(period)-\(dedicatedBy)" }
    let date: Date
    let endDate: Date         // inclusive; equals `date` for a single-day dedication
    let dedicatedBy: String
    let honoreeName: String   // may be empty
    let period: String        // "today" | "week" | "month" — display wording only, see below
    let preposition: String   // "in honor of" | "in memory of" | "on the occasion of" | ""
    let occasion: String      // supplemental text, may be empty
    let displayText: String?  // full override
    let photoURL: String?     // optional photo URL

    var periodTitle: String {
        switch period {
        case "week":  return "This Week's Learning"
        case "month": return "This Month's Learning"
        default:      return "Today's Learning"
        }
    }

    var formattedMessage: String {
        if let override = displayText, !override.isEmpty { return override }
        let periodPhrase: String
        switch period {
        case "week":  periodPhrase = "This week's learning"
        case "month": periodPhrase = "This month's learning"
        default:      periodPhrase = "Today's learning"
        }
        var parts = ["\(periodPhrase) with AnyDaf is dedicated by \(dedicatedBy)"]
        if !preposition.isEmpty  { parts.append(preposition) }
        if !honoreeName.isEmpty  { parts.append(honoreeName) }
        if !occasion.isEmpty     { parts.append(occasion) }
        return parts.joined(separator: " ") + "."
    }
}

enum DedicationService {
    private static let supabaseURL = "https://zewdazoijdpakugfvnzt.supabase.co"

    // Fetches the most relevant active dedication. "Active" means today falls in
    // [date, endDate], checked server-side by the query below. When more than one
    // dedication is active at once (an admin-acknowledged overlap — see
    // dedication-form.html's approval-time warning), picks by `period`'s display tier
    // (today > week > month), then most-recently-created.
    // Returns nil if nothing is active — caller should NOT mark the date as shown.
    static func fetch() async -> Dedication? {
        let todayStr = todayDateString()

        let urlStr = "\(supabaseURL)/rest/v1/dedications"
            + "?date=lte.\(todayStr)"
            + "&end_date=gte.\(todayStr)"
            + "&status=eq.approved"
            + "&for_anydaf=eq.true"
            + "&select=date,end_date,dedicated_by,honoree_name,period,preposition,occasion,display_text,photo_url"
            + "&order=date.desc,id.desc"
            + "&limit=10"
        guard let url = URL(string: urlStr) else { return nil }
        var request = URLRequest(url: url)
        request.setValue(Secrets.supabaseAnonKey, forHTTPHeaderField: "apikey")
        request.setValue("Bearer \(Secrets.supabaseAnonKey)", forHTTPHeaderField: "Authorization")

        guard let (data, response) = try? await URLSession.shared.data(for: request),
              (response as? HTTPURLResponse)?.statusCode == 200,
              let rows = try? JSONSerialization.jsonObject(with: data) as? [[String: Any]]
        else { return nil }

        return rows
            .compactMap { decode($0) }
            .sorted { periodPriority($0.period) > periodPriority($1.period) }
            .first
    }

    private static func decode(_ row: [String: Any]) -> Dedication? {
        guard let dateStr = row["date"] as? String,
              let date = parseDate(dateStr),
              let dedicatedBy = row["dedicated_by"] as? String,
              !dedicatedBy.isEmpty
        else { return nil }
        let endDate = (row["end_date"] as? String).flatMap(parseDate) ?? date
        return Dedication(
            date: date,
            endDate: endDate,
            dedicatedBy: dedicatedBy,
            honoreeName: (row["honoree_name"] as? String) ?? "",
            period:      (row["period"] as? String) ?? "today",
            preposition: (row["preposition"] as? String) ?? "",
            occasion:    (row["occasion"] as? String) ?? "",
            displayText: (row["display_text"] as? String).flatMap { $0.isEmpty ? nil : $0 },
            photoURL:    (row["photo_url"] as? String).flatMap { $0.isEmpty ? nil : $0 }
        )
    }

    private static func periodPriority(_ period: String) -> Int {
        switch period {
        case "today": return 3
        case "week":  return 2
        default:      return 1
        }
    }

    private static func parseDate(_ str: String) -> Date? {
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd"
        f.locale = Locale(identifier: "en_US_POSIX")
        return f.date(from: str)
    }

    static func formatDate(_ date: Date) -> String {
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd"
        f.locale = Locale(identifier: "en_US_POSIX")
        return f.string(from: date)
    }

    static func todayDateString() -> String { formatDate(Date()) }
}
