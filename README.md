# VaultAI

Sincronização automática entre **Apple Notes** e **Obsidian** no macOS — com app nativo em **Swift/SwiftUI**.

O app nativo (`Sources/VaultAI`) é a interface principal: dashboard, painel na menu bar, ajustes e agendamento próprio. Os scripts Python originais continuam no repositório como **legado/referência** e para uso via terminal (`pipeline.py`, `notes_to_obsidian.py`, `organize_vault.py`).

## ✨ Funcionalidades

- **Sync Apple Notes → Obsidian** — exporta notas preservando formatação, imagens e anexos (unidirecional)
- **Organização automática** — MOC por domínio em `_index/` e links por título citado ou tag em comum
- **Detecção de lixo** — move notas vazias ou com nomes genéricos para `_lixo`
- **App nativo** — dashboard SwiftUI com progresso, métricas, pausa, sync completo e simulação (dry-run)
- **Menu bar** — estado do sync, atalhos e ações rápidas
- **Agendamento próprio** — timer nativo no intervalo configurado; sem LaunchAgent
- **Iniciar com o sistema** — item de login via `SMAppService`
- **Incremental** — processa só notas novas/modificadas desde o último sync
- **Resiste a falhas** — checkpointing retoma syncs interrompidos
- **Privacidade** — notas com senha/token/API key ficam só no Apple Notes; tudo roda local

## 📋 Pré-requisitos

- **macOS** 13 (Ventura) ou superior
- **Swift 5.9+** (Xcode Command Line Tools ou Xcode)
- **Apple Notes** (app nativo)
- **Obsidian** (opcional, para visualizar o vault)
- Python 3.9+ apenas para o pipeline legado

## 🚀 Instalação

### 1. Clone o repositório

```bash
git clone https://github.com/francieloliveira/apple-notes-to-obsidian.git
cd apple-notes-to-obsidian
```

### 2. Compile e teste

```bash
make test     # swift test (10 testes)
make app      # gera build/VaultAI.app
```

### 3. Instale

```bash
make install  # instala em /Applications e remove LaunchAgents antigos
open /Applications/VaultAI.app
```

`scripts/install.sh` monta o bundle Release, instala em `/Applications/VaultAI.app` (ou `~/Applications` se não houver permissão), registra no LaunchServices, indexa no Spotlight e remove os LaunchAgents `com.vaultai.pipeline` / `com.vaultai.menubar` para não sincronizar duas vezes.

### 4. Permissão de Automação

No primeiro sync o macOS pergunta se o VaultAI pode controlar o **Notes**. Autorize.

Se negar por engano: **Ajustes do Sistema → Privacidade e Segurança → Automação → VaultAI → Notes**.

### 5. Abra o dashboard

```bash
open /Applications/VaultAI.app
```

O app abre o dashboard e mantém o ícone na menu bar. Fechar a janela não encerra o app: use **Sair** no painel da menu bar (ou ⌘Q).

---

## 🖥️ App nativo (Swift)

| Camada | Arquivo | Papel |
|---|---|---|
| Entrada/UI | `Sources/VaultAI/App/VaultAIApp.swift` | Scenes: dashboard, menu bar, ajustes |
| Estado | `Sources/VaultAI/App/AppModel.swift` | Polling, sync, pausa, item de login |
| Orquestração | `Sources/VaultAI/Core/Pipeline.swift` | Lock, sync → organize, status, notificação |
| Sync | `Sources/VaultAI/Core/VaultSync.swift` | Porta de `notes_to_obsidian.py` |
| Organize | `Sources/VaultAI/Core/VaultOrganizer.swift` | Porta de `organize_vault.py` |
| Apple Notes | `Sources/VaultAI/Core/AppleNotesService.swift` | AppleScript em paralelo |
| Markdown | `Sources/VaultAI/Core/MarkdownRenderer.swift` | HTML → Markdown, imagens, checklists |
| Estado | `Sources/VaultAI/Core/StateStore.swift` | `status.json`, `progress.json`, métricas |
| Visual | `Sources/VaultAI/UI/` | Tema, dashboard, menu bar, ajustes |

