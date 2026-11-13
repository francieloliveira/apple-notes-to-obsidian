import SwiftUI

/// Ponte entre o dashboard e a janela de Ajustes para abrir direto numa seção.
@MainActor
final class SettingsRouter: ObservableObject {
    enum Section: Hashable {
        case domains
    }

    @Published private(set) var pending: Section?

    func open(_ section: Section) {
        pending = section
    }

    func clear() {
        pending = nil
    }
}
