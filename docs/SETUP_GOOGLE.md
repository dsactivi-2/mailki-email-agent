# Google Workspace / Gmail API Setup

## Voraussetzung
- Admin-Zugriff auf Google Cloud Console
- Google Workspace mit der Domain activi.io

## Schritt-fuer-Schritt

### 1. Google Cloud Projekt erstellen
1. Gehe zu https://console.cloud.google.com/
2. Oben links: Projekt-Auswahl -> "Neues Projekt"
3. Name: `mailki-email-agent`
4. Organisation: deine Workspace-Organisation
5. "Erstellen" klicken

### 2. Gmail API aktivieren
1. Im Projekt: "APIs & Dienste" -> "Bibliothek"
2. Suche: "Gmail API"
3. Klick auf "Gmail API" -> "Aktivieren"

### 3. OAuth-Zustimmungsbildschirm
1. "APIs & Dienste" -> "OAuth-Zustimmungsbildschirm"
2. Nutzertyp: "Intern" (nur fuer Workspace-User)
3. App-Name: `Mailki Email Agent`
4. Support-E-Mail: deine Admin-Adresse
5. Bereiche hinzufuegen:
   - `https://www.googleapis.com/auth/gmail.readonly`
   - `https://www.googleapis.com/auth/gmail.send`
   - `https://www.googleapis.com/auth/gmail.modify`
6. Speichern

### 4. OAuth-Client-ID erstellen
1. "APIs & Dienste" -> "Anmeldedaten"
2. "Anmeldedaten erstellen" -> "OAuth-Client-ID"
3. Anwendungstyp: "Webanwendung"
4. Name: `mailki-backend`
5. Autorisierte Weiterleitungs-URIs:
   - `http://localhost:8001/api/auth/google/callback` (Dev)
   - `https://mailki.activi.io/api/auth/google/callback` (Prod)
6. "Erstellen" klicken
7. **Client-ID und Client-Secret kopieren** -> in `.env` eintragen:
   ```
   GOOGLE_CLIENT_ID=<deine-client-id>
   GOOGLE_CLIENT_SECRET=<dein-client-secret>
   ```

### 5. Service Account (optional, fuer Server-to-Server)
Falls du ohne User-Interaktion auf Postfaecher zugreifen willst:
1. "Anmeldedaten" -> "Dienstkonto erstellen"
2. Name: `mailki-service`
3. JSON-Key herunterladen -> sicher ablegen (NICHT ins Repo!)
4. Im Google Admin: Domain-weite Delegierung aktivieren
   - Admin Console -> Sicherheit -> API-Steuerung -> Domain-weite Delegierung
   - Client-ID des Service Accounts eintragen
   - Bereiche: die Gmail-Bereiche von oben

## Ergebnis
- `.env` hat `GOOGLE_CLIENT_ID` und `GOOGLE_CLIENT_SECRET`
- Gmail API ist aktiviert
- OAuth-Flow ist bereit fuer die App
