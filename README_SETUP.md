## Configuração

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
