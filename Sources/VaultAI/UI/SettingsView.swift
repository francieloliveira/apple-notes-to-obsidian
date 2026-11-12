import SwiftUI
import AppKit

struct SettingsView: View {
    @EnvironmentObject private var model: AppModel
    @State private var draft = AppConfig()
    @State private var loaded = false
    @State private var savedRecently = false

    var body: some View {
        ZStack {
            AuroraBackground()

            VStack(spacing: 0) {
                ScrollView(.vertical, showsIndicators: false) {
                    VStack(spacing: 16) {
                        header
                        vaultCard
                        syncCard
                        privacyCard
                        domainsCard
                    }
                    .padding(.horizontal, 20)
                    .padding(.top, 44)
                    .padding(.bottom, 18)
                }

                actions
            }
        }
        .frame(
            minWidth: 540,
            idealWidth: 560,
            maxWidth: .infinity,
            minHeight: 640,
            idealHeight: 720,
            maxHeight: .infinity
        )
        .onAppear {
            if !loaded {
                draft = model.config
                loaded = true
            }
        }
    }

    // MARK: - Header

    private var header: some View {
        HStack(spacing: 12) {
            LogoMark(size: 40)
            VStack(alignment: .leading, spacing: 2) {
                Text("Ajustes")
                    .font(Theme.font(22, .bold))
                    .foregroundStyle(.white)
                Text("Configuração local do VaultAI")
                    .font(Theme.font(10, .medium))
                    .foregroundStyle(Theme.muted)
            }
            Spacer()
            Text("~/.vault/config.json")
                .font(Theme.font(9, .medium))
                .foregroundStyle(Theme.muted.opacity(0.7))
        }
    }

    // MARK: - Vault

    private var vaultCard: some View {
        GlassCard {
            VStack(alignment: .leading, spacing: 12) {
                SectionLabel(title: "Vault Obsidian", icon: "folder.fill")

                HStack(spacing: 8) {
                    TextField("~/VaultAI", text: $draft.vaultPath)
                        .textFieldStyle(.plain)
                        .font(Theme.font(12, .medium))
                        .foregroundStyle(.white)
                        .padding(.horizontal, 11)
                        .padding(.vertical, 9)
                        .background(
                            RoundedRectangle(cornerRadius: 10, style: .continuous)
                                .fill(Color.black.opacity(0.22))
                        )
                        .overlay(
                            RoundedRectangle(cornerRadius: 10, style: .continuous)
                                .strokeBorder(Color.white.opacity(0.10), lineWidth: 1)
                        )

                    Button {
                        chooseFolder()
                    } label: {
                        HStack(spacing: 4) {
                            Image(systemName: "folder.badge.plus")
                            Text("Escolher")
                        }
                    }
                    .buttonStyle(SecondaryButtonStyle())
                    .frame(width: 104)
                }

                Text("Caminho expandido: \(draft.vaultURL.path)")
                    .font(Theme.font(9, .medium))
                    .foregroundStyle(Theme.muted)
                    .lineLimit(1)
                    .truncationMode(.middle)

                TextField("Subpasta opcional (ex.: Notes)", text: $draft.syncRoot)
                    .textFieldStyle(.plain)
                    .font(Theme.font(12, .medium))
                    .foregroundStyle(.white)
                    .padding(.horizontal, 11)
                    .padding(.vertical, 9)
                    .background(
                        RoundedRectangle(cornerRadius: 10, style: .continuous)
                            .fill(Color.black.opacity(0.22))
                    )
                    .overlay(
                        RoundedRectangle(cornerRadius: 10, style: .continuous)
                            .strokeBorder(Color.white.opacity(0.10), lineWidth: 1)
                    )
            }
        }
    }

    // MARK: - Sync

    private var syncCard: some View {
        GlassCard {
            VStack(alignment: .leading, spacing: 14) {
                SectionLabel(title: "Sincronização", icon: "arrow.triangle.2.circlepath")

                settingRow(title: "Intervalo automático", subtitle: "O app roda enquanto estiver na barra de menu") {
                    Picker("", selection: $draft.pipelineIntervalSecs) {
                        Text("15 min").tag(900)
                        Text("30 min").tag(1800)
                        Text("1 h").tag(3600)
                        Text("2 h").tag(7200)
                    }
                    .pickerStyle(.segmented)
                    .labelsHidden()
                    .frame(width: 220)
                }

                Divider().overlay(Color.white.opacity(0.06))

                settingRow(title: "Workers de leitura", subtitle: "Processos paralelos ao buscar o corpo das notas") {
                    Stepper(value: $draft.fetchWorkers, in: 1...16) {
                        Text("\(draft.fetchWorkers)")
                            .font(Theme.font(12, .semibold))
                            .monospacedDigit()
                            .frame(width: 22)
                    }
                    .fixedSize()
                }

                Divider().overlay(Color.white.opacity(0.06))

                Toggle(isOn: $draft.autoSyncOnLaunch) {
                    settingLabel(title: "Sincronizar ao abrir", subtitle: "Executa se o último sync estiver atrasado")
                }
                .toggleStyle(.switch)
                .tint(Theme.accent)

                Divider().overlay(Color.white.opacity(0.06))

                Toggle(isOn: Binding(
                    get: { model.launchAtLogin },
                    set: { model.setLaunchAtLogin($0) }
                )) {
                    settingLabel(title: "Iniciar com o sistema", subtitle: "Registra o VaultAI como item de login")
                }
                .toggleStyle(.switch)
                .tint(Theme.accent)
            }
        }
    }

