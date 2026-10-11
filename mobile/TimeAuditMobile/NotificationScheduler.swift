import Foundation
import UserNotifications

enum NotificationScheduler {
    static let requestID = "time-audit-30-minute-check-in"

    static func enable() async throws {
        let center = UNUserNotificationCenter.current()
        let granted = try await center.requestAuthorization(options: [.alert, .sound, .badge])
        guard granted else { throw NotificationError.permissionDenied }

        center.removePendingNotificationRequests(withIdentifiers: [requestID])
        let content = UNMutableNotificationContent()
        content.title = "Time Audit check-in"
        content.body = "What are you doing, and how does it feel?"
        content.sound = .default
        let trigger = UNTimeIntervalNotificationTrigger(timeInterval: 30 * 60, repeats: true)
        try await center.add(UNNotificationRequest(identifier: requestID, content: content, trigger: trigger))
        UserDefaults.standard.set(true, forKey: "remindersEnabled")
    }

    static func disable() {
        UNUserNotificationCenter.current().removePendingNotificationRequests(withIdentifiers: [requestID])
        UserDefaults.standard.set(false, forKey: "remindersEnabled")
    }
}

enum NotificationError: LocalizedError {
    case permissionDenied

    var errorDescription: String? {
        "Notifications are off for Time Audit. Enable them in iPhone Settings to receive check-ins."
    }
}
