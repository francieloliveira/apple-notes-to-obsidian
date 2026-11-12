import Foundation

public enum Notifier {
    public static func post(title: String, subtitle: String = "", message: String, sound: String = "Glass") {
        let script = """
        display notification "\(escape(message))" with title "\(escape(title))" subtitle "\(escape(subtitle))" sound name "\(escape(sound))"
        """
        _ = try? ProcessRunner.run("/usr/bin/osascript", arguments: ["-e", script], timeout: 5)
    }

    private static func escape(_ value: String) -> String {
        value
            .replacingOccurrences(of: "\\", with: "\\\\")
            .replacingOccurrences(of: "\"", with: "\\\"")
            .replacingOccurrences(of: "\n", with: " ")
    }
}
