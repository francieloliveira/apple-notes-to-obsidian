import Foundation

public extension SyncMetrics {
    var dictionary: [String: Any] {
        [
            "generated_at": Dates.isoString(),
            "criadas": criadas,
            "atualizadas": atualizadas,
            "protegidas": protegidas,
            "bloqueadas": bloqueadas,
            "erros": erros,
            "skipped": skipped
        ]
    }

    static var empty: SyncMetrics { SyncMetrics() }
}

public extension OrganizeMetrics {
    var dictionary: [String: Any] {
        [
            "generated_at": Dates.isoString(),
            "lixo": lixo,
            "linkadas": linkadas,
            "limpas": limpas,
            "mocs": mocs,
            "sem_sinal": semSinal,
            "sem_links": semLinks,
            "ja_linkadas": jaLinkadas,
            "max_inline_links": maxInlineLinks
        ]
    }
}

public enum StateStore {
    public static func snapshot(config: AppConfig) -> DashboardSnapshot {
        var snapshot = DashboardSnapshot()

        let status = JSONFile.object(at: config.statusURL)
        snapshot.rawState = JSONFile.string(status, "state", default: "idle")
        snapshot.message = JSONFile.string(status, "message")
        snapshot.updatedAt = Dates.parse(JSONFile.string(status, "updated_at"))
        snapshot.paused = FileManager.default.fileExists(atPath: config.pausedURL.path)

        let statusMetrics = JSONFile.dict(status, "metrics")
        let metricsFile = JSONFile.object(at: config.metricsURL)
        // Em caso de erro o status carrega as métricas mais recentes da tentativa;
        // em dry run as métricas do status são a previsão da simulação.
        snapshot.simulated = JSONFile.bool(statusMetrics, "dry_run")
        let preferStatus = (snapshot.rawState == "error" || snapshot.simulated) && !statusMetrics.isEmpty
        snapshot.sync = SyncMetrics.from(
            preferStatus ? statusMetrics : (metricsFile.isEmpty ? statusMetrics : metricsFile)
        )

        let organizeStatus = JSONFile.dict(statusMetrics, "organize")
        snapshot.organize = organizeStatus.isEmpty
            ? OrganizeMetrics.from(JSONFile.object(at: config.organizeMetricsURL))
            : OrganizeMetrics.from(organizeStatus)

        let elapsed = JSONFile.double(statusMetrics, "elapsed_s")
        snapshot.elapsed = elapsed > 0 ? elapsed : snapshot.sync.elapsed

        let progress = JSONFile.object(at: config.progressURL)
        let total = JSONFile.int(progress, "total")
        if total > 0 {
            snapshot.progress = ProgressInfo(
                current: JSONFile.int(progress, "current"),
                total: total,
                criadas: JSONFile.int(progress, "criadas"),
                atualizadas: JSONFile.int(progress, "atualizadas"),
                erros: JSONFile.int(progress, "erros")
            )
        }

        let state = JSONFile.object(at: config.stateFileURL)
        if let epoch = (state["_last_sync_epoch"] as? NSNumber)?.doubleValue, epoch > 0 {
            snapshot.lastSyncEpoch = Date(timeIntervalSince1970: epoch)
        }
        return snapshot
    }

    public static func writeStatus(
        config: AppConfig,
        state: String,
        message: String,
        metrics: [String: Any]? = nil
    ) {
        let object: [String: Any] = [
            "state": state,
            "message": message,
            "updated_at": Dates.isoString(),
            "metrics": metrics ?? [:]
        ]
        JSONFile.write(object, to: config.statusURL)
    }

    public static func writeProgress(config: AppConfig, _ progress: ProgressInfo) {
        let object: [String: Any] = [
            "current": progress.current,
            "total": progress.total,
            "criadas": progress.criadas,
            "atualizadas": progress.atualizadas,
            "erros": progress.erros
        ]
        JSONFile.write(object, to: config.progressURL)
    }

    public static func clearProgress(config: AppConfig) {
        JSONFile.remove(config.progressURL)
    }

    public static func writeEmptyMetrics(config: AppConfig) {
        JSONFile.write(SyncMetrics.empty.dictionary, to: config.metricsURL)
    }

    /// Corrige o status quando o app foi encerrado no meio de um sync:
    /// o status fica "running" e o lock vira órfão, travando a UI e os
    /// próximos syncs. Marca como interrompido e libera o lock.
    @discardableResult
    public static func reconcileInterruptedRun(config: AppConfig) -> Bool {
        let status = JSONFile.object(at: config.statusURL)
        guard JSONFile.string(status, "state") == "running" else { return false }
        guard !PipelineLock.isRunning() else { return false }

        PipelineLock.clearIfStale()
        clearProgress(config: config)
        writeStatus(config: config, state: "error", message: "Sync interrompido")
        return true
    }

    public static func readMetrics(config: AppConfig) -> SyncMetrics {
        return SyncMetrics.from(JSONFile.object(at: config.metricsURL))
    }

    public static func readOrganizeMetrics(config: AppConfig) -> OrganizeMetrics {
        return OrganizeMetrics.from(JSONFile.object(at: config.organizeMetricsURL))
    }

    public static func isPaused(config: AppConfig) -> Bool {
        FileManager.default.fileExists(atPath: config.pausedURL.path)
    }

    public static func setPaused(config: AppConfig, _ paused: Bool) {
        let fm = FileManager.default
        if paused {
            try? fm.createDirectory(at: config.stateURL, withIntermediateDirectories: true)
            fm.createFile(atPath: config.pausedURL.path, contents: nil)
        } else {
            try? fm.removeItem(at: config.pausedURL)
        }
    }
}