O app mantém o mesmo formato de estado em `~/.vault` do pipeline Python (`status.json`, `metrics.json`, `notes_state.json`, `note_paths.json`, `sync_checkpoint.json`). É seguro alternar entre o app e o pipeline legado.

### Desenvolvimento

```bash
swift build
swift test
./scripts/build-app.sh debug
# roda com estado e vault temporários, sem tocar no vault real:
VAULTAI_STATE_DIR=/tmp/vaultai-state VAULT_PATH=/tmp/VaultAITest \
  ./build/VaultAI.app/Contents/MacOS/VaultAI
```

### Configuração

O app lê, nesta ordem: padrões → `config.py` legado (apenas atribuições simples) → `~/.vault/config.json` → variáveis de ambiente. A tela **Ajustes** (⌘,) grava `~/.vault/config.json`.

| Variável | Padrão | Descrição |
|---|---|---|
| `VAULT_PATH` | `~/VaultAI` | Caminho do vault Obsidian |
| `VAULTAI_STATE_DIR` | `~/.vault` | Diretório de estado/logs |
| `VAULT_SYNC_ROOT` | vazio | Subpasta do vault (ex.: `Notes`) |

---

## 📖 Como Funciona

### Pipeline de Sincronização

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Apple Notes    │ ──→ │  notes_to_       │ ──→ │  Obsidian Vault │
│  (macOS)        │     │  obsidian.py     │     │  (markdown)     │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                               │
                               ▼
                        ┌──────────────────┐
                        │  organize_vault  │
                        │  - Links         │
                        │  - Domínios      │
                        │  - Limpeza       │
                        └──────────────────┘
```

### Etapas do Sync

1. **Export** — Lê metadados de todas as notas no Apple Notes via AppleScript
2. **Fetch** — Baixa conteúdo de notas novas/modificadas (paralelo, 8 workers)
3. **Convert** — Converte HTML do Notes para Markdown, extrai imagens como arquivos
4. **Organize** — `find_links` (título citado ou tag), `generate_moc` (domínio em `_index/`), move lixo
5. **Notify** — Notificação macOS com resumo (notas criadas/atualizadas)

### Domínios Pré-configurados

A tabela é o `DOMAIN_KEYWORDS` de `config.example.py`. O sync importa o `config.py` local — edite esse, não o example.

| Domínio | Keywords |
|---------|----------|
| `tech` | python, java, javascript, docker, kubernetes |
| `cloud` | aws, azure, gcp, lambda, s3 |
| `ai` | llm, machine learning, transformer, embedding |
| `devops` | ci/cd, pipeline, deploy, terraform |
| `sql` | select, postgresql, mysql, sqlite |
| `git` | git commit, git push, github, branch, pull request |
| `scrum` | scrum, sprint, backlog, user story |

---

## 🎯 Uso

### Dashboard

A janela principal mostra estado, atividade, progresso, métricas do último sync e ações:

- **Sincronizar agora** (⌘R) — sync incremental
- **Sync completo** (⇧⌘R) — reprocessa o vault inteiro
- **Simular** — dry-run, sem gravar nada
- **Pausar / Retomar** — grava/apaga `~/.vault/sync_paused`
- **Abrir vault** / **Abrir log** — abrem no Finder/TextEdit
- **Ajustes** (⌘,) — vault, intervalo, workers, privacidade e domínios

### Menu bar

O ícone reflete o estado (sincronizando, erro, pausa) e abre um painel com progresso, métricas rápidas, **Sincronizar agora**, pausa, abrir app e sair.

### Terminal (pipeline legado)

Os scripts Python continuam funcionando e compartilham o mesmo estado:

```bash
# Sync normal (apenas notas novas/modificadas)
"$PYTHON" ~/IntegraNotesMacObsidian/pipeline.py

# Sync completo: --full reprocessa o vault inteiro
"$PYTHON" ~/IntegraNotesMacObsidian/pipeline.py --full

