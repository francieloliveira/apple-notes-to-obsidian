import SwiftUI
import AppKit

struct SettingsView: View {
    @EnvironmentObject private var model: AppModel
    @EnvironmentObject private var router: SettingsRouter
    @State private var draft = AppConfig()
    @State private var loaded = false
    @State private var savedRecently = false

    // Editor de domínios
    @State private var addingDomain = false
    @State private var editingDomain: String?
    @State private var domainName = ""
    @State private var domainKeywordsText = ""
    @State private var domainError: String?

    private enum DomainField: Hashable { case name, keywords }
    @FocusState private var focusedField: DomainField?

    private var hasChanges: Bool { draft != model.config }

    var body: some View {
        ZStack {
            AuroraBackground()

            VStack(spacing: 0) {
                ScrollViewReader { proxy in
                    ScrollView(.vertical, showsIndicators: false) {
                        VStack(spacing: 16) {
                            header
                            vaultCard
                            syncCard
                            privacyCard
                            domainsCard
                                .id(SettingsRouter.Section.domains)
                        }
                        .padding(.horizontal, 20)
                        .padding(.top, 44)
                        .padding(.bottom, 18)
                    }
                    .onAppear { scrollToPending(proxy) }
                    .onChange(of: router.pending) { _ in scrollToPending(proxy) }
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

    /// Rola até a seção pedida pelo dashboard e limpa o pedido.
    @MainActor
    private func scrollToPending(_ proxy: ScrollViewProxy) {
        guard router.pending == .domains else { return }
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.18) {
            withAnimation(.easeOut(duration: 0.32)) {
                proxy.scrollTo(SettingsRouter.Section.domains, anchor: .bottom)
            }
            router.clear()
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
            VStack(alignment: .leading, spacing: 12) {
                HStack(spacing: 8) {
                    SectionLabel(title: "Domínios dos MOCs", icon: "square.grid.2x2.fill")
                    Spacer()
                    Text("\(draft.domainKeywords.count)")
                        .font(Theme.font(9, .semibold))
                        .foregroundStyle(Theme.muted)
                        .padding(.horizontal, 7)
                        .padding(.vertical, 2)
                        .background(Capsule().fill(Color.white.opacity(0.06)))
                }

                Text("Cada domínio vira um MOC no vault. As palavras-chave ligam a nota ao domínio quando aparecem no texto; uma tag com o mesmo nome do domínio também conta.")
                    .font(Theme.font(9.5, .medium))
                    .foregroundStyle(Theme.muted)
                    .fixedSize(horizontal: false, vertical: true)

                VStack(spacing: 6) {
                    ForEach(draft.domainKeywords.keys.sorted(), id: \.self) { domain in
                        if editingDomain == domain {
                            domainEditor(original: domain)
                        } else {
                            domainRow(domain)
                        }
                    }
                }

                if addingDomain {
                    domainEditor(original: nil)
                } else if editingDomain == nil {
                    Button {
                        startAddingDomain()
                    } label: {
                        HStack(spacing: 5) {
                            Image(systemName: "plus.circle.fill")
                            Text("Adicionar domínio")
                        }
                        .font(Theme.font(11, .semibold))
                        .foregroundStyle(Theme.accent)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 9)
                        .background(
                            RoundedRectangle(cornerRadius: 10, style: .continuous)
                                .fill(Theme.accent.opacity(0.07))
                        )
                        .overlay(
                            RoundedRectangle(cornerRadius: 10, style: .continuous)
                                .strokeBorder(
                                    Theme.accent.opacity(0.28),
                                    style: StrokeStyle(lineWidth: 1, dash: [4, 3])
                                )
                        )
                    }
                    .buttonStyle(.plain)
                }

                if let domainError {
                    HStack(spacing: 5) {
                        Image(systemName: "exclamationmark.circle.fill")
                            .font(.system(size: 9, weight: .semibold))
                        Text(domainError)
                    }
                    .font(Theme.font(9.5, .medium))
                    .foregroundStyle(Theme.red)
                }

                Text("As alterações valem para o próximo sync. Clique em Salvar alterações para aplicar.")
                    .font(Theme.font(9, .medium))
                    .foregroundStyle(Theme.muted.opacity(0.7))
            }
        }
    }

    private func domainRow(_ domain: String) -> some View {
        let keywords = draft.domainKeywords[domain] ?? []
        return HStack(spacing: 8) {
            Text(domain)
                .font(Theme.font(10, .bold))
                .foregroundStyle(Theme.violet)
                .padding(.horizontal, 7)
                .padding(.vertical, 3)
                .background(Capsule().fill(Theme.violet.opacity(0.12)))

            Text(keywords.isEmpty ? "só por tag" : keywords.joined(separator: " · "))
                .font(Theme.font(10, .medium))
                .foregroundStyle(Theme.muted.opacity(keywords.isEmpty ? 0.6 : 1))
                .lineLimit(2)
                .fixedSize(horizontal: false, vertical: true)

            Spacer(minLength: 6)

            HeaderIconButton(icon: "pencil", help: "Editar \(domain)") {
                startEditingDomain(domain)
            }
            HeaderIconButton(icon: "trash", help: "Remover \(domain)") {
                removeDomain(domain)
            }
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 8)
        .background(
            RoundedRectangle(cornerRadius: 10, style: .continuous)
                .fill(Color.white.opacity(0.025))
        )
    }

    private func domainEditor(original: String?) -> some View {
        let accent = original == nil ? Theme.accent : Theme.violet
        return VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 6) {
                Image(systemName: original == nil ? "plus.circle.fill" : "pencil.circle.fill")
                    .font(.system(size: 11, weight: .semibold))
                    .foregroundStyle(accent)
                Text(original == nil ? "Novo domínio" : "Editar domínio")
                    .font(Theme.font(10, .semibold))
                    .foregroundStyle(.white.opacity(0.9))
                Spacer()
            }

            configField("Nome do domínio (ex.: viagens)", text: $domainName)
                .focused($focusedField, equals: .name)
                .onSubmit { commitDomain(original: original) }

            configField("Palavras-chave separadas por vírgula (ex.: viagem, hotel, passagem)", text: $domainKeywordsText)
                .focused($focusedField, equals: .keywords)
                .onSubmit { commitDomain(original: original) }

            HStack(spacing: 8) {
                smallButton("Salvar domínio", tint: accent, filled: true) {
                    commitDomain(original: original)
                }
                smallButton("Cancelar", tint: Theme.muted, filled: false) {
                    cancelDomainEditor()
                }
                Spacer()
            }
        }
        .padding(10)
        .background(
            RoundedRectangle(cornerRadius: 10, style: .continuous)
                .fill(Color.white.opacity(0.03))
        )
        .overlay(
            RoundedRectangle(cornerRadius: 10, style: .continuous)
                .strokeBorder(accent.opacity(0.28), lineWidth: 1)
        )
    }

