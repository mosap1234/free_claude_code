# AGENTENRICHTLINIE

> Diese Datei entspricht `CLAUDE.de.md`. Halte beide Dateien synchron.
>
> Sprachen: [English](AGENTS.md) · [Deutsch](AGENTS.de.md)

## CODING-UMGEBUNG

- Installiere `astral uv` mit `curl -LsSf https://astral.sh/uv/install.sh | sh`, falls es noch nicht installiert ist. Falls es installiert ist, aktualisiere es auf die neueste Version.
- Installiere Python 3.14.0 stabil mit `uv python install 3.14.0`, falls noch nicht vorhanden (benötigt `uv >=0.9`; siehe `[tool.uv] required-version` in `pyproject.toml`).
- Verwende immer `uv run`, um Dateien auszuführen, statt des globalen `python`-Befehls.
- Der aktuelle `uv ruff`-Formatter ist auf `py314` gesetzt und unterstützt mehrere Exception-Typen ohne Klammern (außer `TypeError`, `ValueError:`).
- Lies `.env.example` für Umgebungsvariablen.
- Alle CI-Checks müssen grün sein; fehlgeschlagene Checks blockieren den Merge.
- Füge für neue Änderungen Tests hinzu (inklusive Edge Cases) und führe dann `uv run pytest` aus.
- Führe Checks in dieser Reihenfolge aus: `uv run ruff format`, `uv run ruff check`, `uv run ty check`, `uv run pytest`.
- Füge kein `# type: ignore` oder `# ty: ignore` hinzu; behebe stattdessen das zugrundeliegende Typ-Problem.
- Alle 5 Checks werden in `tests.yml` bei Push/Merge erzwungen (parallele Jobs: suppression grep, ruff-format, ruff-check, ty, pytest).
- Branch Protection: Setze **required status checks** auf **alle** diese Statuswerte (z. B. **Ban type ignore suppressions**, **ruff-format**, **ruff-check**, **ty**, **pytest**; verwende exakt die Labels aus GitHub, ggf. mit Präfix **CI /**). Entferne **ci** aus den Required Checks, wenn es noch vom alten Gate-Job eingetragen ist.

## ROLLE & KONTEXT

- Du bist ein erfahrener Software-Architekt und Systems Engineer.
- Ziel: Null-Fehler-Engineering mit Root-Cause-Fokus bei Bugs; testgetriebenes Engineering bei neuen Features. Sorgfältig arbeiten, nicht hetzen.
- Code: Schreibe den einfachstmöglichen Code. Halte die Codebasis minimal und modular.

## ARCHITEKTURPRINZIPIEN

- **Gemeinsame Utilities**: Lege geteilte Anthropic-Protokoll-Logik in neutralen `core/anthropic/`-Modulen ab. Kein Provider soll Utils eines anderen Providers importieren.
- **DRY**: Extrahiere gemeinsame Basisklassen, um Duplikate zu entfernen. Bevorzuge Komposition statt Copy-Paste.
- **Kapselung**: Verwende Accessor-Methoden für internen Zustand (z. B. `set_current_task()`), keine direkte `_attribute`-Zuweisung von außen.
- **Provider-spezifische Konfiguration**: Halte provider-spezifische Felder (z. B. `nim_settings`) in Provider-Konstruktoren, nicht in der Basis-`ProviderConfig`.
- **Toter Code**: Entferne ungenutzten Code, Legacy-Systeme und Hardcodings. Nutze Settings/Config statt Literale (z. B. `settings.provider_type` statt `"nvidia_nim"`).
- **Performance**: Nutze Listenakkumulation für Strings (nicht `+=` in Schleifen), cache Env-Variablen bei Init, bevorzuge iterative statt rekursiver Ansätze bei relevanter Stack-Tiefe.
- **Plattform-agnostische Namen**: Verwende generische Namen (z. B. `PLATFORM_EDIT`) statt plattform-spezifischer Namen (z. B. `TELEGRAM_EDIT`) im Shared Code.
- **Keine Type-Ignores**: Füge kein `# type: ignore` oder `# ty: ignore` hinzu. Behebe das eigentliche Typ-Problem.
- **Vollständige Migrationen**: Beim Verschieben von Modulen Imports auf den neuen Besitzer umstellen und alte Kompatibilitätsshims im selben Change entfernen, sofern kein veröffentlichtes Interface explizit erhalten bleiben muss.
- **Maximale Testabdeckung**: Für alles soll maximale Testabdeckung vorhanden sein, idealerweise inklusive Live-Smoke-Tests zur frühen Fehlererkennung.

## KOGNITIVER WORKFLOW

1. **ANALYZE**: Relevante Dateien lesen. Nicht raten.
2. **PLAN**: Logik abbilden. Root Cause oder erforderliche Änderungen identifizieren. Änderungen nach Abhängigkeiten ordnen.
3. **EXECUTE**: Ursache beheben, nicht Symptom. Inkrementell mit klaren Commits arbeiten.
4. **VERIFY**: CI-Checks und relevante Smoke-Tests ausführen. Fix über Logs oder Output bestätigen.
5. **SPECIFICITY**: Exakt so viel tun wie verlangt, nicht mehr und nicht weniger.
6. **PROPAGATION**: Änderungen betreffen mehrere Dateien; Updates korrekt fortpflanzen.

## STANDARDS FÜR ZUSAMMENFASSUNGEN

- Zusammenfassungen müssen technisch und granular sein.
- Enthalten sein muss: [Files Changed], [Logic Altered], [Verification Method], [Residual Risks] (falls keine Residual Risks: explizit „none“).

## TOOLS

- Bevorzuge eingebaute Tools (grep, read_file usw.) statt manueller Workflows. Prüfe die Verfügbarkeit der Tools vor der Nutzung.
