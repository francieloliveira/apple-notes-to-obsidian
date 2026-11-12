import SwiftUI
import AppKit

struct MenuPanelView: View {
    @EnvironmentObject private var model: AppModel
    @Environment(\.openWindow) private var openWindow

    var body: some View {
        VStack(spacing: 14) {
            header
            statusBlock
            quickMetrics
            primaryAction

            if let error = model.errorMessage {
                Text(error)
                    .font(Theme.font(10, .medium))
                    .foregroundStyle(Theme.red)
                    .lineLimit(2)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }

            HStack(spacing: 8) {
                panelButton(
                    model.snapshot.paused ? "Retomar" : "Pausar",
                    icon: model.snapshot.paused ? "play.fill" : "pause.fill",
                    color: Theme.amber
                ) {
                    model.setPaused(!model.snapshot.paused)
                }

                panelButton("Abrir app", icon: "macwindow", color: Theme.blue) {
                    NSApp.activate(ignoringOtherApps: true)
                    openWindow(id: "dashboard")
                }

                panelButton("Sair", icon: "power", color: Theme.red) {
                    model.quit()
                }
            }

            HStack(spacing: 5) {
                Image(systemName: "folder")
                    .font(.system(size: 8, weight: .semibold))
                Text(model.config.vaultURL.path)
                    .lineLimit(1)
                    .truncationMode(.middle)
                Spacer()
                Text("\(model.config.intervalMinutes) min")
            }
            .font(Theme.font(9, .medium))
            .foregroundStyle(Theme.muted.opacity(0.7))
        }
        .padding(16)
        .frame(width: 340)
        .background(AuroraBackground())
    }

    private var header: some View {
        HStack(spacing: 10) {
            LogoMark(size: 36)

            VStack(alignment: .leading, spacing: 1) {
                Text("VaultAI")
                    .font(Theme.font(16, .bold))
                    .foregroundStyle(.white)
                Text("Notes → Obsidian")
                    .font(Theme.font(9, .medium))
                    .foregroundStyle(Theme.muted)
            }

            Spacer()
            StatusPill(state: model.displayState, compact: true)
        }
    }

    private var menuRingSymbol: String? {
        guard model.percent == nil, model.displayState != .sincronizando else { return nil }
        switch model.displayState {
        case .ok: return "checkmark"
        case .pausa: return "pause.fill"
        case .erro: return "exclamationmark"
        default: return "moon.zzz"
        }
    }

    private var statusBlock: some View {
        HStack(spacing: 14) {
            ProgressRing(
                percent: model.percent,
                isActive: model.displayState == .sincronizando,
                color: model.stateColor,
                size: 68,
                caption: "",
                symbol: menuRingSymbol
            )

            VStack(alignment: .leading, spacing: 6) {
                Text(model.activityText)
                    .font(Theme.font(12, .semibold))
                    .foregroundStyle(.white.opacity(0.95))
                    .lineLimit(2)
                    .fixedSize(horizontal: false, vertical: true)

                GradientProgressBar(
                    percent: model.percent,
                    isActive: model.displayState == .sincronizando,
                    color: model.stateColor
                )

                Text("Último sync \(Dates.relative(model.snapshot.lastSync))")
                    .font(Theme.font(9, .medium))
                    .foregroundStyle(Theme.muted)
            }
        }
        .padding(12)
        .background(
            RoundedRectangle(cornerRadius: 16, style: .continuous)
                .fill(Color.white.opacity(0.04))
        )
        .overlay(
            RoundedRectangle(cornerRadius: 16, style: .continuous)
                .strokeBorder(Color.white.opacity(0.08), lineWidth: 1)
        )
    }

    private var quickMetrics: some View {
        HStack(spacing: 6) {
            CompactMetric(icon: "plus.circle.fill", title: "criadas", value: model.snapshot.sync.criadas, color: Theme.green)
            CompactMetric(icon: "arrow.triangle.2.circlepath", title: "atualizadas", value: model.snapshot.sync.atualizadas, color: Theme.blue)
            CompactMetric(icon: "link", title: "links", value: model.snapshot.organize.linkadas, color: Theme.accent)
        }
    }

    private var primaryAction: some View {
        Button {
            model.syncNow()
        } label: {
            HStack(spacing: 7) {
                if model.isRunning {
                    ProgressView().controlSize(.small).tint(Theme.ink)
                } else {
                    Image(systemName: "arrow.triangle.2.circlepath")
                        .font(.system(size: 12, weight: .bold))
                }
                Text(model.isRunning ? "Sincronizando…" : "Sincronizar agora")
            }
        }
        .buttonStyle(PrimaryButtonStyle())
        .disabled(model.isRunning)
        .opacity(model.isRunning ? 0.8 : 1)
    }

    private func panelButton(_ title: String, icon: String, color: Color, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            HStack(spacing: 5) {
                Image(systemName: icon)
                    .font(.system(size: 9, weight: .semibold))
                    .foregroundStyle(color)
                Text(title)
                    .lineLimit(1)
            }
        }
        .buttonStyle(SecondaryButtonStyle())
    }
}
