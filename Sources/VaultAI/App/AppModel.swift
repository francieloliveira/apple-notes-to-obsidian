import Foundation
import SwiftUI
import AppKit
import ServiceManagement

@MainActor
final class AppModel: ObservableObject {
    @Published private(set) var config: AppConfig
    @Published private(set) var snapshot: DashboardSnapshot
    @Published private(set) var isRunning = false
    @Published private(set) var runningLabel = ""
    @Published var errorMessage: String?
    @Published var toast: String?
    @Published private(set) var launchAtLogin = LoginItem.isEnabled

    private var pollTimer: Timer?
    private var autoTimer: Timer?
    private var toastWorkItem: DispatchWorkItem?

    init() {
        let loaded = ConfigStore.load()
        config = loaded
        try? FileManager.default.createDirectory(at: loaded.stateURL, withIntermediateDirectories: true)
        StateStore.reconcileInterruptedRun(config: loaded)
        snapshot = StateStore.snapshot(config: loaded)

        startPolling()
        scheduleAutoSync()

        if loaded.autoSyncOnLaunch {
            DispatchQueue.main.asyncAfter(deadline: .now() + 3) { [weak self] in
                guard let self else { return }
                guard !self.isRunning, !StateStore.isPaused(config: self.config) else { return }
                let last = self.snapshot.lastSync
                let stale = last == nil || Date().timeIntervalSince(last!) > Double(self.config.pipelineIntervalSecs)
                if stale { self.syncNow() }
            }
        }
    }

    // MARK: - Derivados para a UI

    var displayState: DisplayState {
        if isRunning { return .sincronizando }
        return snapshot.displayState
    }

    var stateColor: Color { Theme.stateColor(displayState) }

    var stateTitle: String {
        if snapshot.simulated, displayState == .ok { return "Simulado" }
        return displayState.title
    }

    var percent: Int? { snapshot.percent }

    var activityText: String {
        if isRunning, snapshot.rawState != "running" {
            return runningLabel.isEmpty ? "Preparando o sync…" : runningLabel
        }
        return snapshot.activity
    }

    var subtitleText: String {
        if isRunning { return snapshot.rawState == "running" ? snapshot.subtitle : "Preparando o sync…" }
        return snapshot.subtitle
    }

    var menuBarIcon: String {
        switch displayState {
        case .sincronizando: return "arrow.triangle.2.circlepath"
        case .erro: return "exclamationmark.triangle.fill"
        case .pausa: return "pause.circle.fill"
        default: return "externaldrive.fill.badge.icloud"
        }
    }

    // MARK: - Polling

    private func startPolling() {
        pollTimer?.invalidate()
        pollTimer = Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { [weak self] _ in
            Task { @MainActor in self?.refresh() }
        }
    }

    func refresh() {
        if !isRunning, snapshot.rawState == "running", !PipelineLock.isRunning() {
            StateStore.reconcileInterruptedRun(config: config)
        }
        snapshot = StateStore.snapshot(config: config)
    }

    // MARK: - Pipeline

    func syncNow(full: Bool = false, dryRun: Bool = false) {
        guard !isRunning else { return }
        isRunning = true
        runningLabel = dryRun ? "Simulando sync…" : (full ? "Sincronizando tudo…" : "Sincronizando notas…")
        errorMessage = nil

        let currentConfig = config
        Task {
            let result = await Task.detached(priority: .userInitiated) {
                Pipeline(config: currentConfig).run(full: full, dryRun: dryRun)
            }.value

            self.isRunning = false
            self.refresh()

            if result.ok {
                self.showToast(result.summary)
            } else {
                self.errorMessage = result.error ?? "Sync falhou"
            }
        }
    }

    func setPaused(_ paused: Bool) {
        StateStore.setPaused(config: config, paused)
        if paused {
            autoTimer?.invalidate()
            autoTimer = nil
            showToast("Sync automático pausado")
        } else {
            scheduleAutoSync()
            showToast("Sync automático retomado")
        }
        refresh()
    }

    private func scheduleAutoSync() {
        autoTimer?.invalidate()
        guard !StateStore.isPaused(config: config) else { return }

        autoTimer = Timer.scheduledTimer(withTimeInterval: Double(config.pipelineIntervalSecs), repeats: true) { [weak self] _ in
            Task { @MainActor in
                guard let self, !self.isRunning, !StateStore.isPaused(config: self.config) else { return }
                self.syncNow()
            }
        }
    }

    // MARK: - Configuração

    func saveConfig(_ newConfig: AppConfig) {
        config = newConfig
        ConfigStore.save(newConfig)
        try? FileManager.default.createDirectory(at: newConfig.stateURL, withIntermediateDirectories: true)
        scheduleAutoSync()
        refresh()
        showToast("Configuração salva")
    }

    func setLaunchAtLogin(_ enabled: Bool) {
        do {
            try LoginItem.set(enabled)
            launchAtLogin = LoginItem.isEnabled
            showToast(enabled ? "VaultAI abrirá ao iniciar" : "Abertura automática desativada")
        } catch {
            launchAtLogin = LoginItem.isEnabled
            errorMessage = "Não foi possível alterar a abertura automática: \(error.localizedDescription)"
        }
    }

    // MARK: - Ações do sistema

    func openVault() {
        NSWorkspace.shared.open(config.vaultURL)
    }

    func openLog() {
        let log = config.pipelineLogURL
        if !FileManager.default.fileExists(atPath: log.path) {
            FileManager.default.createFile(atPath: log.path, contents: nil)
        }
        openInTextEdit(log)
    }

    func openConfig() {
        ConfigStore.save(config)
        openInTextEdit(config.configURL)
    }

    private func openInTextEdit(_ url: URL) {
        guard let editor = NSWorkspace.shared.urlForApplication(withBundleIdentifier: "com.apple.TextEdit") else {
            NSWorkspace.shared.open(url)
            return
        }
        NSWorkspace.shared.open([url], withApplicationAt: editor, configuration: .init()) { _, _ in }
    }

    func quit() {
        NSApp.terminate(nil)
    }

    // MARK: - Feedback

    func showToast(_ text: String) {
        toast = text
        toastWorkItem?.cancel()
        let item = DispatchWorkItem { [weak self] in
            Task { @MainActor in
                withAnimation(.easeOut(duration: 0.25)) { self?.toast = nil }
            }
        }
        toastWorkItem = item
        DispatchQueue.main.asyncAfter(deadline: .now() + 3.5, execute: item)
    }
}

enum LoginItem {
    static var isEnabled: Bool {
        SMAppService.mainApp.status == .enabled
    }

    static func set(_ enabled: Bool) throws {
        if enabled {
            try SMAppService.mainApp.register()
        } else {
            try SMAppService.mainApp.unregister()
        }
    }
}
