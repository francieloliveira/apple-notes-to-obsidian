import Foundation

public struct NoteMeta: Sendable {
    public let id: String
    public let title: String
    public let folderID: String
    public let modDate: String
}

public struct FetchedNote: Sendable {
    public let body: String
    public let modDate: String
    public let tags: [String]
}

/// Ponte com o Apple Notes via AppleScript.
///
/// Usa `/usr/bin/osascript` como o pipeline antigo: cada nota é um processo
/// curto, o que permite buscar várias em paralelo sem travar o Notes.
public final class AppleNotesService: @unchecked Sendable {
    public static let shared = AppleNotesService()

    private let lock = NSLock()
    private var _notesWasRunning = false

    public init() {}

    // MARK: - Scripts

    private let treeScript = #"""
    tell application "Notes"
        set output to ""
        repeat with aFolder in every folder
            set fid   to id of aFolder
            set fname to name of aFolder
            set pid   to ""
            try
                set p to container of aFolder
                if class of p is folder then set pid to id of p
            end try
            set output to output & fid & "|||" & fname & "|||" & pid & "\n"
        end repeat
        return output
    end tell
    """#

    private let listMetaScript = #"""
    tell application "Notes"
        set output to ""
        repeat with aFolder in every folder
            set fid to id of aFolder
            repeat with aNote in every note of aFolder
                set nid    to id of aNote
                set ntitle to name of aNote
                set mdate  to modification date of aNote
                set output to output & nid & "|||" & ntitle & "|||" & fid & "|||" & (mdate as string) & "\n"
            end repeat
        end repeat
        return output
    end tell
    """#

    private let fetchScript = #"""
    tell application "Notes"
        set matchNote to first note whose id is "@NOTE_ID@"
        set mdate to modification date of matchNote
        set tagStr to ""
        try
            set tagList to tags of matchNote
            repeat with aTag in tagList
                if tagStr is "" then
                    set tagStr to (name of aTag)
                else
                    set tagStr to tagStr & "," & (name of aTag)
                end if
            end repeat
        end try
        return (mdate as string) & "||VAULTDATE||" & tagStr & "||VAULTTAGS||" & body of matchNote
    end tell
    """#

    // MARK: - Ciclo de vida do Notes

    public func ensureNotesRunning() {
        let running: Bool
        do {
            let out = try ProcessRunner.osascript(
                #"tell application "System Events" to return (name of processes) contains "Notes""#,
                timeout: 10
            )
            running = out.lowercased() == "true"
        } catch {
            running = false
        }

        lock.lock(); _notesWasRunning = running; lock.unlock()

        if !running {
            _ = try? ProcessRunner.osascript(#"tell application "Notes" to launch"#, timeout: 15)
            Thread.sleep(forTimeInterval: 3)
        }
    }

    public func quitNotesIfWeOpened() {
        lock.lock()
        let wasRunning = _notesWasRunning
        lock.unlock()
        guard !wasRunning else { return }
        _ = try? ProcessRunner.osascript(#"tell application "Notes" to quit"#, timeout: 10)
    }

    // MARK: - Leitura

    public func folderTree() throws -> [String: [String]] {
        let raw = try ProcessRunner.osascript(treeScript, timeout: 60)
        var folders: [String: (name: String, parent: String)] = [:]
        for line in raw.split(separator: "\n", omittingEmptySubsequences: true) {
            let parts = line.components(separatedBy: "|||")
            guard parts.count == 3 else { continue }
            let id = parts[0].trimmingCharacters(in: .whitespaces)
            folders[id] = (parts[1].trimmingCharacters(in: .whitespaces),
                           parts[2].trimmingCharacters(in: .whitespaces))
        }

        var cache: [String: [String]] = [:]
        func resolve(_ id: String, visited: Set<String> = []) -> [String] {
            if let cached = cache[id] { return cached }
            guard !visited.contains(id), let entry = folders[id] else { return [] }
            var next = visited
            next.insert(id)
            let path: [String]
            if !entry.parent.isEmpty, folders[entry.parent] != nil {
                path = resolve(entry.parent, visited: next) + [entry.name]
            } else {
                path = [entry.name]
            }
            cache[id] = path
            return path
        }

        var result: [String: [String]] = [:]
        for id in folders.keys { result[id] = resolve(id) }
        return result
    }

    public func listMeta() throws -> [NoteMeta] {
        let raw = try ProcessRunner.osascript(listMetaScript, timeout: 120)
        var notes: [NoteMeta] = []
        var seen = Set<String>()
        for line in raw.split(separator: "\n", omittingEmptySubsequences: true) {
            let parts = line.components(separatedBy: "|||")
            guard parts.count == 4 else { continue }
            let note = NoteMeta(
                id: parts[0].trimmingCharacters(in: .whitespaces),
                title: parts[1].trimmingCharacters(in: .whitespaces),
                folderID: parts[2].trimmingCharacters(in: .whitespaces),
                modDate: parts[3].trimmingCharacters(in: .whitespaces)
            )
            let key = note.id + "|" + note.folderID
            guard !seen.contains(key) else { continue }
            seen.insert(key)
            notes.append(note)
        }
        return notes
    }

    public func fetchOne(id: String, timeout: TimeInterval = 30) -> FetchedNote? {
        let escaped = id
            .replacingOccurrences(of: "\\", with: "\\\\")
            .replacingOccurrences(of: "\"", with: "\\\"")
        let script = fetchScript.replacingOccurrences(of: "@NOTE_ID@", with: escaped)

        guard let result = try? ProcessRunner.run(
            "/usr/bin/osascript",
            arguments: ["-e", script],
            timeout: timeout
        ), result.status == 0 else { return nil }

        let out = result.stdout
        guard let dateRange = out.range(of: "||VAULTDATE||"),
              let tagsRange = out.range(of: "||VAULTTAGS||") else {
            return nil
        }

        let modDate = String(out[..<dateRange.lowerBound]).trimmingCharacters(in: .whitespacesAndNewlines)
        let tagString = String(out[dateRange.upperBound..<tagsRange.lowerBound])
        let body = String(out[tagsRange.upperBound...])
        let tags = tagString
            .split(separator: ",")
            .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty }
        return FetchedNote(body: body, modDate: modDate, tags: tags)
    }

    /// Busca corpos em paralelo, no máximo `workers` por vez.
    public func fetchBodies(
        notes: [NoteMeta],
        workers: Int,
        progress: @escaping (Int, Int, NoteMeta) -> Void
    ) -> [String: FetchedNote] {
        guard !notes.isEmpty else { return [:] }

        let queue = OperationQueue()
        queue.maxConcurrentOperationCount = max(1, workers)
        queue.qualityOfService = .userInitiated

        let resultLock = NSLock()
        var results: [String: FetchedNote] = [:]
        var done = 0

        for note in notes {
            queue.addOperation { [weak self] in
                guard let self else { return }
                if let fetched = self.fetchOne(id: note.id), !fetched.body.isEmpty {
                    resultLock.lock()
                    results[note.id] = fetched
                    resultLock.unlock()
                }
                resultLock.lock()
                done += 1
                let current = done
                resultLock.unlock()
                progress(current, notes.count, note)
            }
        }

        queue.waitUntilAllOperationsAreFinished()
        resultLock.lock()
        let final = results
        resultLock.unlock()
        return final
    }
}
