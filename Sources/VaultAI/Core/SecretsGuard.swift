import Foundation

/// Blocklist de segredos: senhas e chaves ficam só no Apple Notes.
/// Mesmos padrões do pipeline antigo, com allowlist para títulos inofensivos.
public struct SecretsGuard: Sendable {
    public var enabled: Bool
    public var extraFolders: Set<String>

    public init(enabled: Bool = true, extraFolders: Set<String> = []) {
        self.enabled = enabled
        self.extraFolders = Set(extraFolders.map { $0.lowercased() })
    }

    private static let defaultFolders: Set<String> = [
        "senhas", "passwords", "credentials", "credenciais", "secrets"
    ]

    private static let titlePatterns = [
        #"(?i)\bsenhas?\b"#,
        #"(?i)\bpassword\b"#,
        #"(?i)api[_\s-]?key"#,
        #"(?i)\bapikey\b"#,
        #"(?i)\bcredenciais?\b"#,
        #"(?i)\btoken\b"#,
        #"(?i)\bsecret\b"#,
        #"(?i)ANTHROPIC_API_KEY"#,
        #"(?i)OPENAI.*KEY"#,
        #"(?i)export\s+\w*API_KEY"#,
        #"(?i)github\s+token"#,
        #"(?i)aws\s+credenc"#
    ]

    private static let titleAllowlist = [
        #"(?i)passwordless"#,
        #"(?i)mudar\s+senha\s+usu[aá]rio"#,
        #"(?i)authenticateUser"#,
        #"(?i)after\s+booting\s+fails"#
    ]

    private static let bodyPatterns = [
        #"sk-[A-Za-z0-9]{10,}"#,
        #"AKIA[0-9A-Z]{16}"#,
        #"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----"#,
        #"(?i)aws_secret_access_key\s*=\s*\S+"#,
        #"(?i)export\s+\w*API_KEY\s*=\s*['"]?[A-Za-z0-9_\-]{8,}"#,
        #"(?i)(?:password|senha)\s*[:=]\s*[^\s\"']{4,}"#
    ]

    private static let compiledTitle = compile(titlePatterns)
    private static let compiledAllow = compile(titleAllowlist)
    private static let compiledBody = compile(bodyPatterns)

    public func check(title: String, body: String = "", folderSegments: [String] = []) -> (blocked: Bool, reason: String) {
        guard enabled else { return (false, "") }

        let blockedFolders = Self.defaultFolders.union(extraFolders)
        for segment in folderSegments {
            let value = segment.trimmingCharacters(in: .whitespaces).lowercased()
            if !value.isEmpty, blockedFolders.contains(value) {
                return (true, "pasta bloqueada: \(segment)")
            }
        }

        let allow = Self.compiledAllow.contains { matches($0, title) }
        if !allow, Self.compiledTitle.contains(where: { matches($0, title) }) {
            return (true, "título")
        }

        guard !body.isEmpty else { return (false, "") }
        let plain = body.replacingOccurrences(of: #"<[^>]+>"#, with: " ", options: .regularExpression)
        for regex in Self.compiledBody {
            if matches(regex, plain) || matches(regex, body) {
                return (true, "conteúdo")
            }
        }
        return (false, "")
    }

    private func matches(_ regex: NSRegularExpression, _ text: String) -> Bool {
        regex.firstMatch(in: text, range: NSRange(location: 0, length: (text as NSString).length)) != nil
    }

    private static func compile(_ patterns: [String]) -> [NSRegularExpression] {
        patterns.compactMap { try? NSRegularExpression(pattern: $0) }
    }
}
