import Foundation

enum AuditActivity: String, CaseIterable, Identifiable {
    case work = "Work"
    case admin = "Admin / Logistics"
    case learning = "Learning"
    case social = "Social"
    case entertainment = "Entertainment"
    case health = "Health"
    case eating = "Eating"
    case travel = "Travel / Errands"
    case household = "Household"
    case dogs = "Dogs"
    case scrolling = "Scrolling"
    case rest = "Rest"
    case other = "Other"

    var id: String { rawValue }
}

enum AuditMood: String, CaseIterable, Identifiable {
    case energized = "Energized"
    case focused = "Focused"
    case content = "Content"
    case neutral = "Neutral"
    case tired = "Tired"
    case stressed = "Stressed"
    case anxious = "Anxious"
    case frustrated = "Frustrated"
    case other = "Other"

    var id: String { rawValue }
}

struct CheckInDraft {
    var activity: String
    var mood: String
    var energy: Int
    var kindness: Int
    var safety: Int
    var notes: String
    var screenshotData: Data?
}

struct SubmissionReceipt {
    let pageURL: URL
}

enum AlignmentKind {
    case kindness
    case safety

    func notionOption(for value: Int) -> String {
        switch value {
        case 1:
            return "1 Totally fucking up"
        case 5:
            return self == .kindness
                ? "5 Kind to self and surroundings"
                : "5 Safe to self and surroundings"
        default:
            return String(value)
        }
    }
}
