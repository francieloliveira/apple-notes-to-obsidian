import Foundation
import CryptoKit

/// Converte o HTML do Apple Notes em Markdown para o Obsidian.
///
/// Cobre o que o Notes realmente emite: `div`/`p` por linha, títulos, negrito,
/// itálico, listas (inclusive checklists), links, tabelas simples e imagens
/// base64 — que viram arquivos em `_attachments/`.
public struct MarkdownRenderer {
    private final class ImageContext {
        let directory: URL?
        let title: String
        var count = 0
        init(directory: URL?, title: String) {
            self.directory = directory
            self.title = title
        }
    }

    public init() {}

    public func render(html: String, attachmentsDir: URL?, noteTitle: String) -> String {
        let context = ImageContext(directory: attachmentsDir, title: noteTitle)
        var source = extractImages(from: html, context: context)
        source = replacePlainImages(in: source)

        var renderer = HTMLToMarkdown()
        var markdown = renderer.convert(source)
        markdown = markdown.replacingOccurrences(of: "\u{00a0}", with: " ")
        markdown = normalize(markdown)
        markdown = VaultPaths.fixObsidianEmbeds(markdown, noteDir: attachmentsDir?.deletingLastPathComponent())
        return markdown
    }

    // MARK: - Imagens base64

    private func extractImages(from html: String, context: ImageContext) -> String {
        guard let directory = context.directory else { return html }
        let pattern = #"<img[^>]+src=["'](data:image/[^"']+)["'][^>]*>"#
        guard let regex = try? NSRegularExpression(
            pattern: pattern,
            options: [.caseInsensitive, .dotMatchesLineSeparators]
        ) else { return html }

        let ns = html as NSString
        let matches = regex.matches(in: html, range: NSRange(location: 0, length: ns.length))
        guard !matches.isEmpty else { return html }

        try? FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        var output = html

        for match in matches.reversed() {
            guard match.numberOfRanges > 1 else { continue }
            let source = ns.substring(with: match.range(at: 1))
            guard let replacement = saveImage(source, context: context, directory: directory),
                  let range = Range(match.range, in: output) else { continue }
            output.replaceSubrange(range, with: "![[_attachments/\(replacement)]]")
        }
        return output
    }

    private func saveImage(_ source: String, context: ImageContext, directory: URL) -> String? {
        guard source.hasPrefix("data:image/"),
              let comma = source.firstIndex(of: ",") else { return nil }
        let meta = String(source[..<comma])
        let base64 = String(source[source.index(after: comma)...])
        guard let data = Data(base64Encoded: base64, options: [.ignoreUnknownCharacters]) else { return nil }

        var ext = "png"
        if let slash = meta.firstIndex(of: "/") {
            let after = meta[meta.index(after: slash)...]
            ext = after.split(separator: ";").first.map(String.init) ?? "png"
        }
        if ext == "jpeg" { ext = "jpg" }
        ext = ext.replacingOccurrences(of: #"[^a-z0-9]"#, with: "", options: .regularExpression)
        if ext.isEmpty { ext = "png" }

        context.count += 1
        let prefix = String(base64.prefix(64))
        let digest = Insecure.MD5.hash(data: Data(prefix.utf8))
        let hash = digest.map { String(format: "%02x", $0) }.joined().prefix(6)
        let safeTitle = String(VaultPaths.sanitizeTitle(context.title).prefix(40))
        let filename = "\(safeTitle)_\(context.count)_\(hash).\(ext)"

        let destination = directory.appendingPathComponent(filename)
        if !FileManager.default.fileExists(atPath: destination.path) {
            do {
                try data.write(to: destination, options: .atomic)
            } catch {
                return nil
            }
        }
        return filename
    }

    private func replacePlainImages(in html: String) -> String {
        guard let regex = try? NSRegularExpression(
            pattern: #"<img[^>]+src=["']([^"']+)["'][^>]*>"#,
            options: [.caseInsensitive, .dotMatchesLineSeparators]
        ) else { return html }
        let ns = html as NSString
        var output = html
        for match in regex.matches(in: html, range: NSRange(location: 0, length: ns.length)).reversed() {
            guard match.numberOfRanges > 1, let range = Range(match.range, in: output) else { continue }
            let src = ns.substring(with: match.range(at: 1))
            if src.hasPrefix("data:") {
                output.replaceSubrange(range, with: "")
            } else {
                output.replaceSubrange(range, with: "![](" + src + ")")
            }
        }
        return output
    }

    // MARK: - Normalização

    private func normalize(_ text: String) -> String {
        let lines = text.components(separatedBy: "\n").map { line -> String in
            var value = line.replacingOccurrences(of: "\u{00a0}", with: " ")
            while value.hasSuffix(" ") || value.hasSuffix("\t") { value.removeLast() }
            return value
        }

        var output: [String] = []
        var blankRun = 0
        for line in lines {
            if line.trimmingCharacters(in: .whitespaces).isEmpty {
                blankRun += 1
                if blankRun <= 1 { output.append("") }
            } else {
                blankRun = 0
                output.append(line)
            }
        }
        while output.first?.isEmpty == true { output.removeFirst() }
        while output.last?.isEmpty == true { output.removeLast() }
        return output.joined(separator: "\n")
    }
}

// MARK: - Tokenizador HTML

private struct HTMLToMarkdown {
    private enum ListKind { case ordered, unordered }

