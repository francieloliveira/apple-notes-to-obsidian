import Foundation

public struct SyncMetrics: Equatable, Sendable {
    public var criadas = 0
    public var atualizadas = 0
    public var protegidas = 0
    public var bloqueadas = 0
    public var erros = 0
    public var skipped = true
    public var generatedAt: Date?
    public var elapsed: Double?

    public init() {}

    public static func from(_ dict: [String: Any]) -> SyncMetrics {
        var m = SyncMetrics()
        m.criadas = JSONFile.int(dict, "criadas")
        m.atualizadas = JSONFile.int(dict, "atualizadas")
        m.protegidas = JSONFile.int(dict, "protegidas")
        m.bloqueadas = JSONFile.int(dict, "bloqueadas")
        m.erros = JSONFile.int(dict, "erros")
        m.skipped = JSONFile.bool(dict, "skipped", default: true)
        m.elapsed = JSONFile.double(dict, "elapsed_s")
        m.generatedAt = Dates.parse(JSONFile.string(dict, "generated_at"))
        return m
    }

    public var totalChanged: Int { criadas + atualizadas }
}

public struct OrganizeMetrics: Equatable, Sendable {
    public var linkadas = 0
    public var limpas = 0
    public var mocs = 0
    public var lixo = 0
    public var semSinal = 0
    public var semLinks = 0
    public var jaLinkadas = 0
    public var maxInlineLinks = 0

    public init() {}

    public static func from(_ dict: [String: Any]) -> OrganizeMetrics {
        var m = OrganizeMetrics()
        m.linkadas = JSONFile.int(dict, "linkadas")
        m.limpas = JSONFile.int(dict, "limpas")
        m.mocs = JSONFile.int(dict, "mocs")
        m.lixo = JSONFile.int(dict, "lixo")
        m.semSinal = JSONFile.int(dict, "sem_sinal")
        m.semLinks = JSONFile.int(dict, "sem_links")
        m.jaLinkadas = JSONFile.int(dict, "ja_linkadas")
        m.maxInlineLinks = JSONFile.int(dict, "max_inline_links")
        return m
    }
}

public struct ProgressInfo: Equatable, Sendable {
    public var current: Int
    public var total: Int
    public var criadas: Int
    public var atualizadas: Int
    public var erros: Int

    public init(current: Int, total: Int, criadas: Int = 0, atualizadas: Int = 0, erros: Int = 0) {
        self.current = current
        self.total = total
        self.criadas = criadas
        self.atualizadas = atualizadas
        self.erros = erros
    }

    public var percent: Int? {
        guard total > 0 else { return nil }
        return max(0, min(100, Int((Double(current) / Double(total) * 100).rounded())))
    }
}

public enum DisplayState: String, Sendable {
    case ok
    case sincronizando
    case pausa
    case erro
    case idle

    public var title: String {
        switch self {
        case .ok: return "Atualizado"
        case .sincronizando: return "Sincronizando"
        case .pausa: return "Pausado"
        case .erro: return "Erro"
        case .idle: return "Pronto"
        }
    }
}

public struct DashboardSnapshot: Sendable {
    public var rawState: String = "idle"
    public var message: String = ""
    public var updatedAt: Date?
    public var elapsed: Double?
    public var progress: ProgressInfo?
    public var sync = SyncMetrics()
    public var organize = OrganizeMetrics()
    public var paused = false
    public var lastSyncEpoch: Date?

    public init() {}

    public var displayState: DisplayState {
        if rawState == "running" { return .sincronizando }
        if rawState == "error" { return .erro }
        if paused { return .pausa }
        if rawState == "ok" { return .ok }
        return .idle
    }

    public var percent: Int? { progress?.percent }

    public var lastSync: Date? { lastSyncEpoch ?? updatedAt }

    public var activity: String {
        let text = message
        let lowered = text.lowercased()
        let stage: String
        let pending: String
        if lowered.contains("organiz") {
            stage = "Organizando"
            pending = "Organizando o vault…"
        } else if lowered.contains("simul") {
            stage = "Simulando"
            pending = "Simulando o sync…"
        } else if lowered.contains("notes") || lowered.contains("sincron") {
            stage = "Lendo notas"
            pending = "Lendo notas do Apple Notes…"
        } else {
            stage = ""
            pending = "Preparando o sync…"
        }

        switch displayState {
        case .sincronizando:
            if let pct = percent { return "\(stage.isEmpty ? "Sync" : stage) · \(pct)%" }
            return pending
        case .pausa:
            return "Sync automático pausado"
        case .erro:
            return text.isEmpty ? "Sync falhou" : text
        case .ok:
            if let pct = percent, pct < 100 { return "Parcial · \(pct)%" }
            return "Vault atualizado"
        case .idle:
            return "Aguardando o próximo sync"
        }
    }

    public var subtitle: String {
        switch displayState {
        case .sincronizando:
            return message.isEmpty ? "Lendo o Apple Notes e gravando no vault" : message
        case .pausa:
            return "Retome para voltar a sincronizar automaticamente"
        case .erro:
            return "Abra o log para ver o detalhe"
        case .ok:
            return message.isEmpty ? "Tudo em dia" : message
        case .idle:
            return "Seu vault está pronto para a próxima sincronização"
        }
    }
}

public enum Dates {
    public static let iso: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return f
    }()

    public static let isoNoFraction: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime]
        return f
    }()

    public static func parse(_ raw: String) -> Date? {
        guard !raw.isEmpty else { return nil }
        if let d = iso.date(from: raw) { return d }
        if let d = isoNoFraction.date(from: raw) { return d }

        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.dateFormat = "yyyy-MM-dd'T'HH:mm:ss.SSSSSS"
        if let d = formatter.date(from: raw) { return d }
        formatter.dateFormat = "yyyy-MM-dd'T'HH:mm:ss"
        return formatter.date(from: raw)
    }

    public static func isoString(_ date: Date = Date(), timeZone: TimeZone = .current) -> String {
        let f = ISO8601DateFormatter()
        f.timeZone = timeZone
        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return f.string(from: date)
    }

    public static func logTimestamp(_ date: Date = Date()) -> String {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.dateFormat = "yyyy-MM-dd HH:mm:ss"
        return f.string(from: date)
    }

    public static func relative(_ date: Date?, now: Date = Date()) -> String {
        guard let date else { return "nunca" }
        let seconds = Int(now.timeIntervalSince(date))
        if seconds < 0 || seconds < 60 { return "agora mesmo" }
        if seconds < 3600 { return "há \(seconds / 60) min" }
        if seconds < 86_400 { return "há \(seconds / 3600)h" }
        return "há \(seconds / 86_400)d"
    }

    public static func normalize(_ raw: String) -> String {
        raw.lowercased()
            .split(whereSeparator: { $0.isWhitespace })
            .joined(separator: " ")
    }
}
