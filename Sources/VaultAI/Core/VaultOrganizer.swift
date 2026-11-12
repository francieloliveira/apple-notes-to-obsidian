import Foundation

/// Porta do `organize_vault.py` — Modelo A:
/// links só por título citado ou tag em comum, MOC por domínio em `_index/`,
/// limpeza de notas vazias/genéricas para `_lixo/`.
public final class VaultOrganizer {
    private struct IndexedNote {
        let path: URL
        let stem: String
        let title: String
        let noteID: String
        let domains: Set<String>
        let tags: Set<String>
        let text: String
        let dirty: Bool
    }

    private let config: AppConfig
    private let logger: VaultLogger
    public var onProgress: ((Int, Int, String) -> Void)?
    public var onLog: ((String) -> Void)?

    private static let frontmatterCapture = try! NSRegularExpression(
        pattern: #"^\s*---[ \t]*[\r\n]+(.*?)[\r\n]---[ \t]*[\r\n]*"#,
        options: [.dotMatchesLineSeparators]
    )
    private static let frontmatterStrip = try! NSRegularExpression(
        pattern: #"^\s*---[ \t]*[\r\n]+.*?[\r\n]---[ \t]*[\r\n]*"#,
        options: [.dotMatchesLineSeparators]
    )
    private static let tagItem = try! NSRegularExpression(
        pattern: #"^\s+-\s*"?([^"\n]+)"?\s*$"#
    )
    private static let linksSection = try! NSRegularExpression(
        pattern: #"[\r\n]{2}---[\r\n]+## Links relacionados[\r\n]+.*$"#,
        options: [.dotMatchesLineSeparators]
    )

    public init(config: AppConfig, logger: VaultLogger) {
        self.config = config
        self.logger = logger
    }

    // MARK: - Entrada

    public func run(full: Bool, dryRun: Bool, verbose: Bool) -> Bool {
        try? FileManager.default.createDirectory(at: config.stateURL, withIntermediateDirectories: true)
        log("=== organize iniciado\(dryRun ? " [DRY RUN]" : "") ===")

        let vaultRoot = config.vaultURL
        let dirtyData = JSONFile.object(at: config.dirtyURL)
        var dirtyPaths = JSONFile.stringArray(dirtyData, "paths")

        if !full && dirtyPaths.isEmpty {
            log("Nenhuma nota nova/modificada. Nada a fazer.")
            return true
        }
        if !full {
            log("Processando delta: \(dirtyPaths.count) nota(s)")
        } else {
            log("Modo --full: processando vault inteiro")
        }

        if full {
            log("[ 0 ] Removendo seções ## Links relacionados antigas...")
            let cleaned = stripLinksSections(vaultRoot: vaultRoot, dryRun: dryRun)
            log("  → \(cleaned) arquivo(s) limpo(s)")
        }

        log("[ 1 ] Verificando lixo...")
        var lixoCount = 0
        let targets = dirtyPaths.isEmpty
            ? allMarkdown(in: vaultRoot)
            : dirtyPaths.map { URL(fileURLWithPath: $0) }

        for file in targets {
            guard FileManager.default.fileExists(atPath: file.path) else { continue }
            let relative = Paths.relativePath(of: file, in: vaultRoot)
            let parts = relative.split(separator: "/").map(String.init)
            if parts.contains(where: { Self.skipDirs(config).contains($0) }) { continue }

            if isJunkByName(file.lastPathComponent) {
                moveToLixo(file, vaultRoot: vaultRoot, reason: "nome", dryRun: dryRun)
                lixoCount += 1
            } else if isJunkByContent(file) {
                moveToLixo(file, vaultRoot: vaultRoot, reason: "conteúdo vazio", dryRun: dryRun)
                lixoCount += 1
            }
        }
        log("  → \(lixoCount) movida(s) para \(config.lixoDir)/")

        log("[ 2 ] Indexando vault...")
        let notes = collectAllNotes(vaultRoot: vaultRoot, dirtyPaths: dirtyPaths)
        let withDomain = notes.values.filter { !$0.domains.isEmpty }.count
        let withTags = notes.values.filter { !$0.tags.isEmpty }.count
        log("  → \(notes.count) notas no grafo | \(withDomain) com domínio (MOC) | \(withTags) com tags Apple Notes | máx \(config.maxInlineLinks) links/nota")

        log("[ 3 ] Criando links contextuais (Modelo A)...")
        let processList: [IndexedNote]
        if !dirtyPaths.isEmpty && !full {
            processList = notes.values.filter(\.dirty)
        } else {
            processList = Array(notes.values)
        }

        var linked = 0
        var semSinal = 0
        var semLinks = 0
        var jaLinkadas = 0
        var limpas = 0

        for (index, note) in processList.enumerated() {
            onProgress?(index + 1, processList.count, note.stem)
            let links = findLinks(note: note, all: notes)
            guard FileManager.default.fileExists(atPath: note.path.path) else { continue }

            do {
                let original = try String(contentsOf: note.path, encoding: .utf8)
                let updated = addLinksSection(original, links: links)

                if updated == original {
                    if !links.isEmpty {
                        jaLinkadas += 1
                    } else {
                        let hadSection = Self.linksSection.firstMatch(
                            in: original,
                            range: NSRange(location: 0, length: (original as NSString).length)
                        ) != nil
                        if hadSection {
                            limpas += 1
                        } else if !note.tags.isEmpty {
                            semLinks += 1
                        } else {
                            semSinal += 1
                        }
                    }
                    continue
                }

                if !dryRun {
                    try updated.write(to: note.path, atomically: true, encoding: .utf8)
                }
                if links.isEmpty { limpas += 1 } else { linked += 1 }
            } catch {
                log("  ERRO  \(note.path.lastPathComponent): \(error.localizedDescription)")
            }
        }

        log("[ 4 ] Gerando MOC por domínio...")
        var affectedDomains: Set<String>? = nil
        if !dirtyPaths.isEmpty && !full {
            var affected = Set<String>()
            for note in notes.values where note.dirty {
                affected.formUnion(note.domains)
            }
            affectedDomains = affected
        }
        let mocCount = generateMOC(vaultRoot: vaultRoot, notes: notes, onlyDomains: affectedDomains, dryRun: dryRun)

        log("  → \(linked) linkadas | \(limpas) limpas (sem seção) | \(mocCount) MOC(s)")
        log("  → ignoradas: \(semSinal) sem sinal | \(semLinks) sem link | \(jaLinkadas) já linkadas")

        if !dryRun {
            JSONFile.write(["generated_at": Dates.isoString(), "paths": [String]()], to: config.dirtyURL)
            var metrics = OrganizeMetrics()
            metrics.lixo = lixoCount
            metrics.linkadas = linked
            metrics.limpas = limpas
            metrics.mocs = mocCount
            metrics.semSinal = semSinal
            metrics.semLinks = semLinks
            metrics.jaLinkadas = jaLinkadas
            metrics.maxInlineLinks = config.maxInlineLinks
            JSONFile.write(metrics.dictionary, to: config.organizeMetricsURL)
        }

        dirtyPaths.removeAll()
        return true
    }

