import Foundation

/// Contagens da última execução do sync. Em dry run nada é gravado em
/// `metrics.json`, então o pipeline usa isto para resumir a simulação.
public struct SyncCounts: Sendable {
    public var created = 0
    public var updated = 0
    public var blocked = 0
    public var protected = 0
    public var errors = 0

    public init(created: Int = 0, updated: Int = 0, blocked: Int = 0, protected: Int = 0, errors: Int = 0) {
        self.created = created
        self.updated = updated
        self.blocked = blocked
        self.protected = protected
        self.errors = errors
    }
}

/// Porta do `notes_to_obsidian.py`: exporta o Apple Notes para o vault Obsidian
/// mantendo o mesmo estado em `~/.vault` (checkpoint, paths, aliases, secrets).
public final class VaultSync {
    private let config: AppConfig
    private let notes: AppleNotesService
    private let logger: VaultLogger
    private let renderer = MarkdownRenderer()
    private let progressLock = NSLock()

    public private(set) var lastCounts = SyncCounts()

    public var onProgress: ((ProgressInfo) -> Void)?
    public var onLog: ((String) -> Void)?

    public init(
        config: AppConfig,
        notes: AppleNotesService = .shared,
        logger: VaultLogger
    ) {
        self.config = config
        self.notes = notes
        self.logger = logger
    }

    // MARK: - Entrada

