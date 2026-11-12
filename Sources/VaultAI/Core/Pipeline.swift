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

/// Frase final do pipeline. Separada para poder testar o resumo sem tocar
/// no Apple Notes — inclusive o caso de simulação, que não grava métricas.
public enum PipelineSummary {
    public static func make(counts: SyncCounts, links: Int, dryRun: Bool, skipped: Bool) -> String {
        var parts: [String] = []
        if counts.created > 0 { parts.append("\(counts.created) nova\(counts.created == 1 ? "" : "s")") }
        if counts.updated > 0 { parts.append("\(counts.updated) atualizada\(counts.updated == 1 ? "" : "s")") }
        if counts.blocked > 0 { parts.append("\(counts.blocked) secret(s) bloqueado(s)") }
        if counts.errors > 0 { parts.append("\(counts.errors) erro\(counts.errors == 1 ? "" : "s")") }

        let nothingToDo = dryRun
            ? parts.isEmpty
            : (skipped && parts.isEmpty)

        var summary: String
        if nothingToDo {
            summary = dryRun ? "Simulação: nada a fazer" : "Sem mudanças no Apple Notes"
        } else {
            let base = parts.isEmpty ? "Tudo atualizado" : parts.joined(separator: "  ·  ")
            summary = dryRun ? "Simulação: \(base)" : base
        }

        if links > 0 && !skipped {
            summary += "  ·  \(links) link(s)"
        }
        return summary
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

        // Em dry run o metrics.json não é reescrito, então o resumo vem das
        // contagens da própria simulação.
        let counts = dryRun
            ? sync.lastCounts
            : SyncCounts(
                created: metrics.criadas,
                updated: metrics.atualizadas,
                blocked: metrics.bloqueadas,
                protected: metrics.protegidas,
                errors: metrics.erros
            )

        let summary = PipelineSummary.make(
            counts: counts,
            links: organize.linkadas,
            dryRun: dryRun,
            skipped: metrics.skipped
        )

        var payload: [String: Any]
        if dryRun {
            // A simulação não toca em metrics.json; o status leva a previsão
            // marcada com dry_run para a UI mostrar como "simulado".
            payload = [
                "generated_at": Dates.isoString(),
                "criadas": counts.created,
                "atualizadas": counts.updated,
                "protegidas": counts.protected,
                "bloqueadas": counts.blocked,
                "erros": counts.errors,
                "skipped": false,
                "dry_run": true
            ]
        } else {
            payload = metrics.dictionary
        }
        payload["organize"] = organize.dictionary
        payload["elapsed_s"] = elapsed
        StateStore.writeStatus(config: config, state: "ok", message: summary, metrics: payload)

        let hasCounts = counts.created > 0 || counts.updated > 0 || counts.blocked > 0 || counts.errors > 0
        let shouldNotify = !dryRun && (!metrics.skipped || hasCounts || organize.linkadas > 0)
        if shouldNotify {
            Notifier.post(
                title: "VaultAI",
                subtitle: "concluído em \(Int(elapsed.rounded()))s",
                message: summary,
                sound: "Glass"
            )
        }

        logger.log("=== PIPELINE CONCLUÍDO ===")
        logger.log(String(repeating: "=", count: 55))
        return PipelineResult(ok: true, summary: summary, elapsed: elapsed, error: nil)
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
