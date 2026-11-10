# VaultAI

Sincronização automática entre **Apple Notes** e **Obsidian** no macOS, com organização inteligente. A janela é `ensure_app` em `vaultai_dashboard.py`. O ícone da menu bar é `vault_menubar.py`, subido pelo `install.sh` no venv do pipeline.

## ✨ Funcionalidades

- **Sync Apple Notes → Obsidian** — Exporta notas preservando formatação, imagens e anexos (unidirecional)
- **Organização automática** — Classifica por domínio no MOC (`generate_moc`, `_index/`) e cria links por título citado ou tag (`find_links`)
- **Detecção de lixo** — Move automaticamente notas vazias ou com nomes genéricos para pasta `_lixo`
- **Janela** — Acompanhe o sync com `open /Applications/VaultAI.app` (atalho do Finder; o bundle real continua em `~/Applications`)
- **Menu bar** — `install.sh` carrega `com.vaultai.menubar` (`vault_menubar.py`) com o python de `pipeline_venv_dir`, não com `/usr/bin/python3` e nunca com um `.venv` dataless. O ícone é `assets/menubar_icon.png`
- **Incremental** — Processa apenas notas novas ou modificadas desde o último sync
- **Resiste a falhas** — Checkpointing permite retomar syncs interrompidos

## 📋 Pré-requisitos

- **macOS** 13 (Ventura) ou superior — tags do Notes (`AS_FETCH_ONE` em `notes_to_obsidian.py`) existem a partir do Ventura
- **Python** 3.9+
- **Apple Notes** (app nativo do macOS)
- **Obsidian** (opcional, para visualizar o vault)

## 🚀 Instalação

### 1. Clone o repositório

```bash
git clone https://github.com/francieloliveira/apple-notes-to-obsidian.git
cd apple-notes-to-obsidian
```

### 2. Configure as variáveis de ambiente

Copie o template e ajuste conforme necessário:

```bash
cp config.example.py config.py
```

Edite `config.py` se quiser paths personalizados:

```python
VAULT_PATH = "~/VaultAI"       # Caminho para seu vault Obsidian
VAULTAI_HOME = "~/IntegraNotesMacObsidian"  # Repositório local
```

### 3. Instale tudo

```bash
chmod +x install.sh
./install.sh
```

`install.sh` cria o atalho `~/Applications/VaultAI.app` (`ensure_app` em `vaultai_dashboard.py`) e publica o mesmo bundle em `/Applications/VaultAI.app`, que é a pasta Aplicativos do Finder. O executável da janela chama `/usr/bin/python3`, nunca um python debaixo de `.venv`. O venv do pipeline vem de `pipeline_venv_dir`: `.venv` no repositório só se o projeto não está no iCloud; no iCloud fica em `~/Library/Application Support/VaultAI/venv`. O script instala as dependências nesse venv (`rumps` para a menu bar), configura o LaunchAgent do pipeline (intervalo `PIPELINE_INTERVAL_SECS` do `config.py`; no example, 1800 s = 30 min), carrega `com.vaultai.menubar` com esse mesmo python em `vault_menubar.py` e rotaciona logs grandes. A janela não herda esse python.

### 4. Ícone da menu bar

`install.sh` carrega `vault_menubar.py` com o python de `pipeline_venv_dir`. O ícone é `assets/menubar_icon.png` (`MENUBAR_ICON_PATH`). `install.sh` não chama `generate_menubar_icon`; se o png não existir, o rumps sobe sem imagem.

### 5. Abra a janela

```bash
open /Applications/VaultAI.app
```

O atalho é o de `ensure_app`: `exec /usr/bin/python3` na fonte `vaultai_dashboard.py`. `.venv/bin/python3` não abre a janela.

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

### Janela

Para acompanhar o sync, abra a janela ou use o ícone que `install.sh` sobe (`com.vaultai.menubar`).

```bash
open /Applications/VaultAI.app
```

`ensure_app` grava o executável que chama `vaultai_dashboard.py` com `/usr/bin/python3`. Não use `.venv/bin/python3` para abrir o app.

A janela mostra estado, mensagem, contagens do sync (`format_sync_line`), progresso e organize (`format_organize_line`). Botões: **Sincronizar agora** (`run_pipeline`, sem `--full`), **Pausar** / **Retomar** (grava ou apaga `~/.vault/sync_paused`), **Abrir vault**, **Abrir log** (`PIPELINE_LOG` no TextEdit). Não há sync completo, dry-run nem “iniciar com o sistema” nessa janela.

`vault_menubar.py` é o dropdown do ícone (cubo, Sincronizar, login). `install.sh` carrega `com.vaultai.menubar` com o python de `agent_python` / `pipeline_venv_dir`. Não é o executável da janela: a janela continua `exec /usr/bin/python3` via `ensure_app`.

### Terminal (pipeline — não abre a janela)