    // MARK: - Privacidade

    private var privacyCard: some View {
        GlassCard {
            VStack(alignment: .leading, spacing: 12) {
                SectionLabel(title: "Privacidade", icon: "lock.shield.fill")

                Toggle(isOn: $draft.secretsEnabled) {
                    settingLabel(
                        title: "Bloquear senhas e chaves",
                        subtitle: "Notas com senha, token ou API key ficam só no Apple Notes"
                    )
                }
                .toggleStyle(.switch)
                .tint(Theme.accent)

                HStack(spacing: 6) {
                    Image(systemName: "checkmark.seal.fill")
                        .font(.system(size: 9, weight: .semibold))
                        .foregroundStyle(Theme.green)
                    Text("Todo o processamento é local. Nenhum dado sai do seu Mac.")
                        .font(Theme.font(9.5, .medium))
                        .foregroundStyle(Theme.muted)
                }
            }
        }
    }

    // MARK: - Domínios

    private var domainsCard: some View {
        GlassCard {
            VStack(alignment: .leading, spacing: 10) {
                SectionLabel(title: "Domínios dos MOCs", icon: "square.grid.2x2.fill")

                ForEach(draft.domainKeywords.keys.sorted(), id: \.self) { domain in
                    HStack(alignment: .top, spacing: 10) {
                        Text(domain)
                            .font(Theme.font(10, .bold))
                            .foregroundStyle(Theme.violet)
                            .padding(.horizontal, 7)
                            .padding(.vertical, 3)
                            .background(Capsule().fill(Theme.violet.opacity(0.12)))
                            .frame(width: 72, alignment: .leading)

                        Text((draft.domainKeywords[domain] ?? []).joined(separator: " · "))
                            .font(Theme.font(10, .medium))
                            .foregroundStyle(Theme.muted)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }

                Text("Edite a taxonomia em config.json para adicionar domínios.")
                    .font(Theme.font(9, .medium))
                    .foregroundStyle(Theme.muted.opacity(0.7))
            }
        }
    }

    // MARK: - Ações

    private var actions: some View {
        HStack(spacing: 10) {
            Button {
                model.saveConfig(draft)
                withAnimation(.easeOut(duration: 0.2)) { savedRecently = true }
                DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
                    withAnimation(.easeOut(duration: 0.25)) { savedRecently = false }
                }
            } label: {
                HStack(spacing: 6) {
                    Image(systemName: savedRecently ? "checkmark.circle.fill" : "checkmark")
                    Text(savedRecently ? "Salvo" : "Salvar alterações")
                }
            }
            .buttonStyle(PrimaryButtonStyle())

            Button {
                model.openConfig()
            } label: {
                HStack(spacing: 5) {
                    Image(systemName: "doc.text")
                    Text("Abrir config")
                }
            }
            .buttonStyle(SecondaryButtonStyle())
            .frame(width: 132)
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 14)
        .background(
            LinearGradient(
                colors: [Color.black.opacity(0.0), Color.black.opacity(0.35)],
                startPoint: .top,
                endPoint: .bottom
            )
        )
        .overlay(alignment: .top) {
            Rectangle()
                .fill(Color.white.opacity(0.07))
                .frame(height: 1)
        }
    }

    // MARK: - Componentes

    private func settingRow<Content: View>(
        title: String,
        subtitle: String,
        @ViewBuilder content: () -> Content
    ) -> some View {
        HStack(alignment: .center, spacing: 12) {
            settingLabel(title: title, subtitle: subtitle)
            Spacer(minLength: 10)
            content()
        }
        .frame(maxWidth: .infinity)
    }

    private func settingLabel(title: String, subtitle: String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(title)
                .font(Theme.font(12, .semibold))
                .foregroundStyle(.white.opacity(0.94))
            Text(subtitle)
                .font(Theme.font(9.5, .medium))
                .foregroundStyle(Theme.muted)
                .fixedSize(horizontal: false, vertical: true)
        }
    }

    private func chooseFolder() {
        let panel = NSOpenPanel()
        panel.canChooseDirectories = true
        panel.canChooseFiles = false
        panel.allowsMultipleSelection = false
        panel.prompt = "Escolher vault"
        if panel.runModal() == .OK, let url = panel.url {
            draft.vaultPath = url.path
        }
    }
}
