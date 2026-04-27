# VaultAI

Sincronização automática entre **Apple Notes** e **Obsidian** no macOS, com organização inteligente e menu bar nativa.

## ✨ Funcionalidades

- **Sync bidirecional** — Exporta notas do Apple Notes para o Obsidian preservando formatação, imagens e anexos
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

Para rodar o pipeline automaticamente a cada 5 minutos e ter a menu bar sempre disponível:

```bash
cp com.vaultai.pipeline.plist ~/Library/LaunchAgents/
cp com.vaultai.menubar.plist ~/Library/LaunchAgents/

launchctl load ~/Library/LaunchAgents/com.vaultai.pipeline.plist
launchctl load ~/Library/LaunchAgents/com.vaultai.menubar.plist
```

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
├── config.example.py        # Template de configuração
├── com.vaultai.pipeline.plist    # Launch agent (sync automático)
├── com.vaultai.menubar.plist     # Launch agent (menu bar)
├── sanitize_for_github.py   # Script de sanitização
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

### v1.0.0 (2024)
- Sync Apple Notes → Obsidian
- Menu bar nativa
- Organização por domínios
- Links contextuais bidirecionais
- Detecção de lixo
- Checkpointing para resumes

---

**Feito com ❤️ para usuários de macOS que amam Apple Notes e Obsidian**