O python abaixo é o que `install.sh` imprime em “Pipeline venv” (`pipeline_venv_dir`). Fora do iCloud é o `.venv` do repositório; no iCloud é `~/Library/Application Support/VaultAI/venv`. Não é o interpreter da janela.

```bash
# Sync normal (apenas notas novas/modificadas)
"$PYTHON" ~/IntegraNotesMacObsidian/pipeline.py

# Sync completo: --full reprocessa o vault inteiro.
# O nome do .md segue sanitize_title_for_filename / resolve_human_note_path (política B).
# note_id_slug() não entra no nome — não há sufixo de hash.
"$PYTHON" ~/IntegraNotesMacObsidian/pipeline.py --full

# Dry run (simulação)
"$PYTHON" ~/IntegraNotesMacObsidian/pipeline.py --dry-run

# Testes. Não abre a janela.
/usr/bin/python3 -m unittest discover -s tests
```

---

## 📁 Estrutura do Projeto

```
apple-notes-to-obsidian/
├── vaultai_dashboard.py     # Entry point da janela. install.sh gera ~/Applications/VaultAI.app
├── pipeline.py              # Orquestrador: sync → organize
├── notes_to_obsidian.py     # Export Apple Notes → Markdown
├── organize_vault.py        # Organização e links
├── utils.py                 # Utilitários (logs, nomes de arquivo, note_id_slug)
├── config_import.py         # Importa config.py pelos nomes exigidos
├── vault_menubar.py         # Ícone da menu bar; install.sh carrega com agent_python
├── install.sh               # venv do pipeline + LaunchAgents + atalho da janela
├── requirements.txt         # Dependências Python
├── generate_vaultai_icon.py # Gera VaultAI.iconset; o install não chama
├── VaultAI.icns             # Ícone solto na raiz
├── VaultAI.iconset/         # Tamanhos usados pelo gerador
├── assets/
│   ├── menubar_icon.png     # Ícone do cubo (MENUBAR_ICON_PATH)
│   └── generate_menubar_icon.py
├── tests/                   # Testes unitários
├── config.py                # Configuração local (não versionado)
├── config.py.bak            # Backup local da taxonomia (não versionado)
├── config.example.py        # Template de configuração
├── sanitize_for_github.py   # Script de sanitização para publicação
├── README_SETUP.md
├── .gitignore
├── LICENSE
└── README.md
```

A janela instalada é `vaultai_dashboard.py`. `install.sh` gera `~/Applications/VaultAI.app` (`ensure_app`, bundle `com.vaultai.app`) e carrega `com.vaultai.menubar` (`vault_menubar.py`, python de `pipeline_venv_dir`). `pipeline.py` continua chamando `notes_to_obsidian.py` e `organize_vault.py`.

---

## ⚙️ Configuração Avançada

### Variáveis de Ambiente

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `VAULT_PATH` | `~/VaultAI` | Caminho do vault Obsidian |
| `SCRIPTS_DIR` | `~/IntegraNotesMacObsidian` | Diretório dos scripts |
| `VAULTAI_HOME` | `~/IntegraNotesMacObsidian` | Repositório. O venv do pipeline é `pipeline_venv_dir`, não um `.venv` fixo aqui |

### Arquivos de Estado (não versionados)

O VaultAI mantém estado em `~/.vault/`:

```
~/.vault/
├── pipeline.log           # Log do orquestrador
├── sync.log               # Log detalhado do sync
├── organize.log           # Log da organização
├── menubar.log            # vault_menubar.py, carregado por install.sh
├── status.json            # Lido pela janela (read_snapshot em vaultai_dashboard.py)
├── sync_paused            # Presente = sync automático desativado
├── login_disabled         # Só vault_menubar.py. A janela não lê. Presente = não iniciar o ícone com o sistema
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

### A janela não abre

```bash
open /Applications/VaultAI.app
./install.sh
```

O atalho em `~/Applications/VaultAI.app` é o de `ensure_app`: `exec /usr/bin/python3` na fonte `vaultai_dashboard.py`. Não há segundo bundle no repositório. `.venv/bin/python3` não abre a janela.

### Sync automático não pausa / retoma

O estado é persistido em `~/.vault/sync_paused`. Os botões Pausar/Retomar da janela (`vaultai_dashboard.py`) gravam ou apagam esse arquivo e chamam `launchctl` no agente do pipeline. Se falhar:

```bash
# Pausar manualmente
touch ~/.vault/sync_paused
launchctl bootout gui/$(id -u)/com.vaultai.pipeline

# Retomar manualmente
rm -f ~/.vault/sync_paused
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.vaultai.pipeline.plist

# Log que a janela abre (Abrir log). O ícone escreve em ~/.vault/menubar.log.
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
- Notes.app não está rodando (o script tenta abrir automaticamente)
- Permissão de automação não concedida
- Path do vault incorreto no `config.py`

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
