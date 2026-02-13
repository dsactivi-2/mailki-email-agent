# Slack App / Bot Setup

## Voraussetzung
- Admin-Zugriff auf den Slack-Workspace

## Schritt-fuer-Schritt

### 1. Slack App erstellen
1. Gehe zu https://api.slack.com/apps
2. "Create New App" -> "From scratch"
3. App Name: `Mailki Email Agent`
4. Workspace: deinen Workspace auswaehlen
5. "Create App"

### 2. Bot Token Scopes setzen
1. Links: "OAuth & Permissions"
2. Unter "Scopes" -> "Bot Token Scopes" hinzufuegen:
   - `chat:write` (Nachrichten senden)
   - `chat:write.public` (in Public Channels ohne Einladung)
   - `channels:read` (Channel-Liste lesen)
   - `reactions:read` (Reaktionen lesen fuer Approval)
   - `users:read` (User-Info fuer Zuordnung)
   - `users:read.email` (E-Mail-Adressen fuer Zuordnung)

### 3. Interaktivitaet aktivieren
1. Links: "Interactivity & Shortcuts"
2. "Interactivity" einschalten
3. Request URL (spaeter eintragen):
   - Dev: `https://dev.mailki.activi.io/api/slack/interactions`
   - Prod: `https://mailki.activi.io/api/slack/interactions`
   (Erstmal leer lassen wenn Server noch nicht laeuft)

### 4. App installieren
1. Links: "Install App"
2. "Install to Workspace" klicken
3. Berechtigungen bestaetigen
4. **Bot User OAuth Token** kopieren -> in `.env`:
   ```
   SLACK_BOT_TOKEN=xoxb-...
   ```

### 5. Signing Secret holen
1. Links: "Basic Information"
2. Unter "App Credentials": **Signing Secret** kopieren -> in `.env`:
   ```
   SLACK_SIGNING_SECRET=<dein-signing-secret>
   ```

### 6. Approval-Channel erstellen
1. In Slack: neuen Channel erstellen
2. Name: `#mailki-approvals`
3. Beschreibung: "E-Mail-Drafts zur Freigabe"
4. Den Bot zum Channel einladen: `/invite @Mailki Email Agent`

### 7. Event Subscriptions (spaeter)
Wird aktiviert wenn der Server laeuft:
1. Links: "Event Subscriptions"
2. "Enable Events" einschalten
3. Request URL: `https://mailki.activi.io/api/slack/events`
4. Subscribe to bot events:
   - `message.channels` (Nachrichten in Channels)
   - `reaction_added` (fuer Approve/Reject per Emoji)

## Ergebnis
- `.env` hat `SLACK_BOT_TOKEN` und `SLACK_SIGNING_SECRET`
- Bot ist im Workspace installiert
- `#mailki-approvals` Channel existiert
- Interaktivitaet ist vorbereitet (URL wird spaeter gesetzt)