# Dry run (simulação)
"$PYTHON" ~/IntegraNotesMacObsidian/pipeline.py --dry-run
```

---

## 📁 Estrutura do Projeto

```
apple-notes-to-obsidian/
├── Package.swift            # Swift Package Manager (app + testes)
├── Makefile                 # build, app, run, test, install
├── Sources/VaultAI/
│   ├── App/                 # VaultAIApp, AppModel
│   ├── Core/                # Pipeline, VaultSync, VaultOrganizer, Notes, Estado
│   └── UI/                  # Dashboard, MenuPanel, Settings, Theme
├── tests/VaultAITests/      # Testes Swift (XCTest)
├── Resources/Info.plist     # Bundle do app
├── scripts/
│   ├── build-app.sh         # Monta build/VaultAI.app
│   └── install.sh           # Instala e remove LaunchAgents antigos
├── pipeline.py              # [legado] Orquestrador: sync → organize
├── notes_to_obsidian.py     # [legado] Export Apple Notes → Markdown
├── organize_vault.py        # [legado] Organização e links
├── utils.py                 # [legado] Utilitários
├── vaultai_dashboard.py     # [legado] Dashboard Tkinter
├── vault_menubar.py         # [legado] Ícone da menu bar (rumps)
├── install.sh               # [legado] Instalação Python
├── config.example.py        # Template de configuração legada
├── config.py                # Configuração local (não versionado)
├── VaultAI.icns             # Ícone do app
└── README.md
```

`build/VaultAI.app` é gerado por `make app`; o app instalado fica em `/Applications/VaultAI.app`. O estado compartilhado fica em `~/.vault`.

---

## ⚙️ Configuração Avançada

### Variáveis de Ambiente

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `VAULT_PATH` | `~/VaultAI` | Caminho do vault Obsidian |
| `VAULTAI_STATE_DIR` | `~/.vault` | Diretório de estado e logs |
| `VAULT_SYNC_ROOT` | vazio | Subpasta do vault (ex.: `Notes`) |
| `SCRIPTS_DIR` | `~/IntegraNotesMacObsidian` | [legado] Diretório dos scripts Python |
| `VAULTAI_HOME` | `~/IntegraNotesMacObsidian` | [legado] Repositório do pipeline Python |

### Arquivos de Estado (não versionados)

O VaultAI mantém estado em `~/.vault/`:

```
~/.vault/
├── pipeline.log           # Log do orquestrador
├── sync.log               # Log detalhado do sync
├── organize.log           # Log da organização
├── config.json            # Configuração nativa (Ajustes)
├── status.json            # Estado lido pelo dashboard
├── sync_paused            # Presente = sync automático desativado
├── metrics.json           # Últimas métricas do sync
├── notes_state.json       # Estado das notas (timestamps)
├── notes_ids.json         # Mapeamento de IDs
├── vault_dirty.json       # Notas modificadas (delta)
├── note_paths.json        # note_id → caminho do .md
├── organize_metrics.json  # Estatísticas do organize
└── sync_checkpoint.json   # Checkpoint para resume
```

Estes arquivos são ignorados pelo `.gitignore` — não os versionar.

---

## 🛠️ Troubleshooting

### O app não abre

```bash
make app
open build/VaultAI.app
```

Se o app instalado estiver desatualizado:

```bash
make install
open /Applications/VaultAI.app
```

Verifique também se o processo já está rodando (`pgrep -fl VaultAI`). O app é um agente de menu bar: fechar a janela não encerra o processo.

### Sync automático não pausa / retoma

O estado é persistido em `~/.vault/sync_paused`. O botão Pausar/Retomar do app grava ou apaga esse arquivo e para o timer nativo. O pipeline legado também respeita o arquivo. Se precisar fazer manualmente:

```bash
# Pausar
touch ~/.vault/sync_paused

# Retomar
rm -f ~/.vault/sync_paused

