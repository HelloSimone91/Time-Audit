import AppKit
import Foundation
import ScreenCaptureKit

struct PopupContext: Decodable {
    let activeApp: String
    let activeWindow: String
    let browserURL: String
    let timeoutSeconds: Int
    let activity: String
    let mood: String
    let energy: Int
    let kindness: Int
    let safety: Int
    let captureScreenshot: Bool
    let screenshotPath: String
}

struct PopupResult: Encodable {
    let outcome: String
    let activity: String?
    let mood: String?
    let energy: Int?
    let kindness: Int?
    let safety: Int?
    let notes: String?
    var screenshotPath: String? = nil
}

private func argument(after flag: String) -> String? {
    guard let index = CommandLine.arguments.firstIndex(of: flag),
          CommandLine.arguments.indices.contains(index + 1) else { return nil }
    return CommandLine.arguments[index + 1]
}

private final class AppDelegate: NSObject, NSApplicationDelegate, NSWindowDelegate {
    private let context: PopupContext
    private let outputURL: URL
    private var window: NSWindow!
    private var activityPopup: NSPopUpButton!
    private var moodPopup: NSPopUpButton!
    private var energySlider: NSSlider!
    private var kindnessSlider: NSSlider!
    private var safetySlider: NSSlider!
    private var energyValue: NSTextField!
    private var kindnessValue: NSTextField!
    private var safetyValue: NSTextField!
    private var notesView: NSTextView!
    private var countdownLabel: NSTextField!
    private var progress: NSProgressIndicator!
    private var timer: Timer?
    private var secondsRemaining: Int
    private var finished = false
    private var capturedScreenshotPath: String?

    private let activities = [
        "Work", "Admin / Logistics", "Learning", "Social", "Entertainment",
        "Health", "Eating", "Travel / Errands", "Household", "Dogs",
        "Scrolling", "Rest", "Other"
    ]
    private let moods = [
        "Energized", "Focused", "Content", "Neutral", "Tired", "Stressed",
        "Anxious", "Frustrated", "Other"
    ]

