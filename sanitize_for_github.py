#!/usr/bin/env python3
"""
sanitize_for_github.py
Remove informações pessoais e sensíveis do projeto antes de publicar no GitHub.

O que este script faz:
1. Substitui paths hardcoded com nome de usuário por paths genéricos
2. Renomeia arquivos .plist removendo o nome do usuário
3. Oferece opção para generalizar keywords de domínio (clientes)
4. Cria config.example.py com template de configuração
5. Gera .gitignore adequado

Uso: python sanitize_for_github.py --dry-run   (apenas mostra o que será feito)
     python sanitize_for_github.py             (executa as alterações)
"""

import argparse
import os
import re
import shutil
from pathlib import Path

# ─── CONFIGURAÇÃO ────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.absolute()

# Mapeamento de substituições de paths
PATH_REPLACEMENTS = [
    ("/Users/francieloliveira/ValtAI/ValtAI", "~/VaultAI"),
    ("/Users/francieloliveira", "~"),
    ("/usr/local/bin", "${SCRIPTS_DIR}"),
]

# Keywords que podem ser nomes de clientes (domínios sensíveis)
CLIENT_KEYWORDS = {
    "petrobras": "cliente_energia",
    "mirante": "cliente_documento",
    "fiep": "cliente_industria",
    "iltec": "parceiro_tech",
    "ccee": "cliente_energia",
    "copel": "cliente_energia",
}

# Arquivos para modificar
FILES_TO_SANITIZE = [
    "notes_to_obsidian.py",
    "organize_vault.py",
    "pipeline.py",
    "vault_menubar.py",
]

# Arquivos para renomear
PLIST_RENAMES = {
    "com.franciel.vault-pipeline.plist": "com.vaultai.pipeline.plist",
    "com.franciel.vault-menubar.plist": "com.vaultai.menubar.plist",
}
# ─────────────────────────────────────────────────────────────────────────────


def sanitize_paths(content: str, dry_run: bool = False) -> tuple[str, int]:
    """Substitui paths hardcoded por versões genéricas."""
    count = 0
    for old, new in PATH_REPLACEMENTS:
        if old in content:
            content = content.replace(old, new)
            count += 1
            if dry_run:
                print(f"  [PATH] '{old}' → '{new}'")
    return content, count


def sanitize_client_keywords(content: str, dry_run: bool = False) -> tuple[str, int]:
    """Generaliza keywords que podem ser nomes de clientes."""
    count = 0
    for client, generic in CLIENT_KEYWORDS.items():
        # Substitui nas chaves do dicionário DOMAIN_KEYWORDS
        pattern = rf'"{client}"'
        if re.search(pattern, content):
            content = re.sub(pattern, f'"{generic}"', content)
            count += 1
            if dry_run:
                print(f"  [CLIENT] '{client}' → '{generic}'")
    return content, count


def sanitize_file(filepath: Path, dry_run: bool = False, sanitize_clients: bool = True) -> dict:
    """Sanitiza um arquivo individual."""
    result = {"path": str(filepath), "path_changes": 0, "client_changes": 0, "error": None}
    
    try:
        content = filepath.read_text(encoding="utf-8")
        original = content
        
        # Aplica substituições de path
        content, path_count = sanitize_paths(content, dry_run)
        result["path_changes"] = path_count
        
        # Aplica substituições de clientes (opcional)
        if sanitize_clients:
            content, client_count = sanitize_client_keywords(content, dry_run)
            result["client_changes"] = client_count
        
        # Só escreve se houve mudanças
        if content != original and not dry_run:
            filepath.write_text(content, encoding="utf-8")
            print(f"✓ {filepath.name} ({path_count} paths, {client_count} clients)")
        elif dry_run and (path_count > 0 or client_count > 0):
            print(f"→ {filepath.name} ({path_count} paths, {client_count} clients)")
            
    except Exception as e:
        result["error"] = str(e)
        print(f"✗ {filepath.name}: {e}")
    
    return result


