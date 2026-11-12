import SwiftUI
import AppKit

struct DashboardView: View {
    @EnvironmentObject private var model: AppModel
    @Environment(\.openWindow) private var openWindow

    var body: some View {
        ZStack(alignment: .top) {
            AuroraBackground()

            ScrollView(.vertical, showsIndicators: false) {
                VStack(spacing: 14) {
                    header
                    if let error = model.errorMessage {
                        errorBanner(error)
                    }
                    heroCard
                    metricsCard
                    organizeCard
                    actionsCard
                    footer
                }
                .padding(.horizontal, 20)
                .padding(.top, 44)
                .padding(.bottom, 20)
            }

            if let toast = model.toast {
                ToastView(text: toast)
                    .padding(.top, 14)
                    .transition(.move(edge: .top).combined(with: .opacity))
            }
        }
        .frame(
            minWidth: 500,
            idealWidth: 520,
            maxWidth: .infinity,
            minHeight: 740,
            idealHeight: 812,
            maxHeight: .infinity
        )
        .onAppear { NSApp.activate(ignoringOtherApps: true) }
    }

    // MARK: - Header

    private var header: some View {
        HStack(spacing: 14) {
            LogoMark(size: 50)

            VStack(alignment: .leading, spacing: 3) {
                Text("VaultAI")
                    .font(.system(size: 26, weight: .bold, design: .rounded))
                    .foregroundStyle(.white)
                Text("Apple Notes → Obsidian")
                    .font(Theme.font(11, .medium))
                    .foregroundStyle(Theme.muted)
            }

            Spacer()

            VStack(alignment: .trailing, spacing: 7) {
                HStack(spacing: 8) {
                    StatusPill(state: model.displayState)
                    HeaderIconButton(icon: "gearshape.fill", help: "Ajustes") {
                        NSApp.activate(ignoringOtherApps: true)
                        openWindow(id: "settings")
                    }
                }
                HStack(spacing: 4) {
                    Image(systemName: "clock.arrow.circlepath")
                        .font(.system(size: 8, weight: .semibold))
                    Text("auto · \(model.config.intervalMinutes) min")
                        .font(Theme.font(9, .medium))
                }
                .foregroundStyle(Theme.muted.opacity(0.85))
            }
        }
    }

    // MARK: - Hero

    private var heroCard: some View {
        GlassCard(padding: 16, glow: model.stateColor) {
            HStack(spacing: 18) {
                ProgressRing(
                    percent: model.percent,
                    isActive: model.displayState == .sincronizando,
                    color: model.stateColor,
                    size: 96,
                    caption: ringCaption,
                    symbol: ringSymbol
                )

                VStack(alignment: .leading, spacing: 8) {
                    HStack(alignment: .firstTextBaseline) {
                        Text(model.displayState.title)
                            .font(Theme.font(20, .bold))
                            .foregroundStyle(.white)

                        Spacer()

                        if let elapsed = model.snapshot.elapsed, elapsed > 0 {
                            Text("\(Int(elapsed.rounded()))s")
                                .font(Theme.font(9, .semibold))
                                .foregroundStyle(Theme.muted)
                                .padding(.horizontal, 7)
                                .padding(.vertical, 3)
                                .background(Capsule().fill(Color.white.opacity(0.06)))
                        }
                    }

                    Text(model.activityText)
                        .font(Theme.font(12))
                        .foregroundStyle(Theme.muted)
                        .lineLimit(2)
                        .fixedSize(horizontal: false, vertical: true)

                    GradientProgressBar(
                        percent: model.percent,
                        isActive: model.displayState == .sincronizando,
                        color: model.stateColor
                    )
                    .padding(.top, 1)

                    HStack(spacing: 12) {
                        if let progress = model.snapshot.progress {
                            metricLabel("\(progress.current)/\(progress.total) notas", icon: "doc.text")
                        }
                        metricLabel("Último sync \(Dates.relative(model.snapshot.lastSync))", icon: "clock")
                    }
                    .padding(.top, 1)
                }
            }
        }
    }

