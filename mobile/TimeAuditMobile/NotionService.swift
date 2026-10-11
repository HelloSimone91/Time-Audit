import Foundation
import UIKit

actor NotionService {
    static let dataSourceID = "37906423-ccc1-80b9-96b7-000b196f9131"
    static let notionVersion = "2026-03-11"

    private let token: String
    private let session: URLSession

    init(token: String, session: URLSession = .shared) {
        let trimmed = token.trimmingCharacters(in: .whitespacesAndNewlines)
        self.token = trimmed.lowercased().hasPrefix("bearer ")
            ? String(trimmed.dropFirst(7))
            : trimmed
        self.session = session
    }

    func submit(_ draft: CheckInDraft) async throws -> SubmissionReceipt {
        let screenshotUpload = try await draft.screenshotData.map(uploadScreenshot)
        let now = Date()
        let localFormatter = DateFormatter()
        localFormatter.dateFormat = "yyyy-MM-dd HH:mm"
        let interval = Int(now.timeIntervalSince1970 / (30 * 60))

        let rawContext: [String: Any] = [
            "entry_type": "Mobile Check-In",
            "device": UIDevice.current.name,
            "system": "iOS \(UIDevice.current.systemVersion)",
            "interval_key": "time-audit-mobile-v1-\(interval)",
            "screenshot_attached": screenshotUpload != nil,
            "app_window_browser_context": "Unavailable on iOS by design",
        ]
        let rawData = try JSONSerialization.data(withJSONObject: rawContext, options: [.prettyPrinted, .sortedKeys])
        let rawText = String(data: rawData, encoding: .utf8) ?? ""

        var properties: [String: Any] = [
            "Name": ["title": [["text": ["content": "Mobile audit \(localFormatter.string(from: now))"]]]],
            "Timestamp": ["date": ["start": ISO8601DateFormatter().string(from: now)]],
            "Participated": ["checkbox": true],
            "Activity": ["multi_select": [["name": draft.activity]]],
            "Mood": ["multi_select": [["name": draft.mood]]],
            "Energy": ["number": draft.energy],
            "Kindness Aligned": ["select": ["name": AlignmentKind.kindness.notionOption(for: draft.kindness)]],
            "Safety Aligned": ["select": ["name": AlignmentKind.safety.notionOption(for: draft.safety)]],
            "Notes": Self.richText(draft.notes),
            "Device": Self.richText("\(UIDevice.current.name) (iOS)"),
            "Interval Key": Self.richText("time-audit-mobile-v1-\(interval)"),
            "Entry Type": ["select": ["name": "Mobile Check-In"]],
            "Raw Context": Self.richText(rawText),
        ]
        if let screenshotUpload {
            properties["Screenshot"] = ["files": [screenshotUpload]]
        }

        let response = try await sendJSON(
            path: "pages",
            body: [
                "parent": ["type": "data_source_id", "data_source_id": Self.dataSourceID],
                "properties": properties,
            ]
        )
        guard let urlString = response["url"] as? String, let url = URL(string: urlString) else {
            throw NotionError.invalidResponse("Notion created the page but did not return its URL.")
        }
        return SubmissionReceipt(pageURL: url)
    }

    private func uploadScreenshot(_ data: Data) async throws -> [String: Any] {
        let upload = try await sendJSON(path: "file_uploads", body: [:])
        guard let uploadID = upload["id"] as? String else {
            throw NotionError.invalidResponse("Notion did not return a screenshot upload ID.")
        }

        let boundary = "time-audit-\(UUID().uuidString)"
        var body = Data()
        body.appendUTF8("--\(boundary)\r\n")
        body.appendUTF8("Content-Disposition: form-data; name=\"file\"; filename=\"mobile-time-audit.png\"\r\n")
        body.appendUTF8("Content-Type: image/png\r\n\r\n")
        body.append(data)
        body.appendUTF8("\r\n--\(boundary)--\r\n")

        var request = baseRequest(path: "file_uploads/\(uploadID)/send")
        request.httpMethod = "POST"
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        request.httpBody = body
        let response = try await perform(request)
        guard response["status"] as? String == "uploaded" else {
            throw NotionError.invalidResponse("Notion did not finish the screenshot upload.")
        }
        return [
            "name": "mobile-time-audit.png",
            "type": "file_upload",
            "file_upload": ["id": uploadID],
        ]
    }

    private static func richText(_ value: String) -> [String: Any] {
        ["rich_text": [["text": ["content": String(value.prefix(2000))]]]]
    }

    private func sendJSON(path: String, body: [String: Any]) async throws -> [String: Any] {
        var request = baseRequest(path: path)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        return try await perform(request)
    }

    private func baseRequest(path: String) -> URLRequest {
        var request = URLRequest(url: URL(string: "https://api.notion.com/v1/\(path)")!)
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        request.setValue(Self.notionVersion, forHTTPHeaderField: "Notion-Version")
        return request
    }

    private func perform(_ request: URLRequest) async throws -> [String: Any] {
        guard !token.isEmpty else { throw NotionError.missingToken }
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw NotionError.invalidResponse("Notion returned a non-HTTP response.")
        }
        guard (200..<300).contains(http.statusCode) else {
            let message = String(data: data, encoding: .utf8) ?? "Unknown error"
            throw NotionError.http(http.statusCode, message)
        }
        guard let object = try JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            throw NotionError.invalidResponse("Notion returned unreadable JSON.")
        }
        return object
    }
}

enum NotionError: LocalizedError {
    case missingToken
    case http(Int, String)
    case invalidResponse(String)

    var errorDescription: String? {
        switch self {
        case .missingToken:
            "Add your Notion token in Settings first."
        case .http(let code, let message):
            "Notion error \(code): \(message)"
        case .invalidResponse(let message):
            message
        }
    }
}

private extension Data {
    mutating func appendUTF8(_ string: String) {
        append(Data(string.utf8))
    }
}
