import Foundation

/// Log em arquivo com o mesmo formato do pipeline Python: `[yyyy-MM-dd HH:mm:ss] msg`.
public final class VaultLogger: @unchecked Sendable {
    public let fileURL: URL
    private let lock = NSLock()

    public init(fileURL: URL) {
        self.fileURL = fileURL
        try? FileManager.default.createDirectory(
            at: fileURL.deletingLastPathComponent(),
            withIntermediateDirectories: true
        )
    }

    public func log(_ message: String) {
        let line = "[\(Dates.logTimestamp())] \(message)\n"
        lock.lock()
        defer { lock.unlock() }
        if let handle = try? FileHandle(forWritingTo: fileURL) {
            defer { try? handle.close() }
            _ = try? handle.seekToEnd()
            try? handle.write(contentsOf: Data(line.utf8))
        } else {
            try? line.write(to: fileURL, atomically: true, encoding: .utf8)
        }
    }

    /// Rotaciona `*.log` do diretório de estado. Retorna quantos arquivos mudaram.
    @discardableResult
    public static func rotateLogs(in directory: URL, maxBytes: Int = 5 * 1024 * 1024, backups: Int = 3) -> Int {
        guard let files = try? FileManager.default.contentsOfDirectory(
            at: directory,
            includingPropertiesForKeys: [.fileSizeKey]
        ) else { return 0 }

        var rotated = 0
        for file in files where file.pathExtension == "log" {
            let size = (try? file.resourceValues(forKeys: [.fileSizeKey]).fileSize) ?? 0
            guard size > maxBytes else { continue }

            let fm = FileManager.default
            let oldest = URL(fileURLWithPath: file.path + ".\(backups)")
            try? fm.removeItem(at: oldest)
            if backups > 1 {
                for index in stride(from: backups - 1, through: 1, by: -1) {
                    let src = URL(fileURLWithPath: file.path + ".\(index)")
                    let dst = URL(fileURLWithPath: file.path + ".\(index + 1)")
                    if fm.fileExists(atPath: src.path) {
                        try? fm.moveItem(at: src, to: dst)
                    }
                }
            }
            try? fm.moveItem(at: file, to: URL(fileURLWithPath: file.path + ".1"))
            fm.createFile(atPath: file.path, contents: nil)
            rotated += 1
        }
        return rotated
    }
}
