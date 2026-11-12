# VaultAI — Guia de Instalação

## Pré-requisitos

- macOS 13 (Ventura) ou superior
- Swift 5.9+ (Xcode Command Line Tools ou Xcode)
- Apple Notes instalado
- Python 3.9+ apenas para o pipeline legado

## Instalação rápida

```bash
git clone https://github.com/francieloliveira/apple-notes-to-obsidian.git
cd apple-notes-to-obsidian

make test     # swift test
make app      # gera build/VaultAI.app
make install  # instala em ~/Applications
open ~/Applications/VaultAI.app
```

O `scripts/install.sh` faz tudo:

1. Compila o app em Release
2. Copia o bundle para `~/Applications/VaultAI.app` e cria o atalho `/Applications/VaultAI.app`
3. Remove os LaunchAgents antigos (`com.vaultai.pipeline`, `com.vaultai.menubar`) para não sincronizar duas vezes

## Primeiro sync

O macOS pede permissão para o VaultAI controlar o **Notes** na primeira leitura. Autorize.

Se negar por engano: **Ajustes do Sistema → Privacidade e Segurança → Automação → VaultAI → Notes**.

## Após instalar

- O dashboard abre com `open ~/Applications/VaultAI.app`
- O ícone fica na menu bar; fechar a janela não encerra o app
- O sync automático roda no intervalo configurado em **Ajustes** (padrão: 30 min)
- **Iniciar com o sistema** registra o app como item de login (`SMAppService`)

## Reinstalar após mudanças no código

```bash
make install
```

## Arquivos de preferência

| Arquivo | Significado |
|---------|-------------|
| `~/.vault/config.json` | Configuração do app (Ajustes) |
| `~/.vault/sync_paused` | Sync automático desativado |

## Logs úteis

```bash
tail -f ~/.vault/pipeline.log   # orquestrador (botão "Abrir log")
tail -f ~/.vault/sync.log       # exportação Apple Notes
tail -f ~/.vault/organize.log   # links, MOCs e limpeza
```

## Pipeline legado (Python)

Os scripts continuam no repositório e compartilham o mesmo estado:

```bash
"$PYTHON" pipeline.py            # sync incremental
"$PYTHON" pipeline.py --full     # reprocessa o vault inteiro
"$PYTHON" pipeline.py --dry-run  # simulação
```