    private var ringCaption: String {
        if model.percent != nil { return "progresso" }
        switch model.displayState {
        case .ok: return "em dia"
        case .pausa: return "pausado"
        case .erro: return "atenção"
        default: return "aguardando"
        }
    }

    private var ringSymbol: String? {
        guard model.percent == nil, model.displayState != .sincronizando else { return nil }
        switch model.displayState {
        case .ok: return "checkmark"
        case .pausa: return "pause.fill"
        case .erro: return "exclamationmark"
        default: return "moon.zzz"
        }
    }

    private func metricLabel(_ text: String, icon: String) -> some View {
        HStack(spacing: 4) {
            Image(systemName: icon)
                .font(.system(size: 8, weight: .semibold))
            Text(text)
                .font(Theme.font(9.5, .medium))
                .lineLimit(1)
        }
        .foregroundStyle(Theme.muted)
    }

    // MARK: - Métricas

    private var metricsCard: some View {
        let sync = model.snapshot.sync
        return GlassCard(padding: 16) {
            VStack(spacing: 10) {
                HStack {
                    SectionLabel(title: "Métricas do sync", icon: "chart.bar.fill")
                    Spacer()
                    Text(sync.skipped ? "sem mudanças" : "delta")
                        .font(Theme.font(9, .semibold))
                        .foregroundStyle(sync.skipped ? Theme.muted : Theme.green)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 3)
                        .background(Capsule().fill((sync.skipped ? Theme.muted : Theme.green).opacity(0.12)))
                }

                HStack(spacing: 8) {
                    MetricTile(icon: "plus.circle.fill", title: "Criadas", value: sync.criadas, color: Theme.green)
                    MetricTile(icon: "arrow.triangle.2.circlepath", title: "Atualizadas", value: sync.atualizadas, color: Theme.blue)
                    MetricTile(icon: "exclamationmark.triangle.fill", title: "Erros", value: sync.erros, color: Theme.red)
                    MetricTile(icon: "lock.fill", title: "Bloqueadas", value: sync.bloqueadas, color: Theme.amber)
                }

                HStack(spacing: 14) {
                    metricLabel("protegidas: \(sync.protegidas)", icon: "shield.lefthalf.filled")
                    metricLabel("secrets: \(sync.bloqueadas)", icon: "eye.slash")
                    Spacer()
                    if let generated = sync.generatedAt {
                        metricLabel(Dates.relative(generated), icon: "clock")
                    }
                }
            }
        }
    }

    // MARK: - Organize

    private var organizeCard: some View {
        let organize = model.snapshot.organize
        return GlassCard(padding: 16) {
            VStack(spacing: 10) {
                HStack {
                    SectionLabel(title: "Organize", icon: "point.3.connected.trianglepath.dotted")
                    Spacer()
                    Text("\(model.config.maxInlineLinks) links/nota")
                        .font(Theme.font(9, .medium))
                        .foregroundStyle(Theme.muted)
                }

                HStack(spacing: 8) {
                    MetricTile(icon: "link", title: "Links", value: organize.linkadas, color: Theme.accent)
                    MetricTile(icon: "square.grid.2x2.fill", title: "MOCs", value: organize.mocs, color: Theme.violet)
                    MetricTile(icon: "trash.fill", title: "Lixo", value: organize.lixo, color: Theme.amber)
                }
            }
        }
    }

    // MARK: - Ações

    private var actionsCard: some View {
        GlassCard(padding: 16) {
            VStack(spacing: 10) {
                SectionLabel(title: "Ações", icon: "bolt.fill")
                    .frame(maxWidth: .infinity, alignment: .leading)

                Button {
                    model.syncNow()
                } label: {
                    HStack(spacing: 8) {
                        if model.isRunning {
                            ProgressView()
                                .controlSize(.small)
                                .tint(Theme.ink)
                        } else {
                            Image(systemName: "arrow.triangle.2.circlepath")
                                .font(.system(size: 13, weight: .bold))
                        }
                        Text(model.isRunning ? model.runningLabel : "Sincronizar agora")
                    }
                }
                .buttonStyle(PrimaryButtonStyle())
                .disabled(model.isRunning)
                .opacity(model.isRunning ? 0.8 : 1)

                HStack(spacing: 8) {
                    secondaryButton("Sync completo", icon: "arrow.clockwise") {
                        model.syncNow(full: true)
                    }
                    secondaryButton("Simular", icon: "eye") {
                        model.syncNow(dryRun: true)
                    }
                }

                HStack(spacing: 8) {
                    secondaryButton(
                        model.snapshot.paused ? "Retomar" : "Pausar",
                        icon: model.snapshot.paused ? "play.fill" : "pause.fill"
                    ) {
                        model.setPaused(!model.snapshot.paused)
                    }
                    secondaryButton("Abrir vault", icon: "folder") {
                        model.openVault()
                    }
                    secondaryButton("Abrir log", icon: "doc.text") {
                        model.openLog()
                    }
                }
            }
        }
    }

    private func secondaryButton(_ title: String, icon: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            HStack(spacing: 5) {
                Image(systemName: icon)
                    .font(.system(size: 10, weight: .semibold))
                Text(title)
                    .lineLimit(1)
                    .minimumScaleFactor(0.8)
            }
        }
        .buttonStyle(SecondaryButtonStyle())
    }

    // MARK: - Erro / rodapé

    private func errorBanner(_ message: String) -> some View {
        HStack(spacing: 10) {
            Image(systemName: "exclamationmark.triangle.fill")
                .font(.system(size: 13, weight: .semibold))
                .foregroundStyle(Theme.red)

            Text(message)
                .font(Theme.font(11, .medium))
                .foregroundStyle(.white.opacity(0.9))
                .lineLimit(2)
                .fixedSize(horizontal: false, vertical: true)

            Spacer(minLength: 4)

            Button {
                model.errorMessage = nil
            } label: {
                Image(systemName: "xmark")
                    .font(.system(size: 9, weight: .bold))
                    .foregroundStyle(Theme.muted)
            }
            .buttonStyle(.plain)
        }
        .padding(12)
        .background(
            RoundedRectangle(cornerRadius: 14, style: .continuous)
                .fill(Theme.red.opacity(0.12))
        )
        .overlay(
            RoundedRectangle(cornerRadius: 14, style: .continuous)
                .strokeBorder(Theme.red.opacity(0.25), lineWidth: 1)
        )
    }

    private var footer: some View {
        HStack(spacing: 6) {
            Image(systemName: "folder")
                .font(.system(size: 8, weight: .semibold))
            Text(model.config.vaultURL.path)
                .lineLimit(1)
                .truncationMode(.middle)
            Spacer()
            Text("v2.0 · Swift")
                .font(Theme.font(9, .medium))
        }
        .font(Theme.font(9, .medium))
        .foregroundStyle(Theme.muted.opacity(0.75))
        .padding(.horizontal, 4)
    }
}

// MARK: - Toast

struct ToastView: View {
    let text: String

    var body: some View {
        HStack(spacing: 8) {
            Image(systemName: "checkmark.circle.fill")
                .font(.system(size: 12, weight: .semibold))
                .foregroundStyle(Theme.green)
            Text(text)
                .font(Theme.font(11, .semibold))
                .foregroundStyle(.white.opacity(0.92))
                .lineLimit(1)
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 9)
        .background(Capsule().fill(.ultraThinMaterial))
        .overlay(Capsule().strokeBorder(Color.white.opacity(0.14), lineWidth: 1))
        .shadow(color: Color.black.opacity(0.35), radius: 16, y: 8)
    }
}
