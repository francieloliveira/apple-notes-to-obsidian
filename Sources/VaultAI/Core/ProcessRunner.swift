import Foundation
import Darwin

public enum ProcessError: LocalizedError {
    case launch(String)
    case timeout(String)
    case failed(status: Int32, stderr: String)

    public var errorDescription: String? {
        switch self {
        case .launch(let message): return message
        case .timeout(let message): return "Tempo esgotado: \(message)"
        case .failed(let status, let stderr):
            return stderr.isEmpty ? "Processo falhou (código \(status))" : stderr
        }
    }
}

/// Executa processos lendo stdout/stderr em paralelo (evita deadlock com corpos
/// grandes de notas, que passam fácil do buffer do pipe).
public enum ProcessRunner {
    public struct Result {
        public let status: Int32
        public let stdout: String
        public let stderr: String
    }

    private final class Buffer: @unchecked Sendable {
        private let lock = NSLock()
        private var data = Data()
        func append(_ chunk: Data) {
            lock.lock(); data.append(chunk); lock.unlock()
        }
        var value: Data {
            lock.lock(); defer { lock.unlock() }; return data
        }
    }

    @discardableResult
    public static func run(
        _ executable: String,
        arguments: [String],
        timeout: TimeInterval = 120,
        environment: [String: String]? = nil
    ) throws -> Result {
        let process = Process()
        process.executableURL = URL(fileURLWithPath: executable)
        process.arguments = arguments
        if let environment {
            var env = ProcessInfo.processInfo.environment
            for (k, v) in environment { env[k] = v }
            process.environment = env
        }

        let outPipe = Pipe()
        let errPipe = Pipe()
        process.standardOutput = outPipe
        process.standardError = errPipe

        let out = Buffer()
        let err = Buffer()
        let group = DispatchGroup()

        group.enter()
        DispatchQueue.global(qos: .userInitiated).async {
            while true {
                let chunk = outPipe.fileHandleForReading.availableData
                if chunk.isEmpty { break }
                out.append(chunk)
            }
            group.leave()
        }

        group.enter()
        DispatchQueue.global(qos: .userInitiated).async {
            while true {
                let chunk = errPipe.fileHandleForReading.availableData
                if chunk.isEmpty { break }
                err.append(chunk)
            }
            group.leave()
        }

        let done = DispatchSemaphore(value: 0)
        process.terminationHandler = { _ in done.signal() }

        do {
            try process.run()
        } catch {
            try? outPipe.fileHandleForReading.close()
            try? errPipe.fileHandleForReading.close()
            throw ProcessError.launch("Não foi possível executar \(executable): \(error.localizedDescription)")
        }

        if done.wait(timeout: .now() + timeout) == .timedOut {
            process.terminate()
            if done.wait(timeout: .now() + 2) == .timedOut {
                kill(process.processIdentifier, SIGKILL)
                _ = done.wait(timeout: .now() + 2)
            }
            throw ProcessError.timeout("\(executable) \(arguments.first ?? "")")
        }

        _ = group.wait(timeout: .now() + 5)
        let stdout = String(data: out.value, encoding: .utf8) ?? ""
        let stderr = String(data: err.value, encoding: .utf8) ?? ""

        return Result(status: process.terminationStatus, stdout: stdout, stderr: stderr)
    }

    public static func osascript(_ script: String, timeout: TimeInterval = 120) throws -> String {
        let result = try run("/usr/bin/osascript", arguments: ["-e", script], timeout: timeout)
        guard result.status == 0 else {
            throw ProcessError.failed(status: result.status, stderr: result.stderr.trimmingCharacters(in: .whitespacesAndNewlines))
        }
        return result.stdout.trimmingCharacters(in: .whitespacesAndNewlines)
    }
}
