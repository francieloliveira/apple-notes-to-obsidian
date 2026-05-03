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
VAULT_PATH = "~/VaultAI"  # Caminho para seu vault Obsidian
SCRIPTS_DIR = "/usr/local/bin"
```

### 3. Instale os scripts

```bash
sudo cp pipeline.py notes_to_obsidian.py organize_vault.py vault_menubar.py $SCRIPTS_DIR/
sudo chmod +x $SCRIPTS_DIR/*.py
```

### 4. Instale a dependência da menu bar

```bash
pip3 install rumps
```

### 5. Configure os Launch Agents (opcional)

Para rodar o pipeline automaticamente a cada 5 minutos e ter a menu bar sempre disponível,
você precisará criar os arquivos `.plist` manualmente (não estão no repo, pois contêm paths locais).

Crie `~/Library/LaunchAgents/com.vaultai.pipeline.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>          <string>com.vaultai.pipeline</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/pipeline.py</string>
    </array>
    <key>StartInterval</key>  <integer>300</integer>
    <key>RunAtLoad</key>      <false/>
    <key>StandardOutPath</key><string>/Users/SEU_USUARIO/.vault/launchd.log</string>
    <key>StandardErrorPath</key><string>/Users/SEU_USUARIO/.vault/launchd.log</string>
</dict>
</plist>
```

```bash
launchctl load ~/Library/LaunchAgents/com.vaultai.pipeline.plist
```

> Substitua `SEU_USUARIO` pelo seu nome de usuário macOS.

### 6. Inicie a menu bar

```bash
python3 $SCRIPTS_DIR/vault_menubar.py
```

O ícone 📓 aparecerá na menu bar. Clique para sincronizar manualmente ou acessar logs.

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

Clique no ícone 📓 na menu bar:

- **Sincronizar agora** — Executa sync imediato
- **Sync completo (--full)** — Processa todo o vault, não apenas notas novas
- **Dry run (simular)** — Mostra o que seria feito sem alterar nada
- **Ver log do pipeline** — Abre terminal com tail do log
- **Ver log do sync** — Log detalhado da exportação
- **Abrir vault no Finder** — Abre a pasta do Obsidian

### Via Terminal

```bash
# Sync normal (apenas notas novas/modificadas)
python3 /usr/local/bin/pipeline.py

# Sync completo (reprocessa tudo)
python3 /usr/local/bin/pipeline.py --full

# Dry run (simulação)
python3 /usr/local/bin/pipeline.py --dry-run

# Verbose
python3 /usr/local/bin/pipeline.py --verbose
```

---

## 📁 Estrutura do Projeto

```
apple-notes-to-obsidian/
├── pipeline.py              # Orquestrador principal
├── notes_to_obsidian.py     # Export Apple Notes → Markdown
├── organize_vault.py        # Organização e links
├── vault_menubar.py         # App da menu bar
├── config.py                # Configuração centralizada (não versionado)
├── config.example.py        # Template de configuração
├── sanitize_for_github.py   # Script de sanitização para publicação
├── .gitignore
└── README.md
```

---

## ⚙️ Configuração Avançada

### Variáveis de Ambiente

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `VAULT_PATH` | `~/VaultAI` | Caminho do vault Obsidian |
| `SCRIPTS_DIR` | `/usr/local/bin` | Onde os scripts estão instalados |

### Arquivos de Estado (não versionados)

O VaultAI mantém estado em `~/.vault/`:

```
~/.vault/
├── pipeline.log           # Log do orquestrador
├── sync.log               # Log detalhado do sync
├── organize.log           # Log da organização
├── status.json            # Status atual (lido pela menu bar)
├── notes_state.json       # Estado das notas (timestamps)
├── notes_ids.json         # Mapeamento de IDs
├── vault_dirty.json       # Notas modificadas (delta)
└── sync_checkpoint.json   # Checkpoint para resume
```

Estes arquivos são ignorados pelo `.gitignore` — não os versionar.

---

## 🛠️ Troubleshooting

### Menu bar não aparece

```bash
# Verifique se rumps está instalado
pip3 install rumps

# Rode manualmente para ver erros
python3 /usr/local/bin/vault_menubar.py
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