    // MARK: - Índice

    private func collectAllNotes(vaultRoot: URL, dirtyPaths: [String]) -> [String: IndexedNote] {
        let dirtySet = Set(dirtyPaths.map { URL(fileURLWithPath: $0).standardizedFileURL.path })
        var notes: [String: IndexedNote] = [:]
        let skip = Self.skipDirs(config)

        for file in allMarkdown(in: vaultRoot) {
            let relative = Paths.relativePath(of: file, in: vaultRoot)
            let parts = relative.split(separator: "/").map(String.init)
            if parts.contains(where: { skip.contains($0) }) { continue }
            if isJunkByName(file.lastPathComponent) { continue }

            guard let raw = try? String(contentsOf: file, encoding: .utf8) else { continue }
            let frontmatter = Self.parseFrontmatter(raw)
            let content = Self.stripFrontmatter(raw)
            let stem = file.deletingPathExtension().lastPathComponent

            let noteID: String
            if let value = frontmatter["note_id"] as? String, !value.isEmpty {
                noteID = value
            } else {
                let extracted = VaultPaths.extractNoteID(raw)
                noteID = extracted.isEmpty ? "legacy:\(file.path)" : extracted
            }

            let title = (frontmatter["title"] as? String).flatMap { $0.isEmpty ? nil : $0 } ?? stem

            var tags = Set<String>()
            if let list = frontmatter["tags"] as? [String] {
                tags = Set(list.map { $0.lowercased().trimmingCharacters(in: .whitespaces) }.filter { !$0.isEmpty })
            }

            var domains = getDomains(content)
            domains.formUnion(tags.filter { config.domainKeywords[$0] != nil })

            notes[noteID] = IndexedNote(
                path: file,
                stem: stem,
                title: title,
                noteID: noteID,
                domains: domains,
                tags: tags,
                text: content.lowercased(),
                dirty: dirtySet.contains(file.standardizedFileURL.path)
            )
        }
        return notes
    }

    // MARK: - Links