def rename_plists(dry_run: bool = False) -> list:
    """Renomeia arquivos .plist removendo nome do usuário."""
    renamed = []
    
    for old_name, new_name in PLIST_RENAMES.items():
        old_path = PROJECT_ROOT / old_name
        new_path = PROJECT_ROOT / new_name
        
        if old_path.exists():
            if dry_run:
                print(f"  [RENAME] {old_name} → {new_name}")
                renamed.append({"old": old_name, "new": new_name})
            else:
                # Atualiza também o conteúdo do plist (Label)
                content = old_path.read_text(encoding="utf-8")
                content = content.replace("com.franciel", "com.vaultai")
                content = content.replace("franciel", "vaultai")
                
                old_path.rename(new_path)
                new_path.write_text(content, encoding="utf-8")
                print(f"✓ {old_name} → {new_name}")
                renamed.append({"old": old_name, "new": new_name})
    
    return renamed


def create_gitignore(dry_run: bool = False) -> bool:
    """Cria arquivo .gitignore apropriado."""
    content = """# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual environments
venv/
env/
ENV/
.venv/

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# macOS
.DS_Store
.AppleDouble
.LSOverride
._*

# Logs
*.log
logs/

# State files (contêm dados locais do usuário)
~/.vault/
*.state.json
*.checkpoint.json
*.dirty.json
notes_ids.json

# Arquivos de configuração com dados pessoais
config.py
*.local.py

# Arquivos compactados (podem conter dados sensíveis)
*.zip
*.tar.gz
*.rar

# Certificados e chaves
*.pem
*.key
*.crt
*.p12

# Ambiente
.env
.env.local
.env.*.local
"""
    
    gitignore_path = PROJECT_ROOT / ".gitignore"
    
    if dry_run:
        print(f"  [CREATE] .gitignore ({len(content)} bytes)")
        return True
    
    if not gitignore_path.exists():
        gitignore_path.write_text(content, encoding="utf-8")
        print(f"✓ .gitignore criado")
        return True
    else:
        print(f"→ .gitignore já existe (não sobrescrito)")
        return False


def create_config_example(dry_run: bool = False) -> bool:
    """Cria template de configuração genérico."""
    content = '''#!/usr/bin/env python3
"""
config.example.py
Template de configuração para o VaultAI.

Copie para config.py e ajuste os valores:
    cp config.example.py config.py
"""

import os

# ─── Paths ───────────────────────────────────────────────────────────────────
# Caminho para o vault Obsidian
VAULT_PATH = os.getenv("VAULT_PATH", os.path.expanduser("~/VaultAI"))

# Diretório onde os scripts serão instalados
SCRIPTS_DIR = os.getenv("SCRIPTS_DIR", "/usr/local/bin")

# ─── Timezone ────────────────────────────────────────────────────────────────
TIMEZONE = "America/Sao_Paulo"

# ─── Pastas que devem ser "achatadas" (sem subpastas no vault)
FLAT_FOLDERS = {"notes", "notas", "todas (icloud)", "all icloud", "icloud"}

# ─── Domínios para organização automática ────────────────────────────────────
# Edite conforme necessário para seu caso de uso
DOMAIN_KEYWORDS = {
    "tech": ["python", "java", "javascript", "docker", "kubernetes"],
    "cloud": ["aws", "azure", "gcp", "lambda", "s3"],
    "ai": ["llm", "machine learning", "transformer", "embedding"],
    "devops": ["ci/cd", "pipeline", "deploy", "terraform"],
    # Adicione seus próprios domínios aqui
}
'''
    
    config_path = PROJECT_ROOT / "config.example.py"
    
    if dry_run:
        print(f"  [CREATE] config.example.py ({len(content)} bytes)")
        return True
    
    if not config_path.exists():
        config_path.write_text(content, encoding="utf-8")
        print(f"✓ config.example.py criado")
        return True
    else:
        print(f"→ config.example.py já existe (não sobrescrito)")
        return False


