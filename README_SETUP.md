# VaultAI — Guia de Instalação

## Pré-requisitos

- macOS 12.0+
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

1. Cria `.venv` e instala `rumps` + `markdownify`
2. Configura LaunchAgents (`com.vaultai.pipeline` + `com.vaultai.menubar`)
3. Cria `~/Applications/VaultAI.app` (atalho para reabrir o menu bar)
4. Gera o ícone `assets/menubar_icon.png`
5. Rotaciona logs grandes em `~/.vault/`

## Após instalar

- O ícone de **cubo** aparece na menu bar
- Sync automático roda a cada **30 min** (configurável em `config.py`)
- Clique no ícone para ver status, sincronizar manualmente e ajustar configurações

## Reabrir o menu bar

Se o ícone sumiu (ex.: desativou "Iniciar com o sistema"):

```bash
open ~/Applications/VaultAI.app
```

Ou pelo menu (se o app ainda estiver aberto): **Abrir atalho em Aplicações (VaultAI)**.

## Reinstalar após mudanças no código

```bash
./install.sh
```

## Arquivos de preferência

| Arquivo | Significado |
|---------|-------------|
| `~/.vault/sync_paused` | Sync automático desativado |
| `~/.vault/login_disabled` | Não abrir no login |

Remova o arquivo ou use os toggles no menu para reativar.

## Logs úteis

```bash
tail -f ~/.vault/pipeline.log   # orquestrador
tail -f ~/.vault/sync.log       # exportação Apple Notes
tail -f ~/.vault/menubar.log    # app da menu bar
```

## Regenerar o ícone da menu bar

```bash
.venv/bin/python3 assets/generate_menubar_icon.py
```