    public func run(full: Bool, dryRun: Bool, verbose: Bool) -> Bool {
        ensureDirs()
        log("=== sync iniciado\(dryRun ? " [DRY RUN]" : "") ===")

        if !full, !notesDBChanged() {
            if !dryRun {
                JSONFile.write(["generated_at": Dates.isoString(), "paths": [String]()], to: config.dirtyURL)
                StateStore.writeEmptyMetrics(config: config)
            }
            lastCounts = SyncCounts()
            log("=== sync concluido (sem mudanças) ===")
            return true
        }

        notes.ensureNotesRunning()
        defer {
            notes.quitNotesIfWeOpened()
            StateStore.clearProgress(config: config)
        }

        do {
            log("1/4  Mapeando árvore de pastas...")
            let tree = try notes.folderTree()
            log("     Pastas: \(tree.count)")

            var state = full ? [String: Any]() : JSONFile.object(at: config.stateFileURL)
            var ids = full ? [String: String]() : JSONFile.object(at: config.idsURL).compactMapValues { $0 as? String }
            var paths = full ? [String: String]() : JSONFile.object(at: config.pathsURL).compactMapValues { $0 as? String }

            log("2/4  Listando metadados...")
            let allMeta = try notes.listMeta()
            log("     Notas encontradas: \(allMeta.count)")

            var pending = allMeta.filter { note in
                full || (state[note.id] as? String) != Dates.normalize(note.modDate)
            }
            log("3/4  Notas a processar: \(pending.count) (ignoradas: \(allMeta.count - pending.count))")

            if pending.isEmpty {
                log("     Tudo atualizado. Nada a fazer.")
                JSONFile.write(["generated_at": Dates.isoString(), "paths": [String]()], to: config.dirtyURL)
                StateStore.writeEmptyMetrics(config: config)
                JSONFile.remove(config.checkpointURL)
                log("=== sync concluido ===")
                return true
            }

            var dirtyPaths: [String] = []
            var doneIDs: [String] = []
            var created = 0
            var updated = 0
            var blocked = 0
            var protected = 0
            var errors = 0

            let sessionPendingIDs = pending.map(\.id)
            let checkpoint = full ? [:] : JSONFile.object(at: config.checkpointURL)

            if !checkpoint.isEmpty,
               let checkpointDone = checkpoint["done_ids"] as? [String],
               let checkpointPending = checkpoint["pending_ids"] as? [String],
               Set(checkpointPending) == Set(sessionPendingIDs) {
                state = (checkpoint["state"] as? [String: Any]) ?? state
                ids = ((checkpoint["ids"] as? [String: Any]) ?? [:]).compactMapValues { $0 as? String }
                paths = ((checkpoint["paths"] as? [String: Any]) ?? [:]).compactMapValues { $0 as? String }
                dirtyPaths = (checkpoint["dirty_paths"] as? [String]) ?? []
                created = (checkpoint["created"] as? NSNumber)?.intValue ?? 0
                updated = (checkpoint["updated"] as? NSNumber)?.intValue ?? 0
                doneIDs = checkpointDone
                let doneSet = Set(doneIDs)
                let before = pending.count
                pending = pending.filter { !doneSet.contains($0.id) }
                if before != pending.count {
                    log("     Retomando checkpoint: \(before - pending.count) notas já gravadas, \(pending.count) restantes")
                }
            } else if !checkpoint.isEmpty {
                log("     Checkpoint inválido (notas mudaram) — iniciando do zero")
                JSONFile.remove(config.checkpointURL)
            }

            if pending.isEmpty {
                log("     Todas as notas já gravadas (via checkpoint).")
                lastCounts = SyncCounts(
                    created: created,
                    updated: updated,
                    blocked: blocked,
                    protected: protected,
                    errors: errors
                )
                if !dryRun {
                    state["_last_sync_epoch"] = Date().timeIntervalSince1970
                    JSONFile.write(state, to: config.stateFileURL)
                    JSONFile.write(ids, to: config.idsURL)
                    JSONFile.write(paths, to: config.pathsURL)
                    JSONFile.write(["generated_at": Dates.isoString(), "paths": dirtyPaths], to: config.dirtyURL)
                    var metrics = SyncMetrics()
                    metrics.criadas = created
                    metrics.atualizadas = updated
                    metrics.skipped = false
                    JSONFile.write(metrics.dictionary, to: config.metricsURL)
                }
                JSONFile.remove(config.checkpointURL)
                log("=== sync concluido ===")
                return true
            }

            // Secrets por título/pasta, antes de buscar corpo.
            var toFetch: [NoteMeta] = []
            for note in pending {
                let segments = tree[note.folderID] ?? []
                let secret = secretsGuard.check(title: note.title, folderSegments: segments)
                if secret.blocked {
                    blocked += 1
                    if !dryRun {
                        let removal = VaultPaths.removeSecretFromVault(
                            noteID: note.id, pathsMap: &paths, vaultRoot: config.vaultURL
                        )
                        if removal != .failed {
                            state[note.id] = Dates.normalize(note.modDate)
                            ids[note.id] = note.id
                            if !doneIDs.contains(note.id) { doneIDs.append(note.id) }
                            if case .removed(let rel) = removal {
                                log("  xx  SECRET removido do vault: \(rel)", verboseOnly: verbose)
                            }
                        }
                    }
                    log("  --  BLOQUEADA (secret) '\(String(note.title.prefix(50)))' [\(secret.reason)]")
                } else {
                    toFetch.append(note)
                }
            }
            if blocked > 0 { log("     Secrets bloqueados (título/pasta): \(blocked)") }
            pending = toFetch

            let bodies: [String: FetchedNote]
            if dryRun || pending.isEmpty {
                bodies = [:]
            } else {
                bodies = fetchBodies(pending, tree: tree)
            }

            log("4/4  Gravando no vault...")
            let total = pending.count

            for (index, note) in pending.enumerated() {
                let position = index + 1
                guard let segments = tree[note.folderID], !segments.isEmpty else {
                    errors += 1
                    log("  !! folder não encontrado: \(note.folderID) / '\(note.title)'")
                    emitProgress(ProgressInfo(current: position, total: total, criadas: created, atualizadas: updated, erros: errors))
                    continue
                }

                let isNew = state[note.id] == nil
                let fetched = bodies[note.id]
                let modDate = (fetched?.modDate.isEmpty == false ? fetched!.modDate : note.modDate)

                let bodySecret = secretsGuard.check(title: note.title, body: fetched?.body ?? "", folderSegments: segments)
                if bodySecret.blocked {
                    blocked += 1
                    if !dryRun {
                        let removal = VaultPaths.removeSecretFromVault(
                            noteID: note.id, pathsMap: &paths, vaultRoot: config.vaultURL
                        )
                        if removal != .failed {
                            state[note.id] = Dates.normalize(modDate)
                            ids[note.id] = note.id
                            if !doneIDs.contains(note.id) { doneIDs.append(note.id) }
                            if case .removed(let rel) = removal {
                                log("  xx  SECRET removido do vault: \(rel)", verboseOnly: verbose)
                            }
                        }
                    }
                    log("  --  BLOQUEADA (secret) '\(String(note.title.prefix(50)))' [\(bodySecret.reason)]")
                    emitProgress(ProgressInfo(current: position, total: total, criadas: created, atualizadas: updated, erros: errors))
                    continue
                }

                do {
                    let file = try writeNote(
                        title: note.title,
                        segments: segments,
                        bodyHTML: fetched?.body ?? "",
                        modDate: modDate,
                        noteID: note.id,
                        paths: &paths,
                        tags: fetched?.tags ?? [],
                        dryRun: dryRun
                    )

                    if !dryRun {
                        state[note.id] = Dates.normalize(modDate)
                        ids[note.id] = note.id
                        dirtyPaths.append(file.path)
                        if !doneIDs.contains(note.id) { doneIDs.append(note.id) }
                    }

                    if isNew { created += 1 } else { updated += 1 }
                    emitProgress(ProgressInfo(current: position, total: total, criadas: created, atualizadas: updated, erros: errors))

                    if !dryRun, position % max(1, config.checkpointEvery) == 0 {
                        saveCheckpoint(
                            pendingIDs: sessionPendingIDs,
                            doneIDs: doneIDs,
                            state: state,
                            ids: ids,
                            paths: paths,
                            dirtyPaths: dirtyPaths,
                            created: created,
                            updated: updated
                        )
                        log("  .. checkpoint: \(position)/\(total) notas gravadas", verboseOnly: verbose)
                    }
                } catch VaultError.fileExists(_) {
                    protected += 1
                    log("  --  PROTEGIDA '\(note.title)'")
                } catch {
                    errors += 1
                    log("  !!  ERRO '\(note.title)': \(error.localizedDescription)")
                }
            }

            if !dryRun {
                state["_last_sync_epoch"] = Date().timeIntervalSince1970
                JSONFile.write(state, to: config.stateFileURL)
                JSONFile.write(ids, to: config.idsURL)
                JSONFile.write(paths, to: config.pathsURL)
                JSONFile.write(["generated_at": Dates.isoString(), "paths": dirtyPaths], to: config.dirtyURL)

                var metrics = SyncMetrics()
                metrics.criadas = created
                metrics.atualizadas = updated
                metrics.protegidas = protected
                metrics.bloqueadas = blocked
                metrics.erros = errors
                metrics.skipped = false
                JSONFile.write(metrics.dictionary, to: config.metricsURL)

                if errors == 0 {
                    JSONFile.remove(config.checkpointURL)
                } else {
                    log("  .. checkpoint mantido (\(errors) erros) — próximo sync retoma")
                }
            }

            lastCounts = SyncCounts(
                created: created,
                updated: updated,
                blocked: blocked,
                protected: protected,
                errors: errors
            )
            log("     criadas:\(created)  atualizadas:\(updated)  protegidas:\(protected)  bloqueadas:\(blocked)  erros:\(errors)")
            log("=== sync concluido ===")
            return errors == 0
        } catch {
            log("!! sync falhou: \(error.localizedDescription)")
            return false
        }
    }

