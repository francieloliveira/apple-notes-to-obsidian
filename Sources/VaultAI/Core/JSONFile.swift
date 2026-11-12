import Foundation

/// Leitura e escrita atômicas de JSON, no mesmo formato dos arquivos de estado
/// que o pipeline Python já usava em `~/.vault`.
public enum JSONFile {
    public static func any(at url: URL) -> Any? {
        guard let data = try? Data(contentsOf: url), !data.isEmpty else { return nil }
        return try? JSONSerialization.jsonObject(with: data, options: [.fragmentsAllowed])
    }

    public static func object(at url: URL) -> [String: Any] {
        (any(at: url) as? [String: Any]) ?? [:]
    }

    public static func array(at url: URL) -> [Any] {
        (any(at: url) as? [Any]) ?? []
    }

    @discardableResult
    public static func write(_ object: Any, to url: URL) -> Bool {
        do {
            let dir = url.deletingLastPathComponent()
            try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
            let data = try JSONSerialization.data(
                withJSONObject: object,
                options: [.prettyPrinted, .withoutEscapingSlashes]
            )
            try data.write(to: url, options: .atomic)
            return true
        } catch {
            return false
        }
    }

    public static func remove(_ url: URL) {
        try? FileManager.default.removeItem(at: url)
    }

    // MARK: - Acesso tipado tolerante

    public static func string(_ dict: [String: Any], _ key: String, default def: String = "") -> String {
        if let v = dict[key] as? String { return v }
        if let v = dict[key] as? NSNumber { return v.stringValue }
        return def
    }

    public static func int(_ dict: [String: Any], _ key: String, default def: Int = 0) -> Int {
        if let v = dict[key] as? Int { return v }
        if let v = dict[key] as? NSNumber { return v.intValue }
        if let v = dict[key] as? String, let n = Int(v) { return n }
        return def
    }

    public static func double(_ dict: [String: Any], _ key: String, default def: Double = 0) -> Double {
        if let v = dict[key] as? Double { return v }
        if let v = dict[key] as? NSNumber { return v.doubleValue }
        if let v = dict[key] as? String, let n = Double(v) { return n }
        return def
    }

    public static func bool(_ dict: [String: Any], _ key: String, default def: Bool = false) -> Bool {
        if let v = dict[key] as? Bool { return v }
        if let v = dict[key] as? NSNumber { return v.boolValue }
        return def
    }

    public static func dict(_ dict: [String: Any], _ key: String) -> [String: Any] {
        (dict[key] as? [String: Any]) ?? [:]
    }

    public static func stringArray(_ dict: [String: Any], _ key: String) -> [String] {
        (dict[key] as? [String]) ?? []
    }
}