def create_readme_section(dry_run: bool = False) -> bool:
    """Cria seção de configuração para o README."""
    content = """## Configuração

1. **Copie o template de configuração:**
   ```bash
   cp config.example.py config.py
   ```

2. **Edite `config.py` com seus paths:**
   ```python
   VAULT_PATH = "~/SeuVault"
   SCRIPTS_DIR = "/usr/local/bin"
   ```

3. **Instale os scripts:**
   ```bash
   sudo cp pipeline.py notes_to_obsidian.py organize_vault.py vault_menubar.py $SCRIPTS_DIR/
   sudo chmod +x $SCRIPTS_DIR/*.py
   ```

4. **Instale a dependência da menu bar:**
   ```bash
   pip install rumps
   ```

5. **Configure os launch agents (macOS):**
   ```bash
   cp com.vaultai.pipeline.plist ~/Library/LaunchAgents/
   cp com.vaultai.menubar.plist ~/Library/LaunchAgents/
   launchctl load ~/Library/LaunchAgents/com.vaultai.pipeline.plist
   launchctl load ~/Library/LaunchAgents/com.vaultai.menubar.plist
   ```
"""
    
    readme_section_path = PROJECT_ROOT / "README_SETUP.md"
    
    if dry_run:
        print(f"  [CREATE] README_SETUP.md ({len(content)} bytes)")
        return True
    
    readme_section_path.write_text(content, encoding="utf-8")
    print(f"✓ README_SETUP.md criado")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Sanitiza projeto VaultAI para publicação no GitHub"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Apenas mostra o que será feito, sem modificar arquivos"
    )
    parser.add_argument(
        "--keep-clients",
        action="store_true",
        help="Mantém keywords de clientes (não generaliza)"
    )
    parser.add_argument(
        "--skip-plist",
        action="store_true",
        help="Não renomeia arquivos .plist"
    )
    args = parser.parse_args()
    
    print("=" * 60)
    print("VaultAI - Sanitização para GitHub")
    print("=" * 60)
    print(f"\nModo: {'DRY RUN (apenas visualização)' if args.dry_run else 'EXECUÇÃO REAL'}")
    print(f"Generalizar clientes: {'NÃO' if args.keep_clients else 'SIM'}")
    print()
    
    results = []
    
    # 1. Sanitiza arquivos Python
    print("1. Sanitizando arquivos Python...")
    for filename in FILES_TO_SANITIZE:
        filepath = PROJECT_ROOT / filename
        if filepath.exists():
            result = sanitize_file(
                filepath,
                dry_run=args.dry_run,
                sanitize_clients=not args.keep_clients
            )
            results.append(result)
        else:
            print(f"  ⊘ {filename} não encontrado")
    print()
    
    # 2. Renomeia plists
    if not args.skip_plist:
        print("2. Renomeando arquivos .plist...")
        renamed = rename_plists(dry_run=args.dry_run)
        if not renamed:
            print("  ⊘ Nenhum arquivo .plist encontrado para renomear")
        print()
    
    # 3. Cria .gitignore
    print("3. Criando .gitignore...")
    create_gitignore(dry_run=args.dry_run)
    print()
    
    # 4. Cria config.example.py
    print("4. Criando config.example.py...")
    create_config_example(dry_run=args.dry_run)
    print()
    
    # 5. Cria README de setup
    print("5. Criando README_SETUP.md...")
    create_readme_section(dry_run=args.dry_run)
    print()
    
    # Resumo
    print("=" * 60)
    print("RESUMO")
    print("=" * 60)
    
    total_paths = sum(r["path_changes"] for r in results)
    total_clients = sum(r["client_changes"] for r in results)
    
    if args.dry_run:
        print(f"\nAlterações que seriam feitas:")
        print(f"  • {total_paths} substituições de path")
        print(f"  • {total_clients} substituições de keywords de clientes")
        print(f"  • {len(PLIST_RENAMES)} renomeações de .plist")
        print(f"  • 3 arquivos novos (.gitignore, config.example.py, README_SETUP.md)")
        print(f"\nExecute sem --dry-run para aplicar as alterações.")
    else:
        print(f"\nAlterações aplicadas:")
        print(f"  • {total_paths} substituições de path")
        print(f"  • {total_clients} substituições de keywords de clientes")
        print(f"  • {len(PLIST_RENAMES)} renomeações de .plist")
        print(f"  • 3 arquivos novos (.gitignore, config.example.py, README_SETUP.md)")
        print(f"\n✓ Projeto pronto para publicar no GitHub!")
        print(f"\n⚠️  Antes de publicar, verifique manualmente:")
        print(f"   • files.zip (remova se contiver dados sensíveis)")
        print(f"   • Debug scripts (debug_repeated.py, diagnose_batch.py) - considere remover")
        print(f"   • Logs em ~/.vault/ (não devem estar no repo)")


if __name__ == "__main__":
    main()
