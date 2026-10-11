import PhotosUI
import SwiftUI
import UIKit

struct CheckInView: View {
    @AppStorage("lastActivity") private var activity = AuditActivity.work.rawValue
    @AppStorage("lastMood") private var mood = AuditMood.neutral.rawValue
    @AppStorage("lastEnergy") private var energy = 3.0
    @AppStorage("lastKindness") private var kindness = 3.0
    @AppStorage("lastSafety") private var safety = 3.0
    @AppStorage("remindersEnabled") private var remindersEnabled = false

    @State private var notes = ""
    @State private var selectedPhoto: PhotosPickerItem?
    @State private var screenshotData: Data?
    @State private var isSubmitting = false
    @State private var settingsPresented = false
    @State private var message: StatusMessage?

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    Picker("Activity", selection: $activity) {
                        ForEach(AuditActivity.allCases) { option in
                            Text(option.rawValue).tag(option.rawValue)
                        }
                    }
                    Picker("Mood", selection: $mood) {
                        ForEach(AuditMood.allCases) { option in
                            Text(option.rawValue).tag(option.rawValue)
                        }
                    }
                } header: {
                    Text("Right now")
                }

                Section("Alignment") {
                    scoreRow("Energy", value: $energy)
                    scoreRow("Kindness aligned", value: $kindness)
                    scoreRow("Safety aligned", value: $safety)
                }

                Section("Notes") {
                    TextField("What’s happening?", text: $notes, axis: .vertical)
                        .lineLimit(3...7)
                }

                Section("Screenshot") {
                    PhotosPicker(selection: $selectedPhoto, matching: .images) {
                        Label(screenshotData == nil ? "Choose screenshot" : "Replace screenshot", systemImage: "photo")
                    }
                    if let screenshotData, let image = UIImage(data: screenshotData) {
                        Image(uiImage: image)
                            .resizable()
                            .scaledToFit()
                            .frame(maxHeight: 220)
                            .clipShape(RoundedRectangle(cornerRadius: 12))
                            .accessibilityLabel("Selected Time Audit screenshot")
                        Button("Remove screenshot", role: .destructive) {
                            self.screenshotData = nil
                            selectedPhoto = nil
                        }
                    } else {
                        Text("Optional. You can also connect Take Screenshot to Start Time Audit with Screenshot in Shortcuts.")
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                    }
                }

                Section {
                    Button {
                        Task { await submit() }
                    } label: {
                        HStack {
                            Spacer()
                            if isSubmitting { ProgressView().padding(.trailing, 6) }
                            Text(isSubmitting ? "Saving…" : "Save to Notion")
                            Spacer()
                        }
                    }
                    .disabled(isSubmitting)
                }

                if let message {
                    Section {
                        VStack(alignment: .leading, spacing: 8) {
                            Label(message.title, systemImage: message.isError ? "exclamationmark.triangle" : "checkmark.circle.fill")
                                .foregroundStyle(message.isError ? .red : .green)
                            Text(message.detail).font(.footnote)
                            if let url = message.url {
                                Link("Open Notion entry", destination: url)
                            }
                        }
                    }
                }
            }
            .navigationTitle("Time Audit")
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button { settingsPresented = true } label: {
                        Label("Settings", systemImage: "gearshape")
                    }
                }
            }
            .sheet(isPresented: $settingsPresented) { SettingsView() }
            .task(id: selectedPhoto) { await loadSelectedPhoto() }
            .task {
                if let pending = PendingScreenshotStore.consume(),
                   let png = UIImage(data: pending)?.pngData() {
                    screenshotData = png
                }
            }
        }
    }

    private func scoreRow(_ title: String, value: Binding<Double>) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text(title)
                Spacer()
                Text("\(Int(value.wrappedValue))").monospacedDigit().foregroundStyle(.secondary)
            }
            Slider(value: value, in: 1...5, step: 1)
                .accessibilityLabel(title)
                .accessibilityValue("\(Int(value.wrappedValue)) out of 5")
        }
    }

    @MainActor
    private func loadSelectedPhoto() async {
        guard let selectedPhoto else { return }
        do {
            guard let data = try await selectedPhoto.loadTransferable(type: Data.self),
                  let png = UIImage(data: data)?.pngData() else {
                throw PhotoError.unreadable
            }
            screenshotData = png
        } catch {
            message = StatusMessage(error: error.localizedDescription)
        }
    }

    @MainActor
    private func submit() async {
        guard let token = KeychainStore.loadToken(), !token.isEmpty else {
            settingsPresented = true
            message = StatusMessage(error: "Add your Notion integration token in Settings first.")
            return
        }
        isSubmitting = true
        defer { isSubmitting = false }
        do {
            let draft = CheckInDraft(
                activity: activity,
                mood: mood,
                energy: Int(energy),
                kindness: Int(kindness),
                safety: Int(safety),
                notes: notes.trimmingCharacters(in: .whitespacesAndNewlines),
                screenshotData: screenshotData
            )
            let receipt = try await NotionService(token: token).submit(draft)
            if remindersEnabled { try? await NotificationScheduler.enable() }
            message = StatusMessage(success: receipt.pageURL)
            notes = ""
            screenshotData = nil
            selectedPhoto = nil
        } catch {
            message = StatusMessage(error: error.localizedDescription)
        }
    }
}

private struct StatusMessage: Identifiable {
    let id = UUID()
    let title: String
    let detail: String
    let url: URL?
    let isError: Bool

    init(success url: URL) {
        title = "Saved to Notion"
        detail = "Your mobile Time Audit check-in is complete."
        self.url = url
        isError = false
    }

    init(error: String) {
        title = "Couldn’t save"
        detail = error
        url = nil
        isError = true
    }
}

private enum PhotoError: LocalizedError {
    case unreadable
    var errorDescription: String? { "That image could not be loaded. Try another screenshot." }
}
