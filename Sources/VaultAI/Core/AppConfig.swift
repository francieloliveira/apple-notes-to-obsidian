import Foundation

/// Configuração do VaultAI.
///
/// Ordem de carregamento:
/// 1. Padrões equivalentes ao antigo `config.example.py`.
/// 2. `config.py` legado (apenas atribuições simples), quando encontrado.
/// 3. `~/.vault/config.json` (fonte nativa, editável em Ajustes).
/// 4. Variáveis de ambiente (`VAULT_PATH`, `VAULTAI_HOME`, `VAULT_SYNC_ROOT`).
public struct AppConfig: Sendable, Equatable {
    public var vaultPath: String
    public var stateDir: String
    public var syncRoot: String
    public var flatFolders: [String]
    public var fetchWorkers: Int
    public var checkpointEvery: Int
    public var timezone: String
    public var secretsEnabled: Bool
    public var secretFolders: [String]
    public var lixoDir: String
    public var minContentChars: Int
    public var maxInlineLinks: Int
    public var minTitleChars: Int
    public var domainKeywords: [String: [String]]
    public var pipelineIntervalSecs: Int
    public var pollSecs: Int
    public var autoSyncOnLaunch: Bool

    public init(
        vaultPath: String = "~/VaultAI",
        stateDir: String = "~/.vault",
        syncRoot: String = "",
        flatFolders: [String] = ["notes", "notas", "todas (icloud)", "all icloud", "icloud"],
        fetchWorkers: Int = 8,
        checkpointEvery: Int = 50,
        timezone: String = "America/Sao_Paulo",
        secretsEnabled: Bool = true,
        secretFolders: [String] = ["senhas", "passwords"],
        lixoDir: String = "_lixo",
        minContentChars: Int = 0,
        maxInlineLinks: Int = 5,
        minTitleChars: Int = 5,
        domainKeywords: [String: [String]] = AppConfig.defaultDomains,
        pipelineIntervalSecs: Int = 1800,
        pollSecs: Int = 15,
        autoSyncOnLaunch: Bool = true
    ) {
        self.vaultPath = vaultPath
        self.stateDir = stateDir
        self.syncRoot = syncRoot
        self.flatFolders = flatFolders
        self.fetchWorkers = fetchWorkers
        self.checkpointEvery = checkpointEvery
        self.timezone = timezone
        self.secretsEnabled = secretsEnabled
        self.secretFolders = secretFolders
        self.lixoDir = lixoDir
        self.minContentChars = minContentChars
        self.maxInlineLinks = maxInlineLinks
        self.minTitleChars = minTitleChars
        self.domainKeywords = domainKeywords
        self.pipelineIntervalSecs = pipelineIntervalSecs
        self.pollSecs = pollSecs
        self.autoSyncOnLaunch = autoSyncOnLaunch
    }

    public static let defaultDomains: [String: [String]] = [
        "tech": ["python", "java", "javascript", "docker", "kubernetes"],
        "cloud": ["aws", "azure", "gcp", "lambda", "s3"],
        "ai": ["llm", "machine learning", "transformer", "embedding"],
        "devops": ["ci/cd", "pipeline", "deploy", "terraform"],
        "sql": ["select", "postgresql", "mysql", "sqlite"],
        "git": ["git commit", "git push", "github", "branch", "pull request"],
        "scrum": ["scrum", "sprint", "backlog", "user story"]
    ]

    // MARK: - URLs derivadas

    public var vaultURL: URL { Paths.expand(vaultPath) }
    public var stateURL: URL { Paths.expand(stateDir) }

    public var syncLogURL: URL { stateURL.appendingPathComponent("sync.log") }
    public var organizeLogURL: URL { stateURL.appendingPathComponent("organize.log") }
    public var pipelineLogURL: URL { stateURL.appendingPathComponent("pipeline.log") }
    public var statusURL: URL { stateURL.appendingPathComponent("status.json") }
    public var progressURL: URL { stateURL.appendingPathComponent("progress.json") }
    public var metricsURL: URL { stateURL.appendingPathComponent("metrics.json") }
    public var organizeMetricsURL: URL { stateURL.appendingPathComponent("organize_metrics.json") }
    public var stateFileURL: URL { stateURL.appendingPathComponent("notes_state.json") }
    public var idsURL: URL { stateURL.appendingPathComponent("notes_ids.json") }
    public var dirtyURL: URL { stateURL.appendingPathComponent("vault_dirty.json") }
    public var checkpointURL: URL { stateURL.appendingPathComponent("sync_checkpoint.json") }
    public var pathsURL: URL { stateURL.appendingPathComponent("note_paths.json") }
    public var pausedURL: URL { stateURL.appendingPathComponent("sync_paused") }
    public var configURL: URL { stateURL.appendingPathComponent("config.json") }