    init(context: PopupContext, outputURL: URL) {
        self.context = context
        self.outputURL = outputURL
        self.secondsRemaining = max(1, context.timeoutSeconds)
        super.init()
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.regular)
        captureScreenshotIfRequested()
        buildWindow()
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
        startCountdown()
    }

    private func captureScreenshotIfRequested() {
        guard context.captureScreenshot, !context.screenshotPath.isEmpty else { return }
        let allowed = CGPreflightScreenCaptureAccess() || CGRequestScreenCaptureAccess()
        guard allowed else { return }
        let semaphore = DispatchSemaphore(value: 0)
        var capturedImage: CGImage?
        let displayBounds = CGDisplayBounds(CGMainDisplayID())
        SCScreenshotManager.captureImage(in: displayBounds) { image, error in
            if let error { fputs("Screen capture failed: \(error)\n", stderr) }
            capturedImage = image
            semaphore.signal()
        }
        guard semaphore.wait(timeout: .now() + 15) == .success,
              let image = capturedImage else { return }
        let destination = URL(fileURLWithPath: context.screenshotPath)
        do {
            try FileManager.default.createDirectory(
                at: destination.deletingLastPathComponent(),
                withIntermediateDirectories: true
            )
            let representation = NSBitmapImageRep(cgImage: image)
            guard let png = representation.representation(using: .png, properties: [:]) else { return }
            try png.write(to: destination, options: .atomic)
            capturedScreenshotPath = destination.path
        } catch {
            fputs("Could not save screenshot: \(error)\n", stderr)
        }
    }

    private func label(_ text: String, size: CGFloat = 13, weight: NSFont.Weight = .regular) -> NSTextField {
        let field = NSTextField(labelWithString: text)
        field.font = NSFont.systemFont(ofSize: size, weight: weight)
        field.textColor = .labelColor
        field.lineBreakMode = .byWordWrapping
        field.maximumNumberOfLines = 0
        return field
    }

    private func buildWindow() {
        window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 520, height: 650),
            styleMask: [.titled, .closable, .miniaturizable],
            backing: .buffered,
            defer: false
        )
        window.title = "Time Audit"
        window.center()
        window.level = .floating
        window.isReleasedWhenClosed = false
        window.delegate = self

        let root = NSStackView()
        root.orientation = .vertical
        root.alignment = .leading
        root.spacing = 12
        root.edgeInsets = NSEdgeInsets(top: 22, left: 24, bottom: 20, right: 24)
        root.translatesAutoresizingMaskIntoConstraints = false
        window.contentView = root

        NSLayoutConstraint.activate([
            root.leadingAnchor.constraint(equalTo: window.contentView!.leadingAnchor),
            root.trailingAnchor.constraint(equalTo: window.contentView!.trailingAnchor),
            root.topAnchor.constraint(equalTo: window.contentView!.topAnchor),
            root.bottomAnchor.constraint(equalTo: window.contentView!.bottomAnchor)
        ])

        root.addArrangedSubview(label("Time Audit Check-In", size: 22, weight: .bold))

        var contextLines = ["Active app: \(context.activeApp.isEmpty ? "Unknown" : context.activeApp)"]
        if !context.activeWindow.isEmpty { contextLines.append("Window: \(context.activeWindow)") }
        if !context.browserURL.isEmpty { contextLines.append("URL: \(context.browserURL)") }
        let contextLabel = label(contextLines.joined(separator: "\n"), size: 12)
        contextLabel.textColor = .secondaryLabelColor
        contextLabel.toolTip = contextLines.joined(separator: "\n")
        contextLabel.widthAnchor.constraint(equalToConstant: 472).isActive = true
        root.addArrangedSubview(contextLabel)

        activityPopup = NSPopUpButton()
        activityPopup.addItems(withTitles: activities)
        activityPopup.selectItem(withTitle: activities.contains(context.activity) ? context.activity : "Work")
        root.addArrangedSubview(row(title: "Activity", control: activityPopup))

        moodPopup = NSPopUpButton()
        moodPopup.addItems(withTitles: moods)
        moodPopup.selectItem(withTitle: moods.contains(context.mood) ? context.mood : "Neutral")
        root.addArrangedSubview(row(title: "Mood", control: moodPopup))

        energySlider = makeSlider(value: context.energy)
        energySlider.identifier = NSUserInterfaceItemIdentifier("energy")
        energyValue = valueLabel(context.energy)
        root.addArrangedSubview(sliderRow(title: "Energy", slider: energySlider, value: energyValue))

        kindnessSlider = makeSlider(value: context.kindness)
        kindnessSlider.identifier = NSUserInterfaceItemIdentifier("kindness")
        kindnessValue = valueLabel(context.kindness)
        root.addArrangedSubview(sliderRow(title: "Kindness aligned", slider: kindnessSlider, value: kindnessValue))

        safetySlider = makeSlider(value: context.safety)
        safetySlider.identifier = NSUserInterfaceItemIdentifier("safety")
        safetyValue = valueLabel(context.safety)
        root.addArrangedSubview(sliderRow(title: "Safety aligned", slider: safetySlider, value: safetyValue))

        root.addArrangedSubview(label("Notes", size: 13, weight: .medium))
        let scroll = NSScrollView()
        scroll.hasVerticalScroller = true
        scroll.borderType = .bezelBorder
        notesView = NSTextView(frame: .zero)
        notesView.isRichText = false
        notesView.font = NSFont.systemFont(ofSize: 13)
        notesView.textContainerInset = NSSize(width: 6, height: 6)
        scroll.documentView = notesView
        scroll.heightAnchor.constraint(equalToConstant: 115).isActive = true
        scroll.widthAnchor.constraint(equalToConstant: 472).isActive = true
        root.addArrangedSubview(scroll)

        countdownLabel = label(countdownText(), size: 12)
        countdownLabel.textColor = .secondaryLabelColor
        root.addArrangedSubview(countdownLabel)

        progress = NSProgressIndicator()
        progress.isIndeterminate = false
        progress.minValue = 0
        progress.maxValue = Double(max(1, context.timeoutSeconds))
        progress.doubleValue = Double(secondsRemaining)
        progress.widthAnchor.constraint(equalToConstant: 472).isActive = true
        root.addArrangedSubview(progress)

        let buttons = NSStackView()
        buttons.orientation = .horizontal
        buttons.alignment = .centerY
        buttons.spacing = 10
        let spacer = NSView()
        spacer.setContentHuggingPriority(.defaultLow, for: .horizontal)
        buttons.addArrangedSubview(spacer)
        let skip = NSButton(title: "Skip", target: self, action: #selector(skipPressed))
        skip.keyEquivalent = "\u{1b}"
        buttons.addArrangedSubview(skip)
        let submit = NSButton(title: "Submit", target: self, action: #selector(submitPressed))
        submit.keyEquivalent = "\r"
        buttons.addArrangedSubview(submit)
        buttons.widthAnchor.constraint(equalToConstant: 472).isActive = true
        root.addArrangedSubview(buttons)
    }

    private func row(title: String, control: NSView) -> NSStackView {
        let row = NSStackView()
        row.orientation = .horizontal
        row.alignment = .centerY
        row.spacing = 12
        let titleLabel = label(title, size: 13, weight: .medium)
        titleLabel.widthAnchor.constraint(equalToConstant: 126).isActive = true
        control.widthAnchor.constraint(equalToConstant: 330).isActive = true
        row.addArrangedSubview(titleLabel)
        row.addArrangedSubview(control)
        return row
    }

    private func makeSlider(value: Int) -> NSSlider {
        let slider = NSSlider(
            value: Double(min(5, max(1, value))), minValue: 1, maxValue: 5,
            target: self, action: #selector(sliderChanged(_:))
        )
        slider.numberOfTickMarks = 5
        slider.allowsTickMarkValuesOnly = true
        slider.isContinuous = true
        return slider
    }

    private func valueLabel(_ value: Int) -> NSTextField {
        let field = label(String(min(5, max(1, value))), size: 13, weight: .semibold)
        field.alignment = .center
        field.widthAnchor.constraint(equalToConstant: 24).isActive = true
        return field
    }

    private func sliderRow(title: String, slider: NSSlider, value: NSTextField) -> NSStackView {
        let controls = NSStackView()
        controls.orientation = .horizontal
        controls.alignment = .centerY
        controls.spacing = 8
        slider.widthAnchor.constraint(equalToConstant: 295).isActive = true
        controls.addArrangedSubview(slider)
        controls.addArrangedSubview(value)
        return row(title: title, control: controls)
    }

    @objc private func sliderChanged(_ sender: NSSlider) {
        let value = String(sender.integerValue)
        switch sender.identifier?.rawValue {
        case "energy": energyValue.stringValue = value
        case "kindness": kindnessValue.stringValue = value
        case "safety": safetyValue.stringValue = value
        default: break
        }
    }

    @objc private func submitPressed() {
        finish(PopupResult(
            outcome: "submitted",
            activity: activityPopup.titleOfSelectedItem ?? "Other",
            mood: moodPopup.titleOfSelectedItem ?? "Neutral",
            energy: energySlider.integerValue,
            kindness: kindnessSlider.integerValue,
            safety: safetySlider.integerValue,
            notes: notesView.string.trimmingCharacters(in: .whitespacesAndNewlines)
        ))
    }

    @objc private func skipPressed() {
        finish(PopupResult(outcome: "skipped", activity: nil, mood: nil, energy: nil, kindness: nil, safety: nil, notes: nil))
    }

    func windowShouldClose(_ sender: NSWindow) -> Bool {
        skipPressed()
        return false
    }

    private func countdownText() -> String { "Auto-log as missed in \(secondsRemaining) seconds" }

    private func startCountdown() {
        timer = Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { [weak self] _ in
            guard let self else { return }
            self.secondsRemaining -= 1
            self.countdownLabel.stringValue = self.countdownText()
            self.progress.doubleValue = Double(max(0, self.secondsRemaining))
            if self.secondsRemaining <= 0 {
                self.finish(PopupResult(outcome: "timed_out", activity: nil, mood: nil, energy: nil, kindness: nil, safety: nil, notes: nil))
            }
        }
    }

    private func finish(_ result: PopupResult) {
        guard !finished else { return }
        finished = true
        timer?.invalidate()
        do {
            var completedResult = result
            completedResult.screenshotPath = capturedScreenshotPath
            let data = try JSONEncoder().encode(completedResult)
            try data.write(to: outputURL, options: .atomic)
        } catch {
            fputs("Could not write popup result: \(error)\n", stderr)
        }
        window.orderOut(nil)
        NSApp.terminate(nil)
    }
}

guard let contextPath = argument(after: "--context"),
      let outputPath = argument(after: "--output") else {
    fputs("usage: TimeAuditPopup --context <json> --output <json>\n", stderr)
    exit(2)
}

do {
    let contextData = try Data(contentsOf: URL(fileURLWithPath: contextPath))
    let context = try JSONDecoder().decode(PopupContext.self, from: contextData)
    let delegate = AppDelegate(context: context, outputURL: URL(fileURLWithPath: outputPath))
    let app = NSApplication.shared
    app.delegate = delegate
    app.run()
} catch {
    fputs("Time Audit popup failed: \(error)\n", stderr)
    exit(1)
}
