# Wan2.1

A pinokio script for https://github.com/deepbeepmeep/Wan2GP

## Hilfstool: Prompt -> PowerRechner als `.xls` (Purple Cow Edition)

Datei: `tools/power_rechner_xls.py`

### Was ist neu?

- Unterstützt klassische Formeln (`x = ...`) **und** natürlichere Prompts.
- Rechnet Abhängigkeiten automatisch aus (Prompt-Reihenfolge ist egal).
- Nutzt ein sicheres, eingeschränktes Eval-Modell.
- Exportiert ein visuell formatiertes `.xls` mit drei Blättern:
  - `PowerRechner`
  - `KPI`
  - `Prompt`

### Beispiel 1 (klassisch)

```bash
python3 tools/power_rechner_xls.py \
  --prompt "preis=120; steuer=0.19; brutto=preis*(1+steuer); rabatt=15; endpreis=brutto-rabatt" \
  --out power_rechner.xls
```

### Beispiel 2 (natürlich)

```bash
python3 tools/power_rechner_xls.py \
  --prompt "setze preis auf 240; mwst ist 0.19; berechne brutto als preis * (1 + mwst); berechne monat als brutto geteilt durch 12" \
  --out power_prompt.xls
```

### Unterstützte Syntax

- `variable = ausdruck`
- `setze variable auf wert`
- `variable ist wert`
- `berechne variable als ausdruck`

Unterstützte Operatoren/Funktionen:

- `+ - * / // % **`
- `min(...)`, `max(...)`, `round(...)`, `abs(...)`
