import SwiftUI
import AppKit

@main
struct VaultAIApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
    @StateObject private var model = AppModel()
    @StateObject private var router = SettingsRouter()
    @Environment(\.openWindow) private var openWindow

    var body: some Scene {
        Window("VaultAI", id: "dashboard") {
            DashboardView()
                .environmentObject(model)
                .environmentObject(router)
                .preferredColorScheme(.dark)
        }
        .windowStyle(.hiddenTitleBar)
        .windowResizability(.contentMinSize)
        .defaultSize(width: 520, height: 840)
        .commands {
            CommandGroup(replacing: .newItem) {}
            CommandGroup(replacing: .appSettings) {
                Button("Ajustes…") {
                    NSApp.activate(ignoringOtherApps: true)
                    openWindow(id: "settings")
                }
                .keyboardShortcut(",", modifiers: [.command])
            }
            CommandGroup(after: .appInfo) {
                Button("Sincronizar agora") { model.syncNow() }
                    .keyboardShortcut("r", modifiers: [.command])
                Button("Sync completo") { model.syncNow(full: true) }
                    .keyboardShortcut("r", modifiers: [.command, .shift])
            }
        }

        MenuBarExtra {
            MenuPanelView()
                .environmentObject(model)
                .environmentObject(router)
        } label: {
            Image(systemName: model.menuBarIcon)
        }
        .menuBarExtraStyle(.window)

        Window("Ajustes", id: "settings") {
            SettingsView()
                .environmentObject(model)
                .environmentObject(router)
                .preferredColorScheme(.dark)
        }
        .windowStyle(.hiddenTitleBar)
        .windowResizability(.contentMinSize)
        .defaultSize(width: 560, height: 740)
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        false
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.regular)
    }
}