    private func startAddingDomain() {
        editingDomain = nil
        addingDomain = true
        domainName = ""
        domainKeywordsText = ""
        domainError = nil
        focusedField = .name
    }

    private func startEditingDomain(_ domain: String) {
        addingDomain = false
        editingDomain = domain
        domainName = domain
        domainKeywordsText = (draft.domainKeywords[domain] ?? []).joined(separator: ", ")
        domainError = nil
        focusedField = .name
    }

    private func cancelDomainEditor() {
        addingDomain = false
        editingDomain = nil
        domainName = ""
        domainKeywordsText = ""
        domainError = nil
    }

    private func removeDomain(_ domain: String) {
        draft.domainKeywords.removeValue(forKey: domain)
        if editingDomain == domain { cancelDomainEditor() }
    }

    private func commitDomain(original: String?) {
        if let error = DomainCatalog.apply(
            name: domainName,
            keywordsText: domainKeywordsText,
            original: original,
            to: &draft.domainKeywords
        ) {
            domainError = message(for: error)
            return
        }
        cancelDomainEditor()
    }

    private func message(for error: DomainCatalog.ValidationError) -> String {
        switch error {
        case .emptyName:
            return "Dê um nome ao domínio."
        case .invalidCharacters:
            return "O nome vira arquivo do MOC: evite / \\ e :."
        case .duplicate(let name):
            return "Já existe um domínio chamado “\(name)”."
        }
    }

    private func parseKeywords(_ raw: String) -> [String] {
        var seen = Set<String>()
        return raw
            .split(whereSeparator: { $0 == "," || $0 == ";" || $0 == "·" })
            .map { $0.trimmingCharacters(in: .whitespacesAndNewlines).lowercased() }
            .filter { !$0.isEmpty && seen.insert($0).inserted }
    }

    // MARK: - Ações

    private var actions: some View {
        HStack(spacing: 10) {
            Button {
                guard hasChanges else { return }
                model.saveConfig(draft)
                withAnimation(.easeOut(duration: 0.2)) { savedRecently = true }
                DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
                    withAnimation(.easeOut(duration: 0.25)) { savedRecently = false }
                }
            } label: {
                HStack(spacing: 6) {
                    Image(systemName: savedRecently ? "checkmark.circle.fill" : "checkmark")
                    Text(savedRecently ? "Salvo" : (hasChanges ? "Salvar alterações" : "Tudo salvo"))
                }
            }
            .buttonStyle(PrimaryButtonStyle())
            .disabled(!hasChanges)
            .opacity(hasChanges ? 1 : 0.55)
            .animation(.easeOut(duration: 0.2), value: hasChanges)

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

    private func configField(_ placeholder: String, text: Binding<String>) -> some View {
        TextField(placeholder, text: text)
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

    private func smallButton(
        _ title: String,
        tint: Color,
        filled: Bool,
        action: @escaping () -> Void
    ) -> some View {
        Button(action: action) {
            Text(title)
                .font(Theme.font(10.5, .semibold))
                .foregroundStyle(filled ? Theme.ink : tint)
                .padding(.horizontal, 11)
                .padding(.vertical, 5)
                .background(Capsule().fill(filled ? tint : tint.opacity(0.12)))
                .overlay(Capsule().strokeBorder(tint.opacity(filled ? 0 : 0.30), lineWidth: 1))
        }
        .buttonStyle(.plain)
    }

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