# Log aberto pelo botão "Abrir log"
tail -f ~/.vault/pipeline.log
```

### Sync falha com erro de AppleScript

1. Abra **Apple Notes** manualmente
2. Conceda permissão de automação em:
   **System Settings → Privacy & Security → Automation → Notes**
3. Tente novamente

### Notas não estão sendo exportadas

Verifique os logs:

```bash
tail -100 ~/.vault/sync.log
```

Problemas comuns:
- Notes.app não está rodando (o app tenta abrir automaticamente)
- Permissão de automação não concedida (Ajustes → Privacidade e Segurança → Automação)
- Path do vault incorreto em `~/.vault/config.json`

### Links não estão sendo criados

`find_links` em `organize_vault.py` cria o link inline se o título da outra nota aparece no texto (`title_mentioned`, word boundary, mínimo `MIN_TITLE_CHARS`) ou se há tag em comum. O teto é `MAX_INLINE_LINKS`.

Domínio não entra nesse critério. `generate_moc` usa o domínio só para o MOC em `_index/` (`MOC_DIR`).

---

## 🤖 Integração com Claude (MCP)

Conecte o Claude diretamente ao seu vault Obsidian para buscar notas, explorar links e obter contexto sobre seu conhecimento acumulado — tudo sem sair do chat.

### Como funciona

O VaultAI expõe o vault via **Obsidian Local REST API** (plugin da comunidade), que o Claude acessa via **MCP (Model Context Protocol)**. Com isso, o Claude pode listar arquivos, ler notas com frontmatter, backlinks e tags, e executar buscas semânticas dentro do vault.

### 1. Instale o plugin Obsidian Local REST API

1. Abra o Obsidian → **Settings → Community Plugins → Browse**
2. Busque por **"Local REST API"** (autor: Adam Coddington)
3. Instale e ative o plugin
4. Em **Settings → Local REST API**:
   - Habilite **"Enable Non-encrypted (HTTP) Server"**
   - Anote a porta (padrão: `27123`)
   - Anote o **API Key** gerado automaticamente

### 2. Instale o servidor MCP

```bash
npm install -g @swarogan/obsidian-mcp-rest
```

### 3. Configure o Claude Desktop

Edite `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "obsidian-rest": {
      "command": "/opt/homebrew/bin/node",
      "args": [
        "/opt/homebrew/lib/node_modules/@swarogan/obsidian-mcp-rest/dist/index.js"
      ],
      "env": {
        "OBSIDIAN_REST_URL": "http://localhost:27123",
        "OBSIDIAN_API_KEY": "SUA_API_KEY_AQUI",
        "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
      }
    }
  }
}
```

> Substitua `SUA_API_KEY_AQUI` pelo token exibido no painel do plugin.

### 4. Reinicie o Claude Desktop

Após salvar o arquivo de configuração, reinicie o Claude para que o MCP seja carregado.

### O que o Claude passa a conseguir fazer

Com o vault conectado, você pode perguntar ao Claude coisas como:

- _"O que eu tenho de notas sobre Kubernetes?"_
- _"Mostre minha nota sobre o projeto X"_
- _"Quais notas estão linkadas com a nota Y?"_
- _"Liste tudo que está na pasta `cloud`"_

### Segurança

O servidor HTTP do plugin escuta **somente em `localhost`** — nenhum acesso externo é possível. A API Key autentica cada requisição. Nenhum dado sai do seu Mac.

---

## 🔒 Segurança e Privacidade

- **Nenhum dado sai do seu Mac** — Todo processamento é local
- **Sem APIs externas** — Usa apenas AppleScript e filesystem
- **Estado local** — Arquivos de estado em `~/.vault/` não são versionados
- **Imagens locais** — Anexos são salvos em `_attachments/` dentro do vault

---

## 🧪 Desenvolvimento

### Rodar em modo de desenvolvimento

```bash
# Clone e instale localmente
git clone https://github.com/francieloliveira/apple-notes-to-obsidian.git
cd apple-notes-to-obsidian

# Use paths locais
export SCRIPTS_DIR=$(pwd)
export VAULT_PATH=~/TestVault

