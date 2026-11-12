import Foundation

public struct PipelineResult: Sendable {
    public let ok: Bool
    public let summary: String
    public let elapsed: Double
    public let error: String?

    public static func failure(_ message: String) -> PipelineResult {
        PipelineResult(ok: false, summary: message, elapsed: 0, error: message)
    }
}

/// Lock do pipeline. Guarda o PID do processo que está sincronizando para
/// distinguir uma execução real de um lock deixado por um processo morto.
public enum PipelineLock {
    public static var path = "/tmp/vault_pipeline.lock"

    public static func pid() -> pid_t? {
        guard let text = try? String(contentsOfFile: path, encoding: .utf8) else { return nil }
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard let value = pid_t(trimmed), value > 0 else { return nil }
        return value
    }

    public static func isAlive(_ pid: pid_t) -> Bool {
        if kill(pid, 0) == 0 { return true }
        return errno == EPERM
    }

    /// Há um pipeline de verdade rodando agora?
    public static func isRunning() -> Bool {
        guard let pid = pid() else { return false }
        return isAlive(pid)
    }

    /// Remove o lock quando o processo que o criou já terminou.
    @discardableResult
    public static func clearIfStale() -> Bool {
        guard FileManager.default.fileExists(atPath: path) else { return false }
        guard let pid = pid() else {
            try? FileManager.default.removeItem(atPath: path)
            return true
        }
        guard !isAlive(pid) else { return false }
        try? FileManager.default.removeItem(atPath: path)
        return true
    }
}

/// Orquestrador nativo: lock, sync, organize, status e notificação.
public final class Pipeline {
    private let config: AppConfig
    private let logger: VaultLogger
    private let lockPath = PipelineLock.path
    private let stepTimeout: TimeInterval = 700

    public init(config: AppConfig) {
        self.config = config
        self.logger = VaultLogger(fileURL: config.pipelineLogURL)
    }

    public func run(full: Bool, dryRun: Bool, verbose: Bool = false) -> PipelineResult {
        PipelineEnvironment.verbose = verbose
        try? FileManager.default.createDirectory(at: config.stateURL, withIntermediateDirectories: true)

        let rotated = VaultLogger.rotateLogs(in: config.stateURL)
        if rotated > 0 { logger.log("Logs rotacionados: \(rotated) arquivo(s)") }

        logger.log(String(repeating: "=", count: 55))
        logger.log("=== PIPELINE INICIADO\(dryRun ? " [DRY RUN]" : "") ===")

        guard acquireLock() else {
            return .failure("Pipeline já em execução")
        }
        defer { releaseLock() }

        let started = Date()
        StateStore.writeStatus(
            config: config,
            state: "running",
            message: dryRun ? "Simulando sync..." : "Sincronizando Apple Notes..."
        )

        let sync = VaultSync(config: config, logger: VaultLogger(fileURL: config.syncLogURL))
        let syncOK = sync.run(full: full, dryRun: dryRun, verbose: verbose)
        if !syncOK {
            StateStore.writeStatus(config: config, state: "error", message: "Sync falhou")
            Notifier.post(
                title: "VaultAI",
                subtitle: "Sync falhou",
                message: "Erro ao sincronizar Apple Notes. Ver \(config.pipelineLogURL.path)",
                sound: "Basso"
            )
            return .failure("Sync falhou")
        }

        StateStore.writeStatus(config: config, state: "running", message: "Organizando vault...")

        let organizer = VaultOrganizer(config: config, logger: VaultLogger(fileURL: config.organizeLogURL))
        let organizeOK = organizer.run(full: full, dryRun: dryRun, verbose: verbose)

        let elapsed = Date().timeIntervalSince(started)
        let metrics = StateStore.readMetrics(config: config)
        let organize = StateStore.readOrganizeMetrics(config: config)

        if !organizeOK {
            var payload = metrics.dictionary
            payload["organize"] = organize.dictionary
            payload["elapsed_s"] = elapsed
            StateStore.writeStatus(config: config, state: "error", message: "Organização falhou", metrics: payload)
            Notifier.post(
                title: "VaultAI",
                subtitle: "Organização falhou",
                message: "Sync ok (\(metrics.criadas) novas, \(metrics.atualizadas) atualizadas) mas a organização teve erro.",
                sound: "Basso"
            )
            return PipelineResult(ok: false, summary: "Organização falhou", elapsed: elapsed, error: "Organização falhou")
        }

        var parts: [String] = []
        if metrics.criadas > 0 { parts.append("\(metrics.criadas) nova\(metrics.criadas == 1 ? "" : "s")") }
        if metrics.atualizadas > 0 { parts.append("\(metrics.atualizadas) atualizada\(metrics.atualizadas == 1 ? "" : "s")") }
        if metrics.bloqueadas > 0 { parts.append("\(metrics.bloqueadas) secret(s) bloqueado(s)") }
        if metrics.erros > 0 { parts.append("\(metrics.erros) erro\(metrics.erros == 1 ? "" : "s")") }

        let summary: String
        if metrics.skipped && parts.isEmpty {
            summary = "Sem mudanças no Apple Notes"
        } else {
            summary = parts.isEmpty ? "Tudo atualizado" : parts.joined(separator: "  ·  ")
        }

        var fullSummary = summary
        if organize.linkadas > 0 && !metrics.skipped {
            fullSummary += "  ·  \(organize.linkadas) link(s)"
        }

        var payload = metrics.dictionary
        payload["organize"] = organize.dictionary
        payload["elapsed_s"] = elapsed
        StateStore.writeStatus(config: config, state: "ok", message: fullSummary, metrics: payload)

        let shouldNotify = !dryRun && !(metrics.skipped && parts.isEmpty && organize.linkadas == 0)
        if shouldNotify {
            Notifier.post(
                title: "VaultAI",
                subtitle: "concluído em \(Int(elapsed.rounded()))s",
                message: fullSummary,
                sound: "Glass"
            )
        }

        logger.log("=== PIPELINE CONCLUÍDO ===")
        logger.log(String(repeating: "=", count: 55))
        return PipelineResult(ok: true, summary: fullSummary, elapsed: elapsed, error: nil)
    }

    // MARK: - Lock

    private func acquireLock() -> Bool {
        let fm = FileManager.default
        if fm.fileExists(atPath: lockPath) {
            let pid = PipelineLock.pid()
            let alive = pid.map(PipelineLock.isAlive) ?? false

            if !alive {
                logger.log("Lock órfão (processo \(pid.map(String.init) ?? "?") já terminou). Removendo e continuando.")
                try? fm.removeItem(atPath: lockPath)
            } else {
                let attributes = try? fm.attributesOfItem(atPath: lockPath)
                let modified = (attributes?[.modificationDate] as? Date) ?? .distantPast
                let age = Date().timeIntervalSince(modified)
                if age < stepTimeout * 2 {
                    logger.log("!! Lock ativo (pid \(pid!), \(Int(age))s). Pipeline já em execução. Saindo.")
                    return false
                }
                logger.log("Lock antigo (\(Int(age))s). Removendo e continuando.")
                try? fm.removeItem(atPath: lockPath)
            }
        }
        fm.createFile(atPath: lockPath, contents: Data("\(ProcessInfo.processInfo.processIdentifier)".utf8))
        return true
    }

    private func releaseLock() {
        try? FileManager.default.removeItem(atPath: lockPath)
    }
}
