import Foundation

/// Regras de edição da taxonomia de domínios que geram os MOCs.
///
/// Fica separado da UI para poder ser testado sem abrir a janela de Ajustes.
public enum DomainCatalog {
    public enum ValidationError: Equatable {
        case emptyName
        case invalidCharacters
        case duplicate(String)
    }

    /// O nome vira nome de arquivo do MOC: minúsculo, sem espaços duplicados.
    public static func normalizeName(_ raw: String) -> String {
        raw
            .trimmingCharacters(in: .whitespacesAndNewlines)
            .lowercased()
            .replacingOccurrences(of: "\\s+", with: " ", options: .regularExpression)
    }

    /// Aceita vírgula, ponto e vírgula ou "·" como separador, remove repetidas
    /// e normaliza para minúsculas (as tags do Apple Notes são minúsculas).
    public static func parseKeywords(_ raw: String) -> [String] {
        var seen = Set<String>()
        return raw
            .split(whereSeparator: { $0 == "," || $0 == ";" || $0 == "·" })
            .map { $0.trimmingCharacters(in: .whitespacesAndNewlines).lowercased() }
            .filter { !$0.isEmpty && seen.insert($0).inserted }
    }

    public static func validate(
        name: String,
        original: String?,
        existing: [String: [String]]
    ) -> ValidationError? {
        guard !name.isEmpty else { return .emptyName }
        if name.contains("/") || name.contains("\\") || name.contains(":") {
            return .invalidCharacters
        }
        if name != original, existing[name] != nil {
            return .duplicate(name)
        }
        return nil
    }

    /// Aplica a edição no dicionário. Renomear remove a chave antiga.
    @discardableResult
    public static func apply(
        name rawName: String,
        keywordsText: String,
        original: String?,
        to domains: inout [String: [String]]
    ) -> ValidationError? {
        let name = normalizeName(rawName)
        if let error = validate(name: name, original: original, existing: domains) {
            return error
        }
        let keywords = parseKeywords(keywordsText)
        if let original, original != name {
            domains.removeValue(forKey: original)
        }
        domains[name] = keywords
        return nil
    }
}
