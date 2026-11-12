import Foundation

public enum VaultError: LocalizedError {
    case fileExists(URL)
    case fileOperation(String)

    public var errorDescription: String? {
        switch self {
        case .fileExists(let url): return "Já existe um arquivo que não é do VaultAI: \(url.lastPathComponent)"
        case .fileOperation(let message): return message
        }
    }
}

public enum SecretRemoval: Equatable {
    case removed(String)
    case none
    case failed
}

/// Política B de nomes: arquivo legível, sem hash, aliases preservados.
public enum VaultPaths {
    private static let filenameMax = 80
    private static let noteIDRegex = try! NSRegularExpression(
        pattern: #"(?m)^note_id:\s*"?([^"\n]+)"?\s*$"#
    )
    private static let hashSuffixRegex = try! NSRegularExpression(
        pattern: #"_[0-9a-f]{8}$"#,
        options: [.caseInsensitive]
    )
    private static let aliasItemRegex = try! NSRegularExpression(
        pattern: #"^\s+-\s*"?([^"\n]+)"?\s*$"#
    )
    private static let imageExtRegex = try! NSRegularExpression(
        pattern: #"\.(png|jpg|jpeg|gif|webp|bmp|svg)$"#,
        options: [.caseInsensitive]
    )
    private static let attachmentRefRegex = try! NSRegularExpression(
        pattern: #"!\[\[(?:_attachments/)?([^\]\r\n|#/\\]+)(?:[#|][^\]]*)?\]\]"#
    )

    // MARK: - Nomes