    public var intervalMinutes: Int { max(1, pipelineIntervalSecs / 60) }

    public var flatFolderSet: Set<String> { Set(flatFolders.map { $0.lowercased() }) }

    public var timeZone: TimeZone { TimeZone(identifier: timezone) ?? .current }
}

public enum Paths {
    public static func expand(_ path: String) -> URL {
        URL(fileURLWithPath: (path as NSString).expandingTildeInPath)
    }

    public static func relativePath(of url: URL, in root: URL) -> String {
        let rootPath = root.standardizedFileURL.path
        let path = url.standardizedFileURL.path
        guard path.hasPrefix(rootPath) else { return path }
        var rel = String(path.dropFirst(rootPath.count))
        while rel.hasPrefix("/") { rel.removeFirst() }
        return rel
    }
}

// MARK: - Carregamento

public enum ConfigStore {
    public static func load(environment: [String: String] = ProcessInfo.processInfo.environment) -> AppConfig {
        var config = AppConfig()

        if let stateDir = environment["VAULTAI_STATE_DIR"], !stateDir.isEmpty {
            config.stateDir = stateDir
        }

        if let legacy = LegacyPythonConfig.load() {
            legacy.apply(to: &config)
        }

        let json = JSONFile.object(at: config.configURL)
        if !json.isEmpty {
            apply(json, to: &config)
        }

        if let value = environment["VAULT_PATH"], !value.isEmpty {
            config.vaultPath = value
        }
        if let value = environment["VAULT_SYNC_ROOT"] {
            config.syncRoot = value
        }
        if let value = environment["VAULTAI_STATE_DIR"], !value.isEmpty {
            config.stateDir = value
        }

        return config
    }

    public static func save(_ config: AppConfig) {
        var dict: [String: Any] = [:]
        dict["vaultPath"] = config.vaultPath
        dict["stateDir"] = config.stateDir
        dict["syncRoot"] = config.syncRoot
        dict["flatFolders"] = config.flatFolders
        dict["fetchWorkers"] = config.fetchWorkers
        dict["checkpointEvery"] = config.checkpointEvery
        dict["timezone"] = config.timezone
        dict["secretsEnabled"] = config.secretsEnabled
        dict["secretFolders"] = config.secretFolders
        dict["lixoDir"] = config.lixoDir
        dict["minContentChars"] = config.minContentChars
        dict["maxInlineLinks"] = config.maxInlineLinks
        dict["minTitleChars"] = config.minTitleChars
        dict["domainKeywords"] = config.domainKeywords
        dict["pipelineIntervalSecs"] = config.pipelineIntervalSecs
        dict["pollSecs"] = config.pollSecs
        dict["autoSyncOnLaunch"] = config.autoSyncOnLaunch
        JSONFile.write(dict, to: config.configURL)
    }

