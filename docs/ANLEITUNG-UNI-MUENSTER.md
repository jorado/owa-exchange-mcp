# Uni-Postfach für KI-Agenten (OpenCode, OpenWork, Codex …)

Mit dem **Exchange-MCP** greift ein KI-Agent auf dein Uni-Postfach zu (Mail, Kalender, Ordner, Aufgaben).
Es werden keine Passwörter gespeichert: Du meldest dich selbst im Browser an.
Die Anleitung funktioniert unter macOS, Linux und Windows.

## 1. KI-Tool installieren (falls noch nicht vorhanden)

Jedes Tool, das lokale MCP-Server unterstützt, funktioniert. Zum Beispiel:

| | macOS ([Homebrew](https://brew.sh)) | Linux / Windows |
|---|---|---|
| **OpenWork** (Vorschlag: Desktop-App, bringt OpenCode mit) | `brew install --cask openwork` | Download unter https://github.com/different-ai/openwork/releases |
| **OpenCode** (Terminal) | `brew install anomalyco/tap/opencode` | `npm install -g opencode-ai` |
| **Codex** | `brew install --cask codex` | `npm install -g @openai/codex` |

Für `npm` brauchst du [Node.js](https://nodejs.org).

## 2. uniGPT-API-Key holen (bei Bedarf, für OpenCode/OpenWork)

Mit uniGPT nutzt der Agent nur die internen Modelle der Uni, deine Mails verlassen die Uni also nicht.

1. Als Beschäftigte*r erzeugst du dir selbst einen Key (`sk-…`) im Self-Service-Portal: **https://gpt-api.uni-muenster.de**
   Für alle freigeschaltet sind `DeepSeek-V4-Flash` und `Qwen3.8-27B`. Weitere Modelle gibt es auf Anfrage beim uniGPT-Support (Mattermost).
   Details: https://gpt.uni-muenster.de/docs/api-usage/
2. Hinterlegt wird der Key **nicht** in der Config, sondern über OpenCode: `opencode` starten, `/connect` eingeben, dann **Other** wählen, `unigpt` als Provider-ID eingeben und den Key einfügen.
   Hast du nur OpenWork, nutzt du unter macOS dessen mitgeliefertes OpenCode:
   `/Applications/OpenWork.app/Contents/Resources/sidecars/opencode auth login`
   Unter Linux und Windows installierst du dafür OpenCode wie in Schritt 1.

## 3. Exchange-MCP installieren und einbinden

Voraussetzung: [Python](https://www.python.org/downloads/) 3.10 oder neuer und [Git](https://git-scm.com/downloads).

**macOS / Linux:**

```bash
git clone https://github.com/jorado/owa-exchange-mcp.git ~/owa-exchange-mcp
cd ~/owa-exchange-mcp
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/playwright install chromium   # Linux: ggf. "install --with-deps chromium" (fragt nach sudo)
```

**Windows (PowerShell):**

```powershell
git clone https://github.com/jorado/owa-exchange-mcp.git "$env:USERPROFILE\owa-exchange-mcp"
cd "$env:USERPROFILE\owa-exchange-mcp"
py -m venv .venv
.venv\Scripts\pip install -e .
.venv\Scripts\playwright install chromium
```

**OpenCode / OpenWork:** Die Config liegt in `~/.config/opencode/opencode.json`. OpenWork nutzt zusätzlich eine `opencode.jsonc` in seinem Arbeitsordner (z. B. `C:\Users\NAME\OpenWork Chat\opencode.jsonc`); welche Datei gilt, zeigt OpenWork bei einem Config-Fehler an. Hast du schon eine Config, ergänzt du nur die fehlenden Blöcke. Ohne uniGPT lässt du `model` und `provider` weg.

Beispiel für macOS / Linux:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "model": "unigpt/DeepSeek-V4-Flash",
  "provider": {
    "unigpt": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "uniGPT",
      "options": { "baseURL": "https://gpt.uni-muenster.de/v1" },
      "models": {
        "DeepSeek-V4-Flash": { "name": "uniGPT DeepSeek V4 Flash", "limit": { "context": 128000, "output": 8000 } },
        "Qwen3.8-27B": { "name": "uniGPT Qwen3.8 27B", "limit": { "context": 128000, "output": 8000 } }
      }
    }
  },
  "mcp": {
    "exchange-owa": {
      "type": "local",
      "command": ["{env:HOME}/owa-exchange-mcp/.venv/bin/exchange-mcp-server"],
      "environment": { "EXCHANGE_OWA_URL": "https://owa.uni-muenster.de" },
      "enabled": true
    }
  }
}
```

`{env:HOME}` ersetzt OpenCode automatisch durch dein Home-Verzeichnis. (`~` funktioniert hier nicht.)

> **⚠️ Windows: andere `command`-Zeile!** Unter Windows funktioniert `{env:HOME}` nicht, und `{env:USERPROFILE}` auch nicht: Es setzt Backslashes ein, die das JSON ungültig machen (Fehler `InvalidEscapeCharacter`). Schreib den Pfad stattdessen **aus**, mit `/` statt `\`, mit `Scripts` statt `bin` und mit `.exe`:
>
> ```json
> "command": ["C:/Users/NAME/owa-exchange-mcp/.venv/Scripts/exchange-mcp-server.exe"],
> ```
>
> Deinen Pfad zeigt `echo $env:USERPROFILE` in PowerShell; darin ersetzt du `\` durch `/`.

**Codex:**

```bash
# macOS / Linux
codex mcp add exchange-owa --env EXCHANGE_OWA_URL=https://owa.uni-muenster.de -- ~/owa-exchange-mcp/.venv/bin/exchange-mcp-server
```

```powershell
# Windows (PowerShell)
codex mcp add exchange-owa --env EXCHANGE_OWA_URL=https://owa.uni-muenster.de -- "$env:USERPROFILE\owa-exchange-mcp\.venv\Scripts\exchange-mcp-server.exe"
```

**Claude Code:**

```bash
# macOS / Linux
claude mcp add exchange-owa -s user -e EXCHANGE_OWA_URL=https://owa.uni-muenster.de -- ~/owa-exchange-mcp/.venv/bin/exchange-mcp-server
```

```powershell
# Windows (PowerShell)
claude mcp add exchange-owa -s user -e EXCHANGE_OWA_URL=https://owa.uni-muenster.de -- "$env:USERPROFILE\owa-exchange-mcp\.venv\Scripts\exchange-mcp-server.exe"
```

**Andere Tools:** Als Befehl gibst du den absoluten Pfad zum Server an:
- macOS / Linux: `echo ~/owa-exchange-mcp/.venv/bin/exchange-mcp-server` zeigt ihn.
- Windows: `echo "$env:USERPROFILE\owa-exchange-mcp\.venv\Scripts\exchange-mcp-server.exe"` zeigt ihn.

Als Umgebungsvariable setzt du `EXCHANGE_OWA_URL=https://owa.uni-muenster.de`.

**Werkzeuge:** Standardmäßig kann der Agent nur lesen und Entwürfe schreiben: Mail und Kalender lesen, Personen suchen, Entwürfe anlegen. Senden, Löschen oder Termine annehmen kann er nicht; abschicken musst du selbst in OWA. Brauchst du alle 65 Werkzeuge, setzt du zusätzlich die Umgebungsvariable `EXCHANGE_MCP_TOOLS=all`.

Danach startest du das Tool neu.

## 4. Beim Postfach anmelden

1. Beim Start öffnet sich ein Chromium-Fenster mit der Anmeldeseite von `owa.uni-muenster.de`.
2. Melde dich dort mit deinen Uni-Zugangsdaten an. Das Fenster wartet 5 Minuten.
3. Danach bleibt das Fenster offen. **Minimieren, nicht schließen**, sonst bist du abgemeldet.

Hast du die 5 Minuten verpasst, schreibst du dem Agenten: *„Melde dich bei Exchange an“*.
Nach jedem Neustart musst du dich erneut anmelden.

**Test:** *„Zeige meine ungelesenen Mails von heute.“*

## Hinweise

- **Ein Tool gleichzeitig:** Alle Tools teilen sich denselben Login. Beende den Server im einen Tool, bevor du ein anderes nutzt.
- **Anmeldedaten:** Dein Login liegt im Ordner `.browser-profile` im Installationsordner (z. B. `~/owa-exchange-mcp/.browser-profile`). Den Ordner nicht teilen und nicht in Cloud-Ordner synchronisieren.
- **Schreibrechte:** Mit `EXCHANGE_MCP_TOOLS=all` kann der Agent auch Mails senden, löschen und Termine annehmen. Bei solchen Aktionen genau hinschauen.
- **Linux:** Für das Anmeldefenster brauchst du eine grafische Oberfläche (kein reiner Server).
- **Nicht verfügbar:** Copilot-Funktionen gibt es nur bei Exchange Online, nicht an der Uni Münster.
- **Fehler `team not allowed to access model`:** Das Modell ist für deinen uniGPT-Key nicht freigeschaltet.
- **Update:** Im Installationsordner `git pull` ausführen, dann das Tool neu starten.