    // MARK: - Escrita

    private func writeNote(
        title: String,
        segments: [String],
        bodyHTML: String,
        modDate: String,
        noteID: String,
        paths: inout [String: String],
        tags: [String],
        dryRun: Bool
    ) throws -> URL {
        let vaultRoot = config.vaultURL
        let targetDir = vaultDir(segments, dryRun: dryRun)
        let (file, aliases) = try VaultPaths.resolveHumanNotePath(
            title: title,
            segments: segments,
            noteID: noteID,
            pathsMap: paths,
            vaultRoot: vaultRoot,
            targetDir: targetDir,
            flatFolders: config.flatFolderSet,
            dryRun: dryRun
        )

        if dryRun { return file }

        let attachments = file.deletingLastPathComponent().appendingPathComponent("_attachments")
        let content = renderer.render(html: bodyHTML, attachmentsDir: attachments, noteTitle: title)

        var frontmatter = "---\n"
        frontmatter += "title: \"\(title)\"\n"
        frontmatter += "folder: \"\(segments.joined(separator: "/"))\"\n"
        frontmatter += "source: Apple Notes\n"
        frontmatter += "note_id: \"\(noteID)\"\n"
        frontmatter += "synced_at: \"\(Dates.isoString(timeZone: config.timeZone))\"\n"
        frontmatter += "apple_notes_modified: \"\(modDate)\"\n"
        frontmatter += VaultPaths.formatAliasesYAML(aliases)
        if !tags.isEmpty {
            frontmatter += "tags:\n" + tags.map { "  - \"\($0)\"" }.joined(separator: "\n") + "\n"
        }
        frontmatter += "---\n\n"

        do {
            try (frontmatter + content).write(to: file, atomically: true, encoding: .utf8)
        } catch {
            throw VaultError.fileOperation("Não foi possível gravar \(file.lastPathComponent): \(error.localizedDescription)")
        }

        paths[noteID] = Paths.relativePath(of: file, in: vaultRoot)
        return file
    }