    private var output = ""
    private var listStack: [ListKind] = []
    private var links: [String] = []
    private var skipDepth = 0
    private var inPre = false
    private var blockquoteDepth = 0

    mutating func convert(_ html: String) -> String {
        var index = html.startIndex

        while index < html.endIndex {
            if html[index] == "<" {
                guard let end = html[index...].firstIndex(of: ">") else {
                    appendText(String(html[index...]))
                    break
                }
                let tag = String(html[html.index(after: index)..<end])
                handleTag(tag)
                index = html.index(after: end)
            } else if let next = html[index...].firstIndex(of: "<") {
                appendText(String(html[index..<next]))
                index = next
            } else {
                appendText(String(html[index...]))
                break
            }
        }
        return output
    }

    // MARK: Tags

    private mutating func handleTag(_ raw: String) {
        var tag = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !tag.isEmpty else { return }
        let isClosing = tag.hasPrefix("/")
        if isClosing { tag.removeFirst() }
        if tag.hasSuffix("/") { tag.removeLast() }

        let name = tag.prefix { $0.isLetter || $0.isNumber }.lowercased()
        let attrs = String(tag.dropFirst(name.count))

        if skipDepth > 0 {
            if name == "script" || name == "style" {
                if isClosing { skipDepth -= 1 } else if !attrs.contains("/") { skipDepth += 1 }
            }
            return
        }

        switch name {
        case "script", "style":
            if isClosing { skipDepth = max(0, skipDepth - 1) } else { skipDepth += 1 }

        case "div", "p", "section", "article", "header", "footer":
            newline()

        case "br":
            newline()

        case "h1", "h2", "h3", "h4", "h5", "h6":
            if isClosing {
                newline(2)
            } else {
                let level = Int(name.dropFirst()) ?? 1
                newline(2)
                output += String(repeating: "#", count: max(1, min(6, level))) + " "
            }

        case "b", "strong":
            output += "**"

        case "i", "em":
            output += "*"

        case "s", "strike", "del":
            output += "~~"

        case "code":
            if inPre { return }
            output += "`"

        case "pre":
            if isClosing {
                newline()
                output += "```"
                newline(2)
                inPre = false
            } else {
                newline(2)
                output += "```"
                newline()
                inPre = true
            }

        case "ul":
            if isClosing { listStack.removeLast() } else { listStack.append(.unordered) }
            newline()

        case "ol":
            if isClosing { listStack.removeLast() } else { listStack.append(.ordered) }
            newline()

        case "li":
            if isClosing {
                newline()
            } else {
                newline()
                let indent = String(repeating: "  ", count: max(0, listStack.count - 1))
                output += indent + listPrefix(attrs)
            }

        case "a":
            if isClosing {
                let href = links.popLast() ?? ""
                output += href.isEmpty ? "" : "](\(href))"
            } else {
                links.append(attribute("href", in: attrs) ?? "")
                output += "["
            }

        case "blockquote":
            if isClosing {
                blockquoteDepth = max(0, blockquoteDepth - 1)
                newline()
            } else {
                newline()
                blockquoteDepth += 1
                output += "> "
            }

        case "hr":
            newline(2)
            output += "---"
            newline(2)

        case "table":
            newline(2)

        case "tr":
            newline()
            output += "| "

        case "td", "th":
            if isClosing {
                output += " | "
            } else if output.hasSuffix("| ") {
                // primeira célula da linha: nada extra
            }

        case "img":
            break

        default:
            break
        }
    }