    private func findLinks(note: IndexedNote, all: [String: IndexedNote]) -> [String] {
        var candidates: [(priority: Int, link: String)] = []

        for (otherID, other) in all where otherID != note.noteID {
            if titleMentioned(note.text, title: other.title) {
                candidates.append((1, other.stem))
            } else if !note.tags.isEmpty, !other.tags.isEmpty, !note.tags.isDisjoint(with: other.tags) {
                candidates.append((2, other.stem))
            }
        }

        candidates.sort { $0.priority < $1.priority }
        var seen = Set<String>()
        var result: [String] = []
        for candidate in candidates {
            if seen.contains(candidate.link) { continue }
            seen.insert(candidate.link)
            result.append(candidate.link)
            if result.count >= config.maxInlineLinks { break }
        }
        return result
    }

    private func titleMentioned(_ text: String, title: String) -> Bool {
        guard title.count >= config.minTitleChars else { return false }
        let pattern = #"\b"# + NSRegularExpression.escapedPattern(for: title.lowercased()) + #"\b"#
        guard let regex = try? NSRegularExpression(pattern: pattern) else { return false }
        return regex.firstMatch(in: text, range: NSRange(location: 0, length: (text as NSString).length)) != nil
    }

    private func addLinksSection(_ content: String, links: [String]) -> String {
        let ns = content as NSString
        var value = Self.linksSection.stringByReplacingMatches(
            in: content,
            range: NSRange(location: 0, length: ns.length),
            withTemplate: ""
        )
        value = value.trimmingCharacters(in: .whitespacesAndNewlines)

        let newLinks = Set(links.filter { !value.contains("[[\($0)]]") }).sorted()
        guard !newLinks.isEmpty else { return value }

        var section = "\n\n---\n## Links relacionados\n"
        for link in newLinks {
            section += "- [[\(link)]]\n"
        }
        return value + section
    }

    private func stripLinksSections(vaultRoot: URL, dryRun: Bool) -> Int {
        var cleaned = 0
        let skip = Self.skipDirs(config)
        for file in allMarkdown(in: vaultRoot) {
            let relative = Paths.relativePath(of: file, in: vaultRoot)
            let parts = relative.split(separator: "/").map(String.init)
            if parts.contains(where: { skip.contains($0) }) { continue }
            guard let original = try? String(contentsOf: file, encoding: .utf8) else { continue }
            let ns = original as NSString
            let updated = Self.linksSection.stringByReplacingMatches(
                in: original,
                range: NSRange(location: 0, length: ns.length),
                withTemplate: ""
            ).trimmingCharacters(in: .whitespacesAndNewlines) + "\n"
            if updated != original {
                if !dryRun { try? updated.write(to: file, atomically: true, encoding: .utf8) }
                cleaned += 1
            }
        }
        return cleaned
    }

    // MARK: - MOC

    private func generateMOC(
        vaultRoot: URL,
        notes: [String: IndexedNote],
        onlyDomains: Set<String>?,
        dryRun: Bool
    ) -> Int {
        let mocDir = vaultRoot.appendingPathComponent("_index")
        if !dryRun {
            try? FileManager.default.createDirectory(at: mocDir, withIntermediateDirectories: true)
        }

        var domainMap: [String: [String]] = [:]
        for note in notes.values {
            for domain in note.domains {
                domainMap[domain, default: []].append(note.stem)
            }
        }

        var generated = 0
        for domain in domainMap.keys.sorted() {
            if let onlyDomains, !onlyDomains.contains(domain) { continue }
            let stems = Array(Set(domainMap[domain] ?? [])).sorted { $0.lowercased() < $1.lowercased() }
            let mocFile = mocDir.appendingPathComponent("\(domain).md")
            let display = domain.prefix(1).uppercased() + String(domain.dropFirst())

            var content = "---\n"
            content += "title: \"MOC: \(display)\"\n"
            content += "generated: true\n"
            content += "domain: \"\(domain)\"\n"
            content += "---\n\n"
            content += "# \(display)\n\n"
            content += "*\(stems.count) nota\(stems.count == 1 ? "" : "s") — gerado automaticamente*\n\n"
            for stem in stems {
                content += "- [[\(stem)]]\n"
            }

            if dryRun {
                generated += 1
            } else {
                let existing = (try? String(contentsOf: mocFile, encoding: .utf8)) ?? ""
                if content != existing {
                    try? content.write(to: mocFile, atomically: true, encoding: .utf8)
                    generated += 1
                }
            }
        }
        return generated
    }

    // MARK: - Lixo

    private func isJunkByName(_ name: String) -> Bool {
        let patterns = [
            #"^sem-nome\.md$"#,
            #"^Nova Nota\.md$"#,
            #"^New Note\.md$"#,
            #"^untitled\.md$"#,
            #"^OK\.md$"#
        ]
        for pattern in patterns {
            if name.range(of: pattern, options: [.regularExpression, .caseInsensitive]) != nil {
                return true
            }
        }
        return false
    }

