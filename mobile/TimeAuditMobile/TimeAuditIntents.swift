import AppIntents
import UniformTypeIdentifiers

struct OpenTimeAuditIntent: AppIntent {
    static let title: LocalizedStringResource = "Open Time Audit"
    static let description = IntentDescription("Open the Time Audit check-in form.")
    static let openAppWhenRun = true

    func perform() async throws -> some IntentResult {
        .result()
    }
}

struct StartTimeAuditWithScreenshotIntent: AppIntent {
    static let title: LocalizedStringResource = "Start Time Audit with Screenshot"
    static let description = IntentDescription("Open a Time Audit check-in with a screenshot supplied by Shortcuts.")
    static let openAppWhenRun = true

    @Parameter(
        title: "Screenshot",
        supportedContentTypes: [.image],
        inputConnectionBehavior: .connectToPreviousIntentResult
    )
    var screenshot: IntentFile

    func perform() async throws -> some IntentResult {
        let data = try await screenshot.data(contentType: .image)
        try PendingScreenshotStore.save(data)
        return .result()
    }
}

struct TimeAuditShortcuts: AppShortcutsProvider {
    static var appShortcuts: [AppShortcut] {
        AppShortcut(
            intent: OpenTimeAuditIntent(),
            phrases: [
                "Open \(.applicationName)",
                "Log my time with \(.applicationName)",
            ],
            shortTitle: "Open Time Audit",
            systemImageName: "clock.badge.checkmark"
        )
        AppShortcut(
            intent: StartTimeAuditWithScreenshotIntent(),
            phrases: ["Start \(.applicationName) with a screenshot"],
            shortTitle: "Audit with Screenshot",
            systemImageName: "camera.viewfinder"
        )
    }
}