# Rode sem instalar
python3 pipeline.py --verbose
```

### Sanitizar para publicar

Se modificar o projeto e quiser publicar:

```bash
python3 sanitize_for_github.py
```

Remove paths hardcoded, nomes de usuário e keywords sensíveis.

---

## 📄 Licença

MIT — Ver arquivo [LICENSE](LICENSE)

---

## 🙋 Contribuição

Contribuições são bem-vindas! Abra uma issue ou PR para:

- Novos domínios de organização
- Melhorias na conversão HTML → Markdown
- Correção de bugs
- Documentação

---

## 📝 Changelog

### v1.5.0 (2026-07) — menu bar

`install.sh` carrega `vault_menubar.py` (`com.vaultai.menubar`, python de `agent_python`). `ensure_app` abre a janela `vaultai_dashboard.py` com `/usr/bin/python3`, não o cubo.

- Ícone de cubo e status no dropdown: `vault_menubar.py`
- Menu com seções e submenus: nesse arquivo
- Sync automático com `~/.vault/sync_paused` (a janela também grava esse arquivo em Pausar/Retomar)
- Preferência de login em `~/.vault/login_disabled`: só `vault_menubar.py`. A janela não tem esse toggle
- O atalho `~/Applications/VaultAI.app` reabre a janela (`ensure_app`), não a menu bar
- `assets/menubar_icon.png` é o ícone (`MENUBAR_ICON_PATH`). `install.sh` não chama `generate_menubar_icon`

### v1.4.0 (2026-07) — Política B de títulos
- Arquivos legíveis: `Backup & Restore.md` (sem `_a1b2c3d4` no nome)
- Colisão de títulos: o arquivo ganha um rótulo entre parênteses. `note_id_slug` não entra no nome
- URL como título vira slug
- `aliases:` preserva nomes antigos para links no Obsidian
- Organize linka pelo nome legível; busca no texto usa `title` do frontmatter

### v1.3.0 (2026-07)
- ~~Arquivos com sufixo `note_id`~~ (substituído pela política B em v1.4)
- `note_paths.json` rastreia caminho de cada nota; migra arquivos legados automaticamente
- Checkpoint corrigido (resume por `note_id`)
- Sync skip limpa `vault_dirty.json` e zera métricas
- Pipeline não depende da menu bar (fechar a UI não pausa o sync). O ícone é `vault_menubar.py`, carregado à parte
- Organize indexa por `note_id`; limpa dirty após processar
- `organize_metrics.json` com estatísticas da organização
- MOCs delta: `generate_moc` recebe só os domínios afetados no modo incremental. Isso não cria link
- Logs abertos no TextEdit; testes em `tests/`

### v1.2.0 (2026)
- `install.sh` unificado: venv do pipeline, LaunchAgent e rotação de logs
- `requirements.txt` com dependências documentadas
- Rotação automática de logs em `~/.vault/` (> 5 MB)
- Nesta versão o Python foi unificado via `.venv`. Hoje a janela não usa esse python: `install.sh` chama `/usr/bin/python3` em `ensure_app`. O venv do pipeline é `pipeline_venv_dir`
- O LaunchAgent `com.franciel.vault-menubar` chegou a virar `com.vaultai.menubar`. O `install.sh` atual carrega esse label com o python de `pipeline_venv_dir`, não com um `.venv` do repositório
- `vault_menubar.py` lê `VAULT_PATH` do `config.py`. O install inicia esse arquivo

### v1.1.0 (2025)
- Integração MCP com Claude Desktop via Obsidian Local REST API
- Tags do frontmatter entram no conjunto de domínio em `collect_all_notes`. Isso alimenta `generate_moc`, não `find_links`
- `find_links` liga só por título citado (`title_mentioned`) ou tag em comum. Pasta do Apple Notes não é critério de link
- Domínio não é critério de `find_links`. `generate_moc` escreve o MOC em `_index/`
- Estatísticas detalhadas no organize_vault.py
- Correção de bug: re-sync desnecessário de todas as notas por comparação de datas inconsistente

### v1.0.0 (2024)
- Sync Apple Notes → Obsidian
- Menu bar: `vault_menubar.py`, carregado por `install.sh` (`com.vaultai.menubar`). A janela é outro processo (`ensure_app`)
- Domínio no MOC (`generate_moc`), não como critério de `find_links`
- Links por título citado ou tag (`find_links`)
- Detecção de lixo
- Checkpointing para resumes

---

**Feito com ❤️ para usuários de macOS que amam Apple Notes e Obsidian**