    private func isJunkByContent(_ file: URL) -> Bool {
        guard config.minContentChars > 0 else { return false }
        return realCharCount(readContent(file)) < config.minContentChars
    }

    private func moveToLixo(_ file: URL, vaultRoot: URL, reason: String, dryRun: Bool) {
        let lixo = vaultRoot.appendingPathComponent(config.lixoDir)
        var destination = lixo.appendingPathComponent(file.lastPathComponent)
        if FileManager.default.fileExists(atPath: destination.path) {
            let stem = file.deletingPathExtension().lastPathComponent
            let parent = file.deletingLastPathComponent().lastPathComponent
            destination = lixo.appendingPathComponent("\(stem)_\(parent).\(file.pathExtension)")
        }
        log("  LIXO (\(reason))  \(Paths.relativePath(of: file, in: vaultRoot))")
        if !dryRun {
            try? FileManager.default.createDirectory(at: lixo, withIntermediateDirectories: true)
            try? FileManager.default.moveItem(at: file, to: destination)
        }
    }

    private func readContent(_ file: URL) -> String {
        guard let raw = try? String(contentsOf: file, encoding: .utf8) else { return "" }
        return Self.stripFrontmatter(raw).trimmingCharacters(in: .whitespacesAndNewlines)
    }

    private func realCharCount(_ text: String) -> Int {
        var value = text
        value = value.replacingOccurrences(of: #"\[\[.*?\]\]"#, with: "", options: .regularExpression)
        value = value.replacingOccurrences(of: #"#+\s"#, with: "", options: .regularExpression)
        value = value.replacingOccurrences(of: #"\s+"#, with: "", options: .regularExpression)
        return value.count
    }

    // MARK: - Utilidades

    private func getDomains(_ text: String) -> Set<String> {
        let lowered = text.lowercased()
        var result = Set<String>()
        for (domain, keywords) in config.domainKeywords {
            if keywords.contains(where: { lowered.contains($0.lowercased()) }) {
                result.insert(domain)
            }
        }
        return result
    }

    private func allMarkdown(in root: URL) -> [URL] {
        guard let enumerator = FileManager.default.enumerator(
            at: root,
            includingPropertiesForKeys: [.isRegularFileKey],
            options: [.skipsHiddenFiles]
        ) else { return [] }
        var files: [URL] = []
        for case let url as URL in enumerator where url.pathExtension.lowercased() == "md" {
            files.append(url)
        }
        return files
    }

    private static func skipDirs(_ config: AppConfig) -> Set<String> {
        [config.lixoDir, "_index", "_attachments"]
    }

    private static func stripFrontmatter(_ raw: String) -> String {
        let ns = raw as NSString
        return frontmatterStrip.stringByReplacingMatches(
            in: raw,
            range: NSRange(location: 0, length: ns.length),
            withTemplate: ""
        )
    }

    private static func parseFrontmatter(_ raw: String) -> [String: Any] {
        let ns = raw as NSString
        guard let match = frontmatterCapture.firstMatch(in: raw, range: NSRange(location: 0, length: ns.length)),
              match.numberOfRanges > 1 else { return [:] }

        let text = ns.substring(with: match.range(at: 1))
        var result: [String: Any] = [:]
        let lines = text.components(separatedBy: "\n")
        var index = 0

        while index < lines.count {
            let line = lines[index]
            let startsIndented = line.hasPrefix(" ") || line.hasPrefix("\t")
            if line.contains(":"), !startsIndented {
                let parts = line.split(separator: ":", maxSplits: 1, omittingEmptySubsequences: false)
                let key = parts[0].trimmingCharacters(in: .whitespaces)
                var value = parts.count > 1 ? parts[1].trimmingCharacters(in: .whitespaces) : ""
                value = value.trimmingCharacters(in: CharacterSet(charactersIn: "\""))

                var items: [String] = []
                var next = index + 1
                while next < lines.count {
                    let itemLine = lines[next]
                    let itemNS = itemLine as NSString
                    if let itemMatch = tagItem.firstMatch(in: itemLine, range: NSRange(location: 0, length: itemNS.length)),
                       itemMatch.numberOfRanges > 1 {
                        items.append(itemNS.substring(with: itemMatch.range(at: 1)).trimmingCharacters(in: .whitespaces))
                        next += 1
                    } else if itemLine.hasPrefix("  ") || itemLine.hasPrefix("\t") {
                        next += 1
                    } else {
                        break
                    }
                }

                if !items.isEmpty {
                    result[key] = items
                    index = next
                } else {
                    result[key] = value
                    index += 1
                }
            } else {
                index += 1
            }
        }
        return result
    }

    private func log(_ message: String, verboseOnly: Bool = false) {
        if verboseOnly && !PipelineEnvironment.verbose { return }
        logger.log(message)
        onLog?(message)
    }
}