    public static func sanitizeTitle(_ title: String) -> String {
        var t = title.trimmingCharacters(in: .whitespacesAndNewlines)
        t = t.replacingOccurrences(of: "\u{2026}", with: "")
        t = t.replacingOccurrences(of: "…", with: "")
        t = t.replacingOccurrences(of: #"\s+"#, with: " ", options: .regularExpression)

        if t.range(of: #"^https?://"#, options: [.regularExpression, .caseInsensitive]) != nil {
            t = urlToFilenameSlug(t)
        } else {
            t = replaceInvalidCharacters(t)
            t = t.replacingOccurrences(of: #"-+"#, with: "-", options: .regularExpression)
            t = trimEdges(t)
        }

        if t.count > filenameMax {
            t = String(t.prefix(filenameMax))
            t = trimEdges(t)
        }
        return t.isEmpty ? "sem-nome" : t
    }

    public static func urlToFilenameSlug(_ url: String) -> String {
        guard let comps = URLComponents(string: url.trimmingCharacters(in: .whitespaces)),
              let host = comps.host, !host.isEmpty else {
            return sanitizeTitle(url)
        }
        let netloc = host + (comps.port.map { ":\($0)" } ?? "")
        var slug = netloc.replacingOccurrences(of: ":", with: "-")
        let path = comps.path.trimmingCharacters(in: CharacterSet(charactersIn: "/"))
            .replacingOccurrences(of: "/", with: "-")
        if !path.isEmpty { slug += "-\(path)" }
        slug = replaceInvalidCharacters(slug)
        slug = slug.replacingOccurrences(of: #"-+"#, with: "-", options: .regularExpression)
        slug = trimEdges(slug)
        if slug.count > filenameMax {
            slug = trimEdges(String(slug.prefix(filenameMax)))
        }
        return slug.isEmpty ? "url" : slug
    }

    private static func replaceInvalidCharacters(_ text: String) -> String {
        let invalid = CharacterSet(charactersIn: "\\/*?:\"<>|\n\r\t")
        return text.unicodeScalars.map { invalid.contains($0) ? "-" : String($0) }.joined()
    }

    private static func trimEdges(_ text: String) -> String {
        text.trimmingCharacters(in: CharacterSet(charactersIn: ". -"))
    }

    public static func folderLabel(_ segments: [String], flatFolders: Set<String>) -> String {
        guard !segments.isEmpty else { return "" }
        if segments.count == 1, flatFolders.contains(segments[0].lowercased()) {
            return segments[0]
        }
        return segments.last ?? ""
    }

    public static func uniqueFilename(
        directory: URL,
        title: String,
        segments: [String],
        noteID: String,
        flatFolders: Set<String>
    ) -> String {
        let base = sanitizeTitle(title)
        let folder = sanitizeTitle(folderLabel(segments, flatFolders: flatFolders))

        var candidates = ["\(base).md"]
        if !folder.isEmpty, folder.lowercased() != base.lowercased() {
            candidates.append("\(base) (\(folder)).md")
        }
        for index in 2..<25 {
            if folder.isEmpty {
                candidates.append("\(base) \(index).md")
            } else {
                candidates.append("\(base) (\(folder)) \(index).md")
            }
        }

        for candidate in candidates {
            let url = directory.appendingPathComponent(candidate)
            if !FileManager.default.fileExists(atPath: url.path) { return candidate }
            if isOurs(url), noteIDAtPath(url) == noteID { return candidate }
        }
        return candidates.last ?? "\(base).md"
    }

    // MARK: - Leitura

    public static func readHead(_ url: URL, limit: Int = 1200) -> String {
        guard let handle = try? FileHandle(forReadingFrom: url) else { return "" }
        defer { try? handle.close() }
        let data = (try? handle.read(upToCount: limit)) ?? Data()
        return String(data: data, encoding: .utf8) ?? ""
    }

    public static func isOurs(_ url: URL) -> Bool {
        readHead(url, limit: 500).contains("source: Apple Notes")
    }

    public static func noteIDAtPath(_ url: URL) -> String {
        extractNoteID(readHead(url))
    }

    public static func extractNoteID(_ raw: String) -> String {
        let ns = raw as NSString
        guard let match = noteIDRegex.firstMatch(in: raw, range: NSRange(location: 0, length: ns.length)),
              match.numberOfRanges > 1 else { return "" }
        return ns.substring(with: match.range(at: 1)).trimmingCharacters(in: .whitespaces)
    }

    public static func parseAliases(_ raw: String) -> [String] {
        var aliases: [String] = []
        var inAliases = false
        for line in raw.components(separatedBy: "\n") {
            if line.trimmingCharacters(in: .whitespaces) == "aliases:" {
                inAliases = true
                continue
            }
            guard inAliases else { continue }
            let ns = line as NSString
            if let match = aliasItemRegex.firstMatch(in: line, range: NSRange(location: 0, length: ns.length)),
               match.numberOfRanges > 1 {
                aliases.append(ns.substring(with: match.range(at: 1)).trimmingCharacters(in: .whitespaces))
            } else if line.hasPrefix("  ") || line.hasPrefix("\t") {
                continue
            } else {
                break
            }
        }
        return aliases
    }

    public static func mergeAliases(
        existing: [String],
        oldStem: String?,
        oldTitle: String?,
        newTitle: String
    ) -> [String] {
        var result = existing
        for candidate in [oldStem, oldTitle] {
            guard let candidate else { continue }
            let c = candidate.trimmingCharacters(in: .whitespaces)
            if c.isEmpty || c == newTitle || result.contains(c) { continue }
            result.append(c)
        }
        return result
    }

    public static func formatAliasesYAML(_ aliases: [String]) -> String {
        guard !aliases.isEmpty else { return "" }
        return "aliases:\n" + aliases.map { "  - \"\($0)\"" }.joined(separator: "\n") + "\n"
    }

    public static func stripHashSuffix(_ stem: String) -> String {
        let ns = stem as NSString
        return hashSuffixRegex.stringByReplacingMatches(
            in: stem,
            range: NSRange(location: 0, length: ns.length),
            withTemplate: ""
        )
    }

    // MARK: - Resolução de caminho

    public static func scanVaultForNoteID(
        _ noteID: String,
        vaultRoot: URL,
        skipDirs: Set<String> = ["_lixo", "_index", "_attachments"]
    ) -> URL? {
        guard let enumerator = FileManager.default.enumerator(
            at: vaultRoot,
            includingPropertiesForKeys: [.isRegularFileKey],
            options: [.skipsHiddenFiles]
        ) else { return nil }

        for case let url as URL in enumerator {
            guard url.pathExtension.lowercased() == "md" else { continue }
            let relative = Paths.relativePath(of: url, in: vaultRoot)
            let parts = relative.split(separator: "/").map(String.init)
            if parts.contains(where: { skipDirs.contains($0) }) { continue }
            if extractNoteID(readHead(url)) == noteID { return url }
        }
        return nil
    }

    public static func resolveHumanNotePath(
        title: String,
        segments: [String],
        noteID: String,
        pathsMap: [String: String],
        vaultRoot: URL,
        targetDir: URL,
        flatFolders: Set<String>,
        dryRun: Bool
    ) throws -> (url: URL, aliases: [String]) {
        let filename = uniqueFilename(
            directory: targetDir,
            title: title,
            segments: segments,
            noteID: noteID,
            flatFolders: flatFolders
        )
        let target = targetDir.appendingPathComponent(filename)
        var aliases: [String] = []

        var existing: URL?
        if let rel = pathsMap[noteID], !rel.isEmpty {
            let candidate = vaultRoot.appendingPathComponent(rel)
            if FileManager.default.fileExists(atPath: candidate.path) { existing = candidate }
        }
        if existing == nil {
            existing = scanVaultForNoteID(noteID, vaultRoot: vaultRoot)
        }

        if let existing, existing.standardizedFileURL != target.standardizedFileURL {
            let raw = (try? String(contentsOf: existing, encoding: .utf8)) ?? ""
            aliases = mergeAliases(
                existing: parseAliases(raw),
                oldStem: existing.deletingPathExtension().lastPathComponent,
                oldTitle: stripHashSuffix(existing.deletingPathExtension().lastPathComponent),
                newTitle: title
            )
            if !dryRun {
                try? FileManager.default.createDirectory(at: target.deletingLastPathComponent(), withIntermediateDirectories: true)
                do {
                    try FileManager.default.moveItem(at: existing, to: target)
                } catch {
                    throw VaultError.fileOperation("Não foi possível mover \(existing.lastPathComponent): \(error.localizedDescription)")
                }
            }
        } else if let existing {
            let raw = (try? String(contentsOf: existing, encoding: .utf8)) ?? ""
            aliases = parseAliases(raw)
        }

        let targetExists = FileManager.default.fileExists(atPath: target.path)
        let sameAsExisting = existing.map { $0.standardizedFileURL == target.standardizedFileURL } ?? false
        if targetExists, !isOurs(target), !sameAsExisting {
            throw VaultError.fileExists(target)
        }

        return (target, aliases)
    }

    // MARK: - Secrets

    public static func removeSecretFromVault(
        noteID: String,
        pathsMap: inout [String: String],
        vaultRoot: URL
    ) -> SecretRemoval {
        guard let rel = pathsMap[noteID] else { return .none }
        let file = vaultRoot.appendingPathComponent(rel)
        guard FileManager.default.fileExists(atPath: file.path) else {
            pathsMap.removeValue(forKey: noteID)
            return .none
        }
        guard let text = try? String(contentsOf: file, encoding: .utf8) else { return .failed }
        guard text.prefix(500).contains("source: Apple Notes") else {
            pathsMap.removeValue(forKey: noteID)
            return .none
        }

        do {
            try unlinkReferencedAttachments(note: file, text: text, vaultRoot: vaultRoot)
            try FileManager.default.removeItem(at: file)
        } catch {
            return .failed
        }
        pathsMap.removeValue(forKey: noteID)
        return .removed(rel)
    }

    private static func unlinkReferencedAttachments(note: URL, text: String, vaultRoot: URL) throws {
        let vault = vaultRoot.resolvingSymlinksInPath()
        let attachments = note.deletingLastPathComponent().appendingPathComponent("_attachments").resolvingSymlinksInPath()
        guard attachments.path.hasPrefix(vault.path) else { return }

        let ns = text as NSString
        let matches = attachmentRefRegex.matches(in: text, range: NSRange(location: 0, length: ns.length))
        var seen = Set<String>()
        for match in matches where match.numberOfRanges > 1 {
            let name = ns.substring(with: match.range(at: 1))
            guard !name.isEmpty, !seen.contains(name), name != ".", name != ".." else { continue }
            seen.insert(name)
            let target = attachments.appendingPathComponent(name).resolvingSymlinksInPath()
            guard target.path.hasPrefix(attachments.path), target.path != attachments.path else { continue }
            if FileManager.default.fileExists(atPath: target.path) {
                try? FileManager.default.removeItem(at: target)
            }
        }
    }

    // MARK: - Imagens

    public static func fixObsidianEmbeds(_ markdown: String, noteDir: URL?) -> String {
        let attachments = noteDir?.appendingPathComponent("_attachments")
        let ns = markdown as NSString
        var result = markdown

        let embedRegex = try! NSRegularExpression(pattern: #"!\[\[(.*?)\]\]"#, options: [.dotMatchesLineSeparators])
        let embedMatches = embedRegex.matches(in: markdown, range: NSRange(location: 0, length: ns.length))
        for match in embedMatches.reversed() where match.numberOfRanges > 1 {
            var inner = ns.substring(with: match.range(at: 1)).replacingOccurrences(of: "\\_", with: "_")
            if let attachments {
                let innerNS = inner as NSString
                let isImage = imageExtRegex.firstMatch(in: inner, range: NSRange(location: 0, length: innerNS.length)) != nil
                if isImage, !inner.hasPrefix("_attachments/") {
                    let bare = inner
                    if FileManager.default.fileExists(atPath: attachments.appendingPathComponent(bare).path) {
                        inner = "_attachments/\(bare)"
                    }
                }
            }
            let replacement = "![[\(inner)]]"
            if let range = Range(match.range, in: result) {
                result.replaceSubrange(range, with: replacement)
            }
        }

        let linkRegex = try! NSRegularExpression(pattern: #"(?<!!)\[\[(.*?)\]\]"#, options: [.dotMatchesLineSeparators])
        let linkNS = result as NSString
        let linkMatches = linkRegex.matches(in: result, range: NSRange(location: 0, length: linkNS.length))
        for match in linkMatches.reversed() where match.numberOfRanges > 1 {
            let inner = linkNS.substring(with: match.range(at: 1)).replacingOccurrences(of: "\\_", with: "_")
            if let range = Range(match.range, in: result) {
                result.replaceSubrange(range, with: "[[\(inner)]]")
            }
        }
        return result
    }
}
