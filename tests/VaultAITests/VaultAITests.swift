import XCTest
@testable import VaultAI

final class VaultAITests: XCTestCase {
    func testSanitizeKeepsReadableName() {
        XCTAssertEqual(VaultPaths.sanitizeTitle("Reunião Petrobras"), "Reunião Petrobras")
        XCTAssertFalse(VaultPaths.sanitizeTitle("Reunião Petrobras").contains("_"))
    }

    func testSanitizeStripsEllipsis() {
        let name = VaultPaths.sanitizeTitle("Para atualizar o Open WebUI no Docker…")
        XCTAssertFalse(name.contains("…"))
    }

    func testURLBecomesSlug() {
        let slug = VaultPaths.urlToFilenameSlug("https://premium-dsv-outsystems.petrobras.com.br/S10865_Autonomia")
        XCTAssertTrue(slug.hasPrefix("premium-dsv-outsystems"))
        XCTAssertFalse(slug.contains("://"))
    }

    func testNormalizeDateCollapsesWhitespace() {
        XCTAssertEqual(
            Dates.normalize("  Segunda,  1  de  janeiro  "),
            Dates.normalize("segunda, 1 de janeiro")
        )
    }

    func testSecretsBlocksPasswordTitle() {
        let guardrail = SecretsGuard(enabled: true)
        XCTAssertTrue(guardrail.check(title: "Senha hotmail").blocked)
        XCTAssertTrue(guardrail.check(title: "API key").blocked)
        XCTAssertTrue(guardrail.check(title: "lista wifi", folderSegments: ["Pessoal", "Senhas"]).blocked)
        XCTAssertFalse(guardrail.check(title: "Passwordless login").blocked)
    }

    func testMarkdownRendersHeadingsAndChecklists() {
        let renderer = MarkdownRenderer()
        let markdown = renderer.render(
            html: "<h1>Título</h1><div>Texto <b>forte</b></div><ul><li class=\"checked\">feito</li><li class=\"unchecked\">a fazer</li></ul>",
            attachmentsDir: nil,
            noteTitle: "Teste"
        )
        XCTAssertTrue(markdown.contains("# Título"))
        XCTAssertTrue(markdown.contains("**forte**"))
        XCTAssertTrue(markdown.contains("- [x] feito"))
        XCTAssertTrue(markdown.contains("- [ ] a fazer"))
    }

    func testMarkdownDecodesEntities() {
        let renderer = MarkdownRenderer()
        let markdown = renderer.render(html: "<div>A&amp;B&nbsp;—&nbsp;C</div>", attachmentsDir: nil, noteTitle: "x")
        XCTAssertEqual(markdown, "A&B — C")
    }

    func testAliasesMergeKeepsOldNames() {
        let aliases = VaultPaths.mergeAliases(
            existing: ["Old Name"],
            oldStem: "Old Name_a1b2c3d4",
            oldTitle: "Old Name",
            newTitle: "New Name"
        )
        XCTAssertTrue(aliases.contains("Old Name"))
        XCTAssertTrue(aliases.contains("Old Name_a1b2c3d4"))
        XCTAssertFalse(aliases.contains("New Name"))
    }

    // MARK: - Organizer

    private func makeVault(_ files: [String: String]) throws -> (root: URL, vault: URL, state: URL) {
        let root = FileManager.default.temporaryDirectory
            .appendingPathComponent("vaultai-test-\(UUID().uuidString)")
        let vault = root.appendingPathComponent("vault")
        let state = root.appendingPathComponent("state")
        try FileManager.default.createDirectory(at: vault.appendingPathComponent("Notes"), withIntermediateDirectories: true)
        try FileManager.default.createDirectory(at: state, withIntermediateDirectories: true)
        for (name, content) in files {
            try content.write(
                to: vault.appendingPathComponent("Notes/\(name)"),
                atomically: true,
                encoding: .utf8
            )
        }
        return (root, vault, state)
    }

    func testOrganizerBuildsLinksMOCsAndJunk() throws {
        let fixture = try makeVault([
            "Python.md": "# Python\n\nVou usar Docker no projeto.\n",
            "Docker.md": "# Docker\n\npython e containers.\n",
            "Empty.md": "curto",
            "OK.md": "x"
        ])
        defer { try? FileManager.default.removeItem(at: fixture.root) }

        var config = AppConfig(vaultPath: fixture.vault.path, stateDir: fixture.state.path)
        config.minContentChars = 10
        let organizer = VaultOrganizer(
            config: config,
            logger: VaultLogger(fileURL: fixture.state.appendingPathComponent("organize.log"))
        )

        XCTAssertTrue(organizer.run(full: true, dryRun: false, verbose: false))

        let python = try String(contentsOf: fixture.vault.appendingPathComponent("Notes/Python.md"), encoding: .utf8)
        XCTAssertTrue(python.contains("[[Docker]]"), "nota deve linkar o título citado")
        XCTAssertTrue(
            FileManager.default.fileExists(atPath: fixture.vault.appendingPathComponent("_index/tech.md").path),
            "MOC de domínio deve ser gerado"
        )
        XCTAssertTrue(FileManager.default.fileExists(atPath: fixture.vault.appendingPathComponent("_lixo/OK.md").path))
        XCTAssertTrue(FileManager.default.fileExists(atPath: fixture.vault.appendingPathComponent("_lixo/Empty.md").path))
    }

    func testOrganizerDryRunDoesNotTouchVault() throws {
        let fixture = try makeVault(["Python.md": "# Python\n\nVou usar Docker no projeto.\n"])
        defer { try? FileManager.default.removeItem(at: fixture.root) }

        let config = AppConfig(vaultPath: fixture.vault.path, stateDir: fixture.state.path)
        let organizer = VaultOrganizer(
            config: config,
            logger: VaultLogger(fileURL: fixture.state.appendingPathComponent("organize.log"))
        )

        XCTAssertTrue(organizer.run(full: true, dryRun: true, verbose: false))

        let note = try String(contentsOf: fixture.vault.appendingPathComponent("Notes/Python.md"), encoding: .utf8)
        XCTAssertFalse(note.contains("Links relacionados"))
        XCTAssertFalse(FileManager.default.fileExists(atPath: fixture.vault.appendingPathComponent("_index").path))
        XCTAssertFalse(FileManager.default.fileExists(atPath: fixture.vault.appendingPathComponent("_lixo").path))
    }
}
