# VaultAI

Sincronização automática entre **Apple Notes** e **Obsidian** no macOS, com organização inteligente e menu bar nativa.

## ✨ Funcionalidades

- **Sync Apple Notes → Obsidian** — Exporta notas preservando formatação, imagens e anexos (unidirecional)
- **Organização automática** — Classifica notas por domínio (tech, cloud, AI, devops, etc.) e cria links contextuais
- **Detecção de lixo** — Move automaticamente notas vazias ou com nomes genéricos para pasta `_lixo`
- **Menu bar nativa** — Acompanhe o status do sync, execute sincronizações manuais e acesse logs diretamente da menu bar
- **Incremental** — Processa apenas notas novas ou modificadas desde o último sync
- **Resumo a falhas** — Checkpointing permite retomar syncs interrompidos

## 📋 Pré-requisitos

- **macOS** 12.0 (Monterey) ou superior
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

O script cria um `.venv` local, instala dependências, configura os LaunchAgents
(sync a cada 30 min + menu bar no login), cria o atalho `~/Applications/VaultAI.app`
e rotaciona logs grandes.

### 4. Verifique a menu bar

Após o install, o ícone de **cubo** (BD) deve aparecer na menu bar automaticamente.

Para reiniciar manualmente:

```bash
# Opção 1 — atalho em Aplicações (recomendado)
open ~/Applications/VaultAI.app

# Opção 2 — direto pelo Python
~/IntegraNotesMacObsidian/.venv/bin/python3 ~/IntegraNotesMacObsidian/vault_menubar.py

# Opção 3 — reinstalar tudo
./install.sh
```

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
4. **Organize** — Detecta domínio, cria links contextuais, move lixo
5. **Notify** — Notificação macOS com resumo (notas criadas/atualizadas)

### Domínios Pré-configurados

O organizador detecta automaticamente notas sobre:

| Domínio | Keywords |
|---------|----------|
| `tech` | python, java, javascript, docker, kubernetes |
| `cloud` | aws, azure, gcp, lambda, s3 |
| `ai` | llm, machine learning, transformer, embedding |
| `devops` | ci/cd, pipeline, deploy, terraform |
| `scrum` | scrum, sprint, backlog, product owner |
| `sql` | select, insert, postgresql, mysql |
| `git` | git commit, github, branch, pull request |

Edite `config.py` para adicionar seus próprios domínios.

---

## 🎯 Uso

### Via Menu Bar (Recomendado)

Clique no ícone de **cubo** na menu bar. O estado detalhado fica no menu dropdown:

```
VaultAI
— Status —
●  Atualizado
1 nova
◷  Último sync há 5 min · 23s
●  Automático: ativado · a cada 30 min
─────────────────
Sincronizar  ▸  Agora | Completo | Simular
Abrir        ▸  Vault | Log pipeline | Log sync
─────────────────
— Configurações —
✓ Sync automático (30 min) — Ativado
✓ Iniciar com o sistema — Ativado
Abrir atalho em Aplicações (VaultAI)
─────────────────
Sair
```

**Ações principais:**

| Item | Descrição |
|------|-----------|
| **Sincronizar → Agora** | Sync imediato (apenas notas novas/modificadas) |
| **Sincronizar → Completo** | Reprocessa todo o vault (`--full`) |
| **Sincronizar → Simular** | Dry run — mostra o que seria feito |
| **Sync automático** | Liga/desliga o agendamento a cada 30 min (✓ = ativo) |
| **Iniciar com o sistema** | Liga/desliga abertura automática no login |
| **Abrir atalho em Aplicações** | Abre o Finder em `VaultAI.app` |

As preferências de sync e login são persistidas em `~/.vault/sync_paused` e
`~/.vault/login_disabled`.

### Via Terminal

```bash
# Sync normal (apenas notas novas/modificadas)
~/IntegraNotesMacObsidian/.venv/bin/python3 ~/IntegraNotesMacObsidian/pipeline.py

# Sync completo (reprocessa tudo + renomeia arquivos com note_id)
~/IntegraNotesMacObsidian/.venv/bin/python3 ~/IntegraNotesMacObsidian/pipeline.py --full

# Dry run (simulação)
~/IntegraNotesMacObsidian/.venv/bin/python3 ~/IntegraNotesMacObsidian/pipeline.py --dry-run

# Testes
~/IntegraNotesMacObsidian/.venv/bin/python3 -m unittest discover -s tests
```

---

## 📁 Estrutura do Projeto

```
apple-notes-to-obsidian/
├── pipeline.py              # Orquestrador principal
├── notes_to_obsidian.py     # Export Apple Notes → Markdown
├── organize_vault.py        # Organização e links
├── vault_menubar.py         # App da menu bar
├── utils.py                 # Utilitários (logs, nomes de arquivo, etc.)
├── install.sh               # Instalação unificada (venv + LaunchAgents + atalho)
├── requirements.txt         # Dependências Python
├── assets/
│   ├── menubar_icon.png     # Ícone do cubo na menu bar
│   └── generate_menubar_icon.py
├── tests/                   # Testes unitários
├── config.py                # Configuração centralizada (não versionado)
├── config.example.py        # Template de configuração
├── sanitize_for_github.py   # Script de sanitização para publicação
└── README.md
```

