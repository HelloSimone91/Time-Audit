import SwiftUI

struct SettingsView: View {
    @Environment(\.dismiss) private var dismiss
    @AppStorage("remindersEnabled") private var remindersEnabled = false
    @State private var token = ""
    @State private var isSaving = false
    @State private var errorMessage: String?

    var body: some View {
        NavigationStack {
            Form {
                Section("Notion") {
                    SecureField("Integration token", text: $token)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                    Text("Paste the token itself—do not include the word Bearer. It stays in this iPhone’s Keychain.")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }

                Section("Check-in reminders") {
                    Toggle("Every 30 minutes", isOn: $remindersEnabled)
                    Text("iOS displays a notification. Tap it to open the form; iOS does not allow silent background screenshots of other apps.")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }

                if let errorMessage {
                    Section {
                        Text(errorMessage).foregroundStyle(.red)
                    }
                }
            }
            .navigationTitle("Time Audit Settings")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") { Task { await save() } }
                        .disabled(isSaving || token.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                }
            }
            .task { token = KeychainStore.loadToken() ?? "" }
        }
    }

    @MainActor
    private func save() async {
        isSaving = true
        defer { isSaving = false }
        do {
            try KeychainStore.saveToken(token)
            if remindersEnabled {
                try await NotificationScheduler.enable()
            } else {
                NotificationScheduler.disable()
            }
            dismiss()
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}
