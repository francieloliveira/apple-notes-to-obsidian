# VaultAI — Guia de Instalação

## Pré-requisitos

- macOS 13 (Ventura) ou superior — tags do Notes (`AS_FETCH_ONE` em `notes_to_obsidian.py`) existem a partir do Ventura
- Python 3.9+
- Apple Notes instalado

## Instalação rápida

```bash
git clone https://github.com/francieloliveira/apple-notes-to-obsidian.git
cd apple-notes-to-obsidian

cp config.example.py config.py   # se ainda não existir
chmod +x install.sh
./install.sh
```

O `install.sh` faz tudo:

1. Cria o venv do pipeline (`pipeline_venv_dir`: fora do repositório se o projeto está no iCloud) e instala `rumps` + `markdownify`. A janela não usa esse python (`ensure_app` recebe o interpreter que importa `site`)
2. Configura o LaunchAgent `com.vaultai.pipeline` e carrega `com.vaultai.menubar` (`vault_menubar.py`, o mesmo python do venv)
3. Cria `~/Applications/VaultAI.app` (janela `vaultai_dashboard.py`, bundle `com.vaultai.app`)
4. Rotaciona logs grandes em `~/.vault/`

Não chama `generate_menubar_icon`. O ícone usado é o `assets/menubar_icon.png` que já está no disco.

## Após instalar

- A janela abre com `open /Applications/VaultAI.app`
- Sync automático roda no intervalo de `PIPELINE_INTERVAL_SECS` (no `config.example.py`, 1800 s = 30 min; o `install.sh` lê esse nome)

## Reabrir a janela

```bash
open /Applications/VaultAI.app
```

## Reinstalar após mudanças no código

```bash
./install.sh
```

## Arquivos de preferência

| Arquivo | Significado |
|---------|-------------|
| `~/.vault/sync_paused` | Sync automático desativado. A janela grava ou apaga este arquivo |
| `~/.vault/login_disabled` | Só `vault_menubar.py`. Presente = não iniciar o ícone com o sistema. A janela não lê |

Pausar/Retomar na janela (`vaultai_dashboard.py`) mexe em `sync_paused`, não em `login_disabled`.

## Logs úteis

```bash
tail -f ~/.vault/pipeline.log   # orquestrador; a janela abre este (Abrir log)
tail -f ~/.vault/sync.log       # exportação Apple Notes
```

## Ícone da menu bar

`install.sh` carrega `vault_menubar.py` com o python de `pipeline_venv_dir` (`agent_python`). Não chama `generate_menubar_icon`. A janela abre com `open /Applications/VaultAI.app` (symlink para `~/Applications/VaultAI.app`, `ensure_app`, `/usr/bin/python3`).