    private static func apply(_ dict: [String: Any], to config: inout AppConfig) {
        if let v = dict["vaultPath"] as? String, !v.isEmpty { config.vaultPath = v }
        if let v = dict["stateDir"] as? String, !v.isEmpty { config.stateDir = v }
        if let v = dict["syncRoot"] as? String { config.syncRoot = v }
        if let v = dict["flatFolders"] as? [String] { config.flatFolders = v }
        if let v = dict["fetchWorkers"] as? Int { config.fetchWorkers = max(1, v) }
        if let v = dict["checkpointEvery"] as? Int { config.checkpointEvery = max(1, v) }
        if let v = dict["timezone"] as? String { config.timezone = v }
        if let v = dict["secretsEnabled"] as? Bool { config.secretsEnabled = v }
        if let v = dict["secretFolders"] as? [String] { config.secretFolders = v }
        if let v = dict["lixoDir"] as? String { config.lixoDir = v }
        if let v = dict["minContentChars"] as? Int { config.minContentChars = max(0, v) }
        if let v = dict["maxInlineLinks"] as? Int { config.maxInlineLinks = max(0, v) }
        if let v = dict["minTitleChars"] as? Int { config.minTitleChars = max(1, v) }
        if let v = dict["domainKeywords"] as? [String: [String]] { config.domainKeywords = v }
        if let v = dict["pipelineIntervalSecs"] as? Int { config.pipelineIntervalSecs = max(60, v) }
        if let v = dict["pollSecs"] as? Int { config.pollSecs = max(1, v) }
        if let v = dict["autoSyncOnLaunch"] as? Bool { config.autoSyncOnLaunch = v }
    }
}

/// Lê apenas atribuições simples do `config.py` legado.
enum LegacyPythonConfig {
    struct Values {
        var vaultPath: String?
        var vaulatiHome: String?
        var interval: Int?
        var fetchWorkers: Int?
        var checkpointEvery: Int?
        var pollSecs: Int?
        var timezone: String?

        func apply(to config: inout AppConfig) {
            if let v = vaultPath { config.vaultPath = v }
            if let v = vaulatiHome { config.stateDir = v }
            if let v = interval { config.pipelineIntervalSecs = max(60, v) }
            if let v = fetchWorkers { config.fetchWorkers = max(1, v) }
            if let v = checkpointEvery { config.checkpointEvery = max(1, v) }
            if let v = pollSecs { config.pollSecs = max(1, v) }
            if let v = timezone { config.timezone = v }
        }
    }

    static func candidates() -> [URL] {
        var urls: [URL] = []
        let env = ProcessInfo.processInfo.environment
        if let home = env["VAULTAI_HOME"], !home.isEmpty {
            urls.append(Paths.expand(home).appendingPathComponent("config.py"))
        }
        let home = FileManager.default.homeDirectoryForCurrentUser
        urls.append(home.appendingPathComponent("IntegraNotesMacObsidian/config.py"))
        urls.append(URL(fileURLWithPath: FileManager.default.currentDirectoryPath).appendingPathComponent("config.py"))
        return urls
    }

    static func load() -> Values? {
        guard let url = candidates().first(where: { FileManager.default.fileExists(atPath: $0.path) }),
              let text = try? String(contentsOf: url, encoding: .utf8) else { return nil }

        var values = Values()
        let pattern = #"(?m)^\s*([A-Z][A-Z0-9_]*)\s*=\s*(.+?)\s*$"#
        guard let regex = try? NSRegularExpression(pattern: pattern) else { return values }
        let ns = text as NSString
        for match in regex.matches(in: text, range: NSRange(location: 0, length: ns.length)) {
            guard match.numberOfRanges == 3 else { continue }
            let key = ns.substring(with: match.range(at: 1))
            var raw = ns.substring(with: match.range(at: 2))
            if raw.contains("os.getenv") || raw.hasPrefix("[") || raw.hasPrefix("{") { continue }
            if let hash = raw.range(of: "  #") { raw = String(raw[..<hash.lowerBound]) }
            raw = raw.trimmingCharacters(in: .whitespaces)
            let value = unquote(raw)

            switch key {
            case "VAULT_PATH": values.vaultPath = value
            case "VAULTAI_HOME": values.vaulatiHome = value
            case "PIPELINE_INTERVAL_SECS": values.interval = Int(value)
            case "FETCH_WORKERS": values.fetchWorkers = Int(value)
            case "CHECKPOINT_EVERY": values.checkpointEvery = Int(value)
            case "POLL_SECS": values.pollSecs = Int(value)
            case "TIMEZONE": values.timezone = value
            default: break
            }
        }
        return values
    }

    private static func unquote(_ raw: String) -> String {
        var value = raw
        if (value.hasPrefix("\"") && value.hasSuffix("\"")) ||
            (value.hasPrefix("'") && value.hasSuffix("'")) {
            value.removeFirst()
            value.removeLast()
        }
        return value
    }
}