    private func vaultDir(_ segments: [String], dryRun: Bool) -> URL {
        var base = config.vaultURL
        if !config.syncRoot.isEmpty {
            base.appendPathComponent(config.syncRoot)
        }
        let flat = segments.count == 1 && config.flatFolderSet.contains(segments[0].lowercased())
        if !flat {
            for segment in segments {
                base.appendPathComponent(VaultPaths.sanitizeTitle(segment))
            }
        }
        if !dryRun {
            try? FileManager.default.createDirectory(at: base, withIntermediateDirectories: true)
        }
        return base
    }

    // MARK: - Fetch

    private func fetchBodies(_ pending: [NoteMeta], tree: [String: [String]]) -> [String: FetchedNote] {
        log("     Buscando conteúdo (\(pending.count) notas, \(config.fetchWorkers) workers paralelos)...")
        let bodies = notes.fetchBodies(notes: pending, workers: config.fetchWorkers) { [weak self] current, total, _ in
            self?.emitProgress(ProgressInfo(current: current, total: total))
        }
        let failed = pending.count - bodies.count
        if failed > 0 { log("  !! \(failed) nota(s) sem conteúdo") }
        log("     Conteúdo obtido: \(bodies.count)/\(pending.count)")
        return bodies
    }

    private func emitProgress(_ progress: ProgressInfo) {
        progressLock.lock()
        defer { progressLock.unlock() }
        onProgress?(progress)
        StateStore.writeProgress(config: config, progress)
    }

    // MARK: - Checkpoint

    private func saveCheckpoint(
        pendingIDs: [String],
        doneIDs: [String],
        state: [String: Any],
        ids: [String: String],
        paths: [String: String],
        dirtyPaths: [String],
        created: Int,
        updated: Int
    ) {
        let object: [String: Any] = [
            "saved_at": Dates.isoString(),
            "pending_ids": pendingIDs,
            "done_ids": doneIDs,
            "state": state,
            "ids": ids,
            "paths": paths,
            "dirty_paths": dirtyPaths,
            "created": created,
            "updated": updated
        ]
        JSONFile.write(object, to: config.checkpointURL)
    }

    // MARK: - Banco do Notes

    private func notesDBChanged() -> Bool {
        let db = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Library/Group Containers/group.com.apple.notes/NoteStore.sqlite")
        guard let attributes = try? FileManager.default.attributesOfItem(atPath: db.path),
              let modified = attributes[.modificationDate] as? Date else {
            return true
        }
        let saved = JSONFile.object(at: config.stateFileURL)
        let last = (saved["_last_sync_epoch"] as? NSNumber)?.doubleValue ?? 0
        if modified.timeIntervalSince1970 <= last {
            log("     NoteStore.sqlite inalterado desde o último sync — pulando")
            return false
        }
        return true
    }

    // MARK: - Suporte

    private var secretsGuard: SecretsGuard {
        SecretsGuard(enabled: config.secretsEnabled, extraFolders: Set(config.secretFolders))
    }

    private func ensureDirs() {
        try? FileManager.default.createDirectory(at: config.stateURL, withIntermediateDirectories: true)
        try? FileManager.default.createDirectory(at: config.vaultURL, withIntermediateDirectories: true)
    }

    private func log(_ message: String, verboseOnly: Bool = false) {
        if verboseOnly && !PipelineEnvironment.verbose { return }
        logger.log(message)
        onLog?(message)
    }
}

enum PipelineEnvironment {
    static var verbose = false
}