    private func listPrefix(_ attrs: String) -> String {
        let cls = attribute("class", in: attrs)?.lowercased() ?? ""
        if cls.contains("unchecked") { return "- [ ] " }
        if cls.contains("checked") { return "- [x] " }
        if listStack.last == .ordered { return "1. " }
        return "- "
    }

    private func attribute(_ name: String, in attrs: String) -> String? {
        let pattern = "\(name)\\s*=\\s*[\"']([^\"']*)[\"']"
        guard let regex = try? NSRegularExpression(pattern: pattern, options: [.caseInsensitive]),
              let match = regex.firstMatch(in: attrs, range: NSRange(location: 0, length: (attrs as NSString).length)),
              match.numberOfRanges > 1 else { return nil }
        return (attrs as NSString).substring(with: match.range(at: 1))
    }

    // MARK: Texto

    private mutating func appendText(_ raw: String) {
        var text = decodeEntities(raw)
        if inPre {
            output += text
            return
        }
        text = text.replacingOccurrences(of: "\n", with: " ")
            .replacingOccurrences(of: "\t", with: " ")
            .replacingOccurrences(of: #"\s{2,}"#, with: " ", options: .regularExpression)
        guard !text.isEmpty else { return }

        if blockquoteDepth > 0, output.hasSuffix("\n") {
            output += String(repeating: "> ", count: blockquoteDepth)
        }
        output += text
    }

    private func decodeEntities(_ text: String) -> String {
        var value = text
        let named: [(String, String)] = [
            ("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"),
            ("&quot;", "\""), ("&#39;", "'"), ("&apos;", "'"), ("&hellip;", "…"),
            ("&mdash;", "—"), ("&ndash;", "–"), ("&rsquo;", "’"), ("&lsquo;", "‘"),
            ("&ldquo;", "“"), ("&rdquo;", "”")
        ]
        for (entity, replacement) in named {
            value = value.replacingOccurrences(of: entity, with: replacement, options: .caseInsensitive)
        }

        if let regex = try? NSRegularExpression(pattern: #"&#(x?[0-9a-fA-F]+);"#) {
            let ns = value as NSString
            let matches = regex.matches(in: value, range: NSRange(location: 0, length: ns.length))
            for match in matches.reversed() where match.numberOfRanges > 1 {
                let rawNumber = ns.substring(with: match.range(at: 1))
                let scalarValue: UInt32?
                if rawNumber.hasPrefix("x") || rawNumber.hasPrefix("X") {
                    scalarValue = UInt32(rawNumber.dropFirst(), radix: 16)
                } else {
                    scalarValue = UInt32(rawNumber)
                }
                guard let scalarValue, let scalar = Unicode.Scalar(scalarValue),
                      let range = Range(match.range, in: value) else { continue }
                value.replaceSubrange(range, with: String(Character(scalar)))
            }
        }
        return value
    }

    // MARK: Espaçamento

    private mutating func newline(_ count: Int = 1) {
        guard !output.isEmpty else { return }
        let existing = output.reversed().prefix { $0 == "\n" }.count
        let needed = max(0, count - existing)
        if needed > 0 { output += String(repeating: "\n", count: needed) }
    }
}