---

## ⚙️ Configuração Avançada

### Variáveis de Ambiente

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `VAULT_PATH` | `~/VaultAI` | Caminho do vault Obsidian |
| `SCRIPTS_DIR` | `~/IntegraNotesMacObsidian` | Diretório dos scripts |
| `VAULTAI_HOME` | `~/IntegraNotesMacObsidian` | Repositório + `.venv` |

### Arquivos de Estado (não versionados)

O VaultAI mantém estado em `~/.vault/`:

```
~/.vault/
├── pipeline.log           # Log do orquestrador
├── sync.log               # Log detalhado do sync
├── organize.log           # Log da organização
├── menubar.log            # Log do app da menu bar
├── status.json            # Status atual (lido pela menu bar)
├── sync_paused            # Presente = sync automático desativado
├── login_disabled         # Presente = não abrir no login
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

### Menu bar não aparece

```bash
# Recomendado — atalho criado pelo install.sh
open ~/Applications/VaultAI.app

# Alternativas
./install.sh
~/IntegraNotesMacObsidian/.venv/bin/python3 ~/IntegraNotesMacObsidian/vault_menubar.py
```

Se você desativou **Iniciar com o sistema**, o ícone some ao fechar — use o
`VaultAI.app` em `~/Applications/` para reabrir.

### Sync automático não pausa / retoma

O estado é persistido em `~/.vault/sync_paused`. Se o toggle falhar, verifique:

```bash
# Pausar manualmente
touch ~/.vault/sync_paused
launchctl bootout gui/$(id -u)/com.vaultai.pipeline

# Retomar manualmente
rm -f ~/.vault/sync_paused
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.vaultai.pipeline.plist

# Log de erros do menu bar
cat ~/.vault/menubar.log
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

O organizador só cria links para notas com **domínio detectado**. Adicione keywords ao seu `config.py`:

```python
DOMAIN_KEYWORDS = {
    "meu_domínio": ["palavra1", "palavra2"],
}
```

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

- **Nenhuma dados sai do seu Mac** — Todo processamento é local
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

### v1.5.0 (2026-07) — Menu bar redesenhada
- Ícone fixo de cubo (BD) na menu bar; status detalhado no dropdown
- Menu reorganizado com seções, submenus e checkmarks nativos do macOS
- Sync automático com preferência persistida (`~/.vault/sync_paused`)
- Correção do toggle de pausa (não reativa mais o sync ao reiniciar o app)
- `launchctl bootstrap/bootout` com verificação real do estado do agente
- **Iniciar com o sistema** com preferência persistida (`~/.vault/login_disabled`)
- Atalho `~/Applications/VaultAI.app` para reabrir o menu bar após desativar login
- Ícone gerado em `assets/menubar_icon.png` (template para tema claro/escuro)

### v1.4.0 (2026-07) — Política B de títulos
- Arquivos legíveis: `Backup & Restore.md` (sem `_a1b2c3d4` no nome)
- Colisão de títulos: `daily (Canal Motorista).md`
- URLs como título viram slug: `premium-dsv-outsystems.petrobras.com.br-S10865.md`
- `aliases:` preserva nomes antigos para links no Obsidian
- Organize linka pelo nome legível; busca no texto usa `title` do frontmatter

### v1.3.0 (2026-07)
- ~~Arquivos com sufixo `note_id`~~ (substituído pela política B em v1.4)
- `note_paths.json` rastreia caminho de cada nota; migra arquivos legados automaticamente
- Checkpoint corrigido (resume por `note_id`)
- Sync skip limpa `vault_dirty.json` e zera métricas
- Pipeline independente do menubar (fechar UI não pausa sync)
- Organize indexa por `note_id`; limpa dirty após processar
- `organize_metrics.json` com estatísticas da organização
- MOCs delta: só domínios afetados no modo incremental
- Logs abertos no TextEdit; testes em `tests/`

### v1.2.0 (2026)
- `install.sh` unificado: venv, deploy, LaunchAgents e rotação de logs
- `requirements.txt` com dependências documentadas
- Rotação automática de logs em `~/.vault/` (> 5 MB)
- Python unificado via `.venv` (corrige 3 interpretadores diferentes)
- LaunchAgent legado `com.franciel.vault-menubar` migrado para `com.vaultai.menubar`
- Menu bar usa `VAULT_PATH` do `config.py` (não mais hardcoded)

### v1.1.0 (2025)
- Integração MCP com Claude Desktop via Obsidian Local REST API
- Organização aprimorada: tags do frontmatter enriquecem domínios
- Links por pasta de origem (Apple Notes folder affinity)
- Critério de link relaxado: 1 domínio compartilhado (antes: 2)
- Geração de MOCs (Maps of Content) em `_index/` por domínio
- Estatísticas detalhadas no organize_vault.py
- Correção de bug: re-sync desnecessário de todas as notas por comparação de datas inconsistente

### v1.0.0 (2024)
- Sync Apple Notes → Obsidian
- Menu bar nativa
- Organização por domínios
- Links contextuais bidirecionais
- Detecção de lixo
- Checkpointing para resumes

---

**Feito com ❤️ para usuários de macOS que amam Apple Notes e Obsidian**
