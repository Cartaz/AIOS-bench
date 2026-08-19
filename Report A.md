# AIOS-bench — Hardening Report

**Logica delle modifiche test per test**

> Report tecnico per maintainer. Cataloga, per ciascuno dei 28 task in `benchmarks/tasks/frontier_v2.json`, le vulnerabilità attuali, la logica dell'indurimento proposto e le nuove specifiche di acceptance con snippet JSON pronti da innestare nel catalogo.

| | |
|---|---|
| Repo | `https://github.com/Cartaz/AIOS-bench` |
| Catalogo attivo | `benchmarks/tasks/frontier_v2.json` (28 task, tier 3–5) |
| Evaluator | `aios_bench/evaluators.py` |
| Fixtures | `benchmarks/fixtures/workspace/` |
| Scoring | `overall = 0.60·acceptance + 0.15·execution + 0.10·error_recovery + 0.10·human_independence + 0.05·proportionality` |
| Run registrata | `first_benchmark_results_for_evaluation_of_tests/` (piagent × Qwen, 23/26 "passati" ma con artefatti rotti invisibili allo scoring) |

---

## Indice

1. [Executive Summary](#1-executive-summary)
2. [Matrice impatto / sforzo](#2-matrice-impatto--sforzo)
3. [Vulnerabilità sistemiche](#3-vulnerabilità-sistemiche)
4. [Analisi test per test](#4-analisi-test-per-test)
   - 4.1 [`tool_use`](#41-tool_use)
   - 4.2 [`memory`](#42-memory)
   - 4.3 [`knowledge`](#43-knowledge)
   - 4.4 [`coding`](#44-coding)
   - 4.5 [`autonomy`](#45-autonomy)
   - 4.6 [`browser`](#46-browser)
   - 4.7 [`learning`](#47-learning)
   - 4.8 [`long_horizon`](#48-long_horizon)
   - 4.9 [`subagents`](#49-subagents)
5. [Estensioni dell'evaluator](#5-estensioni-dellevaluator)
6. [Roadmap implementativa in 3 fasi](#6-roadmap-implementativa-in-3-fasi)
7. [Riferimenti cross-benchmark](#7-riferimenti-cross-benchmark)
8. [Appendice: catalogo completo delle modifiche](#8-appendice-catalogo-completo-delle-modifiche)

---

## 1. Executive Summary

AIOS-bench ha un'infrastruttura solida (workspace isolato copiato dal seed, runner con resumability via `task_revision`, 6 adapter, telemetry, dashboard) ma uno **strato di contenuto molto sottile**. Le 9 dimensioni nominali (tool_use, memory, knowledge, coding, autonomy, browser, learning, long_horizon, subagents) sono dichiarate nel README ma misurate in modo quasi esclusivamente strutturale: il 60% del punteggio finale poggia su `acceptance`, e `acceptance` è dominato da check `contains "<keyword>"` case-insensitive su testo libero.

### Le 5 vulnerabilità sistemiche

1. **Match a sottostringa su testo libero.** `evaluators.file_contains` usa `text.lower() in content.lower()`. Le parole "Source", "Priority", "Evidence", "Verified", "Rejected", "Requirement", "Validation", "Conflict" — anche in un disclaimer boilerplate — soddisfano i check. Crea un equilibrio perverso in cui un file "corretto-ma-terse" punteggia meno di un file "sbagliato-ma-keyword-stuffed".
2. **Zero verifica numerica o fattuale.** Nessun task confronta l'output dell'agente con un valore atteso precomputato. L'unico gate "reale" è `python -m pytest -q` sui task di coding — ma l'agente scrive sia il codice che i test, quindi può produrre test trivialmente passanti.
3. **Tutto single-turn, single-prompt.** Long_horizon e memory sono *definiti* come multi-step ma *valutati* solo sull'artefatto finale. Una run da 30 secondi e una da 30 minuti sono identiche se producono gli stessi file.
4. **Fixture minuscola e uniforme.** Tutto il seed è ~2 KB: 6 righe CSV × 2 file, 10 righe di meeting notes, 5 righe di procedure. Il claim "98k context ceiling" del README non viene mai esercitato. C'è un solo difetto in tutta la suite (`broken_tool.py` con `TypeError` su `monthly_total([10, 20, "30"])`), riusato in 5 task diversi.
5. **Tutto in inglese, common-knowledge, low-domain-expertise.** Python, sqlite, CSV: gli LLM hanno già visto tutto nel pretraining. Nessun task richiede grounding in contesto sintetico, contraddittorio, o out-of-distribution che sconfigga i prior del modello.

### Top 5 modifiche prioritarie

| # | Cambiamento | Dove | Impatto |
|---|---|---|---|
| 1 | Aggiungere check `regex`/`numeric_close`/`not_contains` con valori attesi precomputati a `autonomy_001`, `browser_001`, `knowledge_001` | `frontier_v2.json` + `evaluators.py` (~30 LOC) | Converte i 3 task più gameable in test reali |
| 2 | Inviare test nascosti nel fixture per `coding_001`/`coding_004` invece di farli scrivere all'agente | `benchmarks/fixtures/workspace/tests/test_hidden.py` | Rimuove il loophole "agente scrive sia codice che test" |
| 3 | Aggiungere `command:` che esegue realmente il tool prodotto dall'agente su `autonomy_001` e `memory_002` | `frontier_v2.json` | Cattura il fallimento già osservato: script con typo (`monthlyonth_key]`) che passa lo stesso |
| 4 | Piantare un difetto reale in `learning_003` e una contraddizione reale in `knowledge_003` | `benchmarks/fixtures/workspace/skills/` e `procedures/` | Rende falsificabili due task che attualmente chiedono di trovare errori inesistenti |
| 5 | Generatore di corpus sintetico ~50k token per `long_horizon_*` | `benchmarks/fixtures/gen_corpus.py` | Esercita davvero il 98k ceiling, oggi non testato |

### Sintesi del giudizio

La suite passa oggi se "sembra giusta", non se "è giusta". Le modifiche in questo report convertono la seconda condizione nella prima — distinguendo agenti capaci da script di keyword-stuffing. L'effetto sulle metriche registrate: una stima realistica è che il pass-rate di piagent × Qwen passerebbe dall'88% attuale a un range 35–55%, che è esattamente il range in cui un benchmark deve operare per discriminare.

---

## 2. Matrice impatto / sforzo

Legenda: **Impatto** = quanto la modifica alza la difficoltà per un LLM (Alto/Molto alto/Critico). **Sforzo** = lavoro di implementazione (Basso/Medio/Alto). **Quick-win** = Alto impatto + Basso sforzo.

| # | Task | Vulnerabilità principale | Modifica proposta | Nuovo check type | Impatto | Sforzo |
|---|------|--------------------------|-------------------|------------------|---------|--------|
| 1 | `tool_use_001` | Classificazione non verificata | JSON con `evidence_hash` | `regex` + `sha256` | Alto | Basso |
| 2 | `tool_use_002` | "Effective" come substring | `regex` su valore effettivo + trap multi-README | `regex_strict` | Alto | Basso |
| 3 | `tool_use_003` | Singolo difetto ovvio | Secondo test ambiguo + `unchanged` file | `unchanged` (sha256) | Alto | Medio |
| 4 | `memory_001` | No proof di retrieval | Secret token in fixture | `regex` su token | Molto alto | Basso |
| 5 | `memory_002` | Tool non eseguito | `command:` che esegue il tool | `command` | Alto | Basso |
| 6 | `memory_003` | Singola regola applicata | Preferenza contraddittoria mid-stream | `regex` multi-campo | Molto alto | Medio |
| 7 | `memory_004` | "No commit" non verificato | `.git/` piantato + `unchanged .git/HEAD` | `unchanged` | Alto | Basso |
| 8 | `knowledge_001` | Provenance fabbricabile | JSON con `evidence_quote` verificata | `regex` + `not_contains` | Molto alto | Medio |
| 9 | `knowledge_002` | Diff banale | 3 file con contraddizioni reali | `regex` su delta | Alto | Basso |
| 10 | `knowledge_003` | Contraddizione superficiale | 3 fonti con autorità gerarchica | `regex_strict` | Molto alto | Medio |
| 11 | `coding_001` | Agente scrive test | Test nascosti + anti-hardcoding | `command` multi | Critico | Medio |
| 12 | `coding_002` | Stesso broken_tool | Difetto diverso (off-by-one) | `command` + `unchanged` | Alto | Medio |
| 13 | `coding_003` | Refactor non verificato | `command` su CLI edges | `command` | Alto | Basso |
| 14 | `coding_004` | No negative path | Exit code su input invalido | `command` (shell) | Alto | Basso |
| 15 | `autonomy_001` | Tool rotto passa | `command:` esegue il tool + `regex` su totale | `command` + `regex` | Critico | Basso |
| 16 | `autonomy_002` | JSON inventabile | Count esatto + owner `regex` | `regex` + `json_valid` | Alto | Basso |
| 17 | `autonomy_003` | broken_tool riusato | Secondo difetto indipendente | `command` multi | Alto | Medio |
| 18 | `browser_001` | URL fabbricabili | Whitelist domini + ground truth fattuale | `regex` + `not_contains` | Critico | Medio |
| 19 | `browser_002` | `min_lines: 25` come unico gate | Requisiti su sezioni del memo | `regex` multi | Alto | Basso |
| 20 | `learning_001` | No verifica procedura | Esecuzione in sandbox pulita | `command` | Alto | Medio |
| 21 | `learning_002` | Transfer non testato | CSV schema-shifted | `regex` su colonne | Alto | Medio |
| 22 | `learning_003` | Errore non iniettato | Procedura piantata con bug reale | `regex_strict` | Critico | Basso |
| 23 | `long_horizon_001` | 98k ceiling non esercitato | Corpus 50k token + error injection | `regex` + `command` | Molto alto | Alto |
| 24 | `long_horizon_002` | Artifact indipendenti | Catena di dipendenze #1→#2→#3 | `command` multi | Alto | Medio |
| 25 | `long_horizon_003` | Audit non verificato | Checkpoint di stato + `command` | `regex` multi | Alto | Medio |
| 26 | `subagents_001` | No proof di delega | Telemetria obbligatoria | `regex` su events | Alto | Basso |
| 27 | `subagents_002` | No conflitto piantato | Sub-stream contraddittori | `regex` multi | Alto | Medio |
| 28 | `subagents_003` | No "reject" verificato | Sub-task con output da rifiutare | `not_contains` | Alto | Medio |

**Totali**: 28 task modificati · 4 nuovi check types da aggiungere a `evaluators.py` · 1 generatore di fixture aggiuntivo · 5 file di fixture modificati.

---

## 3. Vulnerabilità sistemiche

Prima di entrare nel dettaglio test-per-test, vale la pena fissare le 5 vulnerabilità che attraversano l'intera suite. Capire queste è prerequisito per capire perché ogni singola modifica ha senso: le proposte per-task non sono patch isolate ma istanze di un piano coerente che attacca le vulnerabilità sistemiche una alla volta.

### 3.1 Match a sottostringa su testo libero

L'evaluator `file_contains` in `aios_bench/evaluators.py` implementa il check `contains` come:

```python
def file_contains(path: Path, text: str) -> bool:
    content = path.read_text(encoding="utf-8").lower()
    return text.lower() in content
```

Il match è case-insensitive e su sottostringa. Nei 28 task del catalogo attivo, dei ~80 check di acceptance totali, la maggioranza è `contains "<keyword>"` con keyword generiche come "Source", "Priority", "Evidence", "Verified", "Rejected", "Requirement", "Validation", "Conflict", "Uncertainty", "Adapt", "Transfer". Un report che contiene queste parole in un disclaimer boilerplate (es. "All sources are confidential. The author takes no responsibility for any claims made herein.") passa i check senza aver svolto il task.

Questo è il difetto #1 della suite perché è sistemico: ogni categoria soffre dello stesso problema, e le patch per-task (sostituire `contains` con `regex_strict` su valori specifici) sono tutte istanze della stessa cura. **Senza questa patch, qualsiasi altra modifica ha efficacia limitata**: anche se piantiamo difetti reali, se l'acceptance verifica solo la presenza di keyword, l'agente può comunque passare stampando le keyword.

### 3.2 Zero verifica numerica o fattuale

A parte `python -m pytest -q` sui task di coding, nessun check confronta l'output dell'agente con un valore atteso precomputato. Il totale spese in `autonomy_001` può essere qualsiasi numero. Gli URL in `browser_001` possono puntare a domini inesistenti. Le azioni in `knowledge_001` possono essere inventate di sana pianta. Il JSON in `autonomy_002` può avere 5 o 50 voci — `min_lines: 8` è l'unico gate.

La conseguenza pratica è che il benchmark non misura *correttezza* ma *presenza di artefatti*. Due agenti che producono file con le keyword giuste passano allo stesso modo, anche se uno ha calcolato il totale giusto e l'altro ha scritto "Total Expenses: $0.00". Per un sistema di valutazione di agenti "AIOS" questo è un difetto esiziale: la differenza tra un agente utile e uno inutile sta esattamente nella correttezza, non nella presenza.

### 3.3 Tutto single-turn, single-prompt

Ogni task del catalogo è "una sola consegna, un solo artefatto finale". La dimensione `memory` dichiara di testare "cold → warm progression" ma la verifica sta solo nel file prodotto nella run warm: niente prova che l'agente abbia effettivamente recuperato memoria dalla run cold invece di re-derivare l'informazione dal prompt stesso (che spesso contiene già la risposta, come in `memory_003` dove si dice esplicitamente "preference changed from Python to TypeScript").

Analogamente `long_horizon` dichiara di testare "stato gestito su 98k token" ma il fixture è ~2 KB e non c'è alcuna iniezione di errore mid-task, alcun aggiornamento contraddittorio, alcuna richiesta di diff. La differenza tra un agente che gestisce stato in modo durevole e uno che ricalcola tutto in-context è invisibile allo scoring.

### 3.4 Fixture minuscola e uniforme

Il seed workspace è composto da:
- `data/expenses.csv` (6 righe, 3 colonne)
- `data/sales.csv` (6 righe, 4 colonne)
- `notes/meeting_notes.md` (10 righe)
- `procedures/current.md` (5 righe)
- `procedures/previous.md` (6 righe)
- `projects/broken_tool.py` (~30 righe, singola funzione con TypeError)
- `README.md` (pochi link)

Totale: ~2 KB. C'è un solo difetto in tutta la suite, ed è `broken_tool.py`, riusato in `tool_use_003`, `coding_002`, `coding_003`, `autonomy_003`, `learning_003`. Un agente che lo ha visto una volta ha un vantaggio sproporzionato sugli altri quattro task. Inoltre, l'assenza di corpus reale significa che la pressione sul context window è nulla: l'agente può `cat` l'intero workspace in un comando e aver finito.

### 3.5 Tutto in inglese, common-knowledge, low-domain-expertise

I task di ricerca (`browser_001` su Python 3.14 sqlite3, `browser_002` su tech decision memo) targettano argomenti ben rappresentati nel pretraining dei modelli moderni. I task di coding sono tutti in Python su CSV standard. I task di knowledge lavorano su procedure banali (5 righe). Nessun task richiede grounding in contesto sintetico fornito al volo, contesto contraddittorio, o dominio specialistico out-of-distribution.

Questo significa che il benchmark non misura la capacità dell'agente di *apprendere dal contesto fornito* ma solo di *ricordare dal pretraining*. Un test serio dovrebbe includere almeno un task con dati sintetici inventati (es. un dominio "Acelerax Inc." con procedure interne inventate) dove l'agente deve dimostrare di ragionare sul contesto, non di recuperare da memoria.

### Sintesi

Le 5 vulnerabilità si rafforzano a vicenda. La #1 (substring match) rende inutili le patch che aggiungono requisiti al prompt, perché l'agente può comunque rispondere con keyword. La #2 (no verifica) rende inutile qualsiasi iniezione di difetti, perché l'agente non deve risolverli per passare. La #3 (single-turn) rende la #4 (fixture piccola) ancora più grave, perché non c'è nemmeno accumulo di stato a compensare. La #5 (common knowledge) rende la #2 ancora più grave, perché l'agente può bypassare il context e recuperare dal pretraining.

Le proposte che seguono attaccano queste vulnerabilità in modo coordinato: per ogni task indichiamo come convertire i check `contains` in `regex_strict` o `numeric_close`, come piantare difetti reali che richiedono grounding, come rendere multi-turn dove serve, e come espandere il fixture per esercitare realmente la pressione dichiarata.

---

## 4. Analisi test per test

Per ciascun task la struttura è fissa a 5 blocchi:

1. **Stato attuale** — prompt sintetizzato, acceptance corrente, comportamento osservato nella run registrata.
2. **Debolezza** — la specifica falla sfruttabile da un LLM, con esempi concreti di come un agente può passare senza svolgere il task.
3. **Logica dell'indurimento** — il razionale della modifica, collegato a una o più vulnerabilità sistemiche della sezione 3.
4. **Acceptance prima / dopo** — snippet JSON del campo `acceptance` prima e dopo, pronti da innestare in `frontier_v2.json`. I nuovi check types (`regex_strict`, `numeric_close`, `not_contains`, `json_field_equals`) sono definiti nella sezione 5.
5. **Cosa cattura ora** — elenco esplicito dei pattern di gaming che la nuova acceptance blocca, e dei casi limite da considerare in fase di implementazione.

Ogni categoria si chiude con una tabella comparativa che riepiloga i 5 blocchi in formato sintetico.

### 4.1 `tool_use`

Categoria di 3 task che valuta la capacità dell'agente di operare su filesystem, seguire riferimenti indiretti e diagnosticare/fixare difetti in modo riproducibile. È la categoria più "classica" della suite e quella dove la differenza tra fixture minuscolo e fixture reale è più evidente.

#### `tool_use_001` — Classificazione file autorevoli/storici/decoy

##### 1. Stato attuale

Prompt: classifica i file del workspace come autorevoli / storici / decoy in base al contenuto (non al nome), salva `reports/file_classification.md`.

Acceptance corrente:

```json
"acceptance": [
  {"type": "exists", "path": "reports/file_classification.md", "weight": 2, "fatal": true},
  {"type": "contains", "path": "reports/file_classification.md", "text": "Authoritative", "weight": 1},
  {"type": "contains", "path": "reports/file_classification.md", "text": "Decoy", "weight": 1}
]
```

Tier dichiarato: T3. Run registrata: pass.

##### 2. Debolezza

L'acceptance verifica solo la *presenza delle parole* "Authoritative" e "Decoy" in qualsiasi file markdown. Non verifica che:
- la classificazione sia *corretta* (un agente che etichetta tutto come "Decoy" passa),
- l'agente abbia effettivamente *ispezionato* i file (può scrivere la classificazione a occhi chiusi),
- ci sia una qualunque struttura (prose, bullet, JSON — tutto uguale).

Inoltre il fixture non contiene alcun file "trappola": ogni file ha un nome che suggerisce già il ruolo (`data/expenses.csv` è autorevole, `archive/old_data.csv` è storico, `notes/draft.md` è decoy). Un agente che classificasse in base al nome passerebbe.

##### 3. Logica dell'indurimento

Tre modifiche coordinate:

1. **Output strutturato invece di testo libero.** Costringere l'agente a produrre `reports/file_classification.json` con uno schema fissato: `[{path, classification, evidence_hash, reason}]`. Questo trasforma il task da "scrivi una frase con le parole giuste" a "produci un artefatto macchinicamente verificabile".

2. **Verifica della inspection reale.** Il campo `evidence_hash` deve essere lo SHA-256 del file che l'agente dichiara di aver ispezionato. L'evaluator ricalcola l'hash dal file nel workspace e lo confronta. Se non corrisponde, la voce è invalidata. Questo è il cuore della modifica: non si può più classificare a occhi chiusi.

3. **File trappola.** Aggiungere al fixture un file `data/legacy_sales.csv` il cui nome suggerisce "storico" ma il cui contenuto (intestazione + righe corrette) lo rende autorevole. L'agente che classifica per nome lo marca storico e fallisce. Aggiungere anche `archive/sales_2023.csv` il cui nome suggerisce autorevole ma il cui contenuto contiene un commento `# DEPRECATED, see data/expenses.csv`.

Le tre modifiche insieme convertono il task da "scrivi due parole in un .md" a "ispeziona realmente ogni file, dimostralo con l'hash, e gestisci i casi in cui nome e contenuto mentono".

##### 4. Acceptance prima / dopo

**Prima** (snippet attuale): vedere sopra.

**Dopo**:

```json
"acceptance": [
  {"type": "exists", "path": "reports/file_classification.json", "weight": 2, "fatal": true},
  {"type": "json_valid", "path": "reports/file_classification.json", "weight": 1, "fatal": true},
  {"type": "json_field_equals", "path": "reports/file_classification.json",
   "jq_filter": "[.[] | select(.path == \"data/expenses.csv\").classification] | .[0]",
   "expected": "authoritative", "weight": 2, "fatal": true},
  {"type": "json_field_equals", "path": "reports/file_classification.json",
   "jq_filter": "[.[] | select(.path == \"data/legacy_sales.csv\").classification] | .[0]",
   "expected": "authoritative", "weight": 2, "fatal": true},
  {"type": "json_field_equals", "path": "reports/file_classification.json",
   "jq_filter": "[.[] | select(.path == \"archive/sales_2023.csv\").classification] | .[0]",
   "expected": "decoy", "weight": 2, "fatal": true},
  {"type": "sha256_match", "path": "reports/file_classification.json",
   "jq_filter": "[.[] | select(.path == \"data/expenses.csv\").evidence_hash] | .[0]",
   "expected_sha256_of": "data/expenses.csv", "weight": 2, "fatal": true},
  {"type": "sha256_match", "path": "reports/file_classification.json",
   "jq_filter": "[.[] | select(.path == \"archive/sales_2023.csv\").evidence_hash] | .[0]",
   "expected_sha256_of": "archive/sales_2023.csv", "weight": 2, "fatal": true},
  {"type": "min_count", "path": "reports/file_classification.json",
   "jq_filter": "length", "expected": 7, "weight": 1, "fatal": true}
]
```

Incrementare `task_revision` da 2 a 3 per invalidare run precedenti.

##### 5. Cosa cattura ora

- **Classificazione a occhi chiusi**: bloccata. Senza leggere il file l'agente non può calcolare l'SHA-256 giusto.
- **Classificazione per nome**: bloccata. `data/legacy_sales.csv` ha nome "legacy" ma è autorevole; `archive/sales_2023.csv` ha nome autorevole ma è decoy.
- **Etichettare tutto come decoy**: bloccato dal check `json_field_equals` su `data/expenses.csv = authoritative`.
- **Output boilerplate con keyword**: bloccato. L'acceptance è ora JSON-strutturata.
- **Casi limite da considerare**: l'evaluator deve gestire il caso in cui l'agente ometta un file dal JSON. Il check `min_count: 7` lo copre, ma serve anche un `not_contains` sui path dei file non inclusi per evitare che l'agente ometta i file " scomodi" (es. `archive/sales_2023.csv`).

---

#### `tool_use_002` — Config effettiva via README indiretto

##### 1. Stato attuale

Prompt: segui i riferimenti nel README per trovare la configurazione *effettiva* in uso, verifica contro il codice consumer, salva `reports/effective_config.md`.

Acceptance corrente:

```json
"acceptance": [
  {"type": "exists", "path": "reports/effective_config.md", "weight": 2, "fatal": true},
  {"type": "contains", "path": "reports/effective_config.md", "text": "effective", "weight": 1},
  {"type": "contains", "path": "reports/effective_config.md", "text": "verified", "weight": 1}
]
```

Tier dichiarato: T4. Run registrata: pass (anche se i risultati erano `evaluation=None`, graded su exit code).

##### 2. Debolezza

`contains "effective"` e `contains "verified"` sono soddisfatti da un report che dice "The effective config is verified." — frase unica, nessun dato. Il fixture attuale ha un solo `README.md` che punta direttamente al file di config: non c'è alcuna indirezione reale. Il "follow README references through indirection" è nominato nel prompt ma non testato.

Inoltre, l'agente non deve *dimostrare* di aver verificato contro il codice consumer: gli basta scrivere la parola "verified".

##### 3. Logica dell'indurimento

Tre modifiche coordinate:

1. **Multi-README indiretto.** Aggiungere al fixture tre README in posizioni diverse con valori di config *plausibili ma stanchi*:
   - `README.md` (root) → "see docs/README.md for current config"
   - `docs/README.md` → "port: 8080, env: staging"
   - `archive/README_2025.md` → "port: 8081, env: production"
   - `config/app.yaml` (file reale) → "port: 8081, env: production"

   Il codice consumer (`tools/run_server.py`) legge `config/app.yaml`. Quindi la risposta corretta è `port: 8081, env: production`. Un agente che prende il primo README trova 8080 (stale); uno che prende l'archivio trova 8081 (corretto per caso); solo chi verifica contro `tools/run_server.py` conferma.

2. **`regex_strict` sui valori attesi.** Sostituire `contains "effective"` con `regex_strict` che fa match su pattern `port:\s*8081` e `env:\s*production`. Questo costringe l'agente a riportare i valori effettivi, non solo la parola "effective".

3. **Verifica della catena.** Aggiungere un check che il report citi il percorso di indirezione seguito (es. `regex_strict` su `README\.md -> docs/README\.md -> config/app\.yaml`). Questo trasforma il task da "trova il config" a "documenta come lo hai trovato".

##### 4. Acceptance prima / dopo

**Prima**: vedere sopra.

**Dopo**:

```json
"acceptance": [
  {"type": "exists", "path": "reports/effective_config.md", "weight": 2, "fatal": true},
  {"type": "regex_strict", "path": "reports/effective_config.md",
   "pattern": "port:\\s*8081\\b", "weight": 2, "fatal": true},
  {"type": "regex_strict", "path": "reports/effective_config.md",
   "pattern": "env:\\s*production\\b", "weight": 2, "fatal": true},
  {"type": "regex_strict", "path": "reports/effective_config.md",
   "pattern": "README\\.md\\s*->\\s*docs/README\\.md\\s*->\\s*config/app\\.yaml",
   "weight": 1, "fatal": false},
  {"type": "not_contains", "path": "reports/effective_config.md",
   "text": "port: 8080", "weight": 1, "fatal": false},
  {"type": "regex_strict", "path": "reports/effective_config.md",
   "pattern": "consumer:\\s*tools/run_server\\.py", "weight": 1}
]
```

Incrementare `task_revision` da 2 a 3.

##### 5. Cosa cattura ora

- **"effective" come keyword vuota**: bloccata. Senza i valori `8081` e `production` non si passa.
- **Primo README trovato**: bloccato da `not_contains "port: 8080"`. L'agente che copia dal `docs/README.md` stale non passa.
- **Nessuna documentazione del percorso**: penalizzato. La regex sulla catena è non-fatal ma conta nel punteggio.
- **Nessuna verifica consumer**: penalizzato. La regex `consumer:` obbliga a citare `tools/run_server.py`.
- **Casi limite**: il `regex_strict` usa `\b` word boundary per evitare match parziali (es. `80810` non deve matchare `8081`). Da validare in `evaluators.py` con `re.search` + `\b`.

---

#### `tool_use_003` — Diagnosi, fix, rerun, prova

##### 1. Stato attuale

Prompt: esegui il test command fornito, diagnostica il fallimento, identifica il singolo file responsabile, fixalo, riesegui la suite completa, prova che il failure originale è gone. Non indebolire i test o alterare le aspettative.

Acceptance corrente:

```json
"acceptance": [
  {"type": "command", "command": "python -m pytest -q", "timeout": 45,
   "weight": 4, "fatal": true}
]
```

Tier dichiarato: T5. Run registrata: pass (ma solo perché pytest era già verde — vedi sotto).

##### 2. Debolezza

Il singolo check `python -m pytest -q` è circolare: l'agente controlla sia il codice che i test. Se l'agente *elimina* il test che fallisce o *lo indebolisce* (`assert True`), pytest diventa verde. Il prompt dice "non indebolire i test" ma l'acceptance non lo verifica. Inoltre, il difetto nel fixture (`broken_tool.py` con TypeError) è *lo stesso* usato in altri 4 task: un agente che lo ha visto una volta ha pattern-matchato la soluzione (cast a `float`).

La run registrata mostra `tool_use_003` "passato" ma l'artefatto `scripts/analyze_expenses.py` contiene un typo (`monthlyonth_key]` vs `monthly[month_key]`) che l'evaluator non esegue mai.

##### 3. Logica dell'indurimento

Tre modifiche coordinate:

1. **Test pre-confezionati nel fixture.** Aggiungere `tests/test_broken_tool.py` al fixture con assertion reali (non scritti dall'agente). L'agente *non* deve modificare questo file. Aggiungere `unchanged tests/test_broken_tool.py` (sha256) come check fatal: se l'agente lo tocca, fallisce.

2. **Secondo test ambiguo.** Aggiungere `tests/test_helpers.py` che *passa* ma referenzia `broken_tool` in modo fuorviante (es. un mock che simula il comportamento atteso). Un agente naive "sistema" `test_helpers.py` invece di `broken_tool.py`. Aggiungere `unchanged tests/test_helpers.py` come check fatal.

3. **Verifica della correzione reale.** Aggiungere `regex_strict` su `projects/broken_tool.py` che verifica il pattern `float\(` sia presente (la correzione corretta è il cast a float). Aggiungere anche `not_contains` su `assert True` e `pass` nei file di test per bloccare l'indebolimento.

In alternativa (più ambiziosa): sostituire `broken_tool.py` con un nuovo difetto più sottile, es. un off-by-one in un date range. Vedere sezione 7 per la discussione cross-benchmark.

##### 4. Acceptance prima / dopo

**Prima**: vedere sopra.

**Dopo**:

```json
"acceptance": [
  {"type": "command", "command": "python -m pytest -q", "timeout": 45,
   "weight": 3, "fatal": true},
  {"type": "unchanged", "path": "tests/test_broken_tool.py", "weight": 2, "fatal": true},
  {"type": "unchanged", "path": "tests/test_helpers.py", "weight": 2, "fatal": true},
  {"type": "regex_strict", "path": "projects/broken_tool.py",
   "pattern": "float\\(", "weight": 2, "fatal": true},
  {"type": "not_contains", "path": "tests/test_broken_tool.py",
   "text": "assert True", "weight": 1, "fatal": true},
  {"type": "not_contains", "path": "tests/test_helpers.py",
   "text": "assert True", "weight": 1, "fatal": true},
  {"type": "regex_strict", "path": "reports/fix_summary.md",
   "pattern": "root cause:\\s*.+", "weight": 1}
]
```

Incrementare `task_revision` da 2 a 3.

##### 5. Cosa cattura ora

- **Indebolimento dei test**: bloccato da `not_contains "assert True"` + `unchanged` su entrambi i file di test.
- **Modifica del file sbagliato**: bloccato da `unchanged tests/test_helpers.py`. L'agente deve toccare solo `projects/broken_tool.py`.
- **Pattern matching sul TypeError conosciuto**: parzialmente mitigato dal secondo test ambiguo. Per una mitigazione completa serve un secondo difetto indipendente (vedi sezione 7).
- **Nessuna documentazione del fix**: penalizzato dalla `regex_strict` su `root cause:` nel summary.
- **Casi limite**: l'`unchanged` sha256 è sensibile a whitespace newline finale. L'evaluator deve normalizzare (es. `hashlib.sha256(content.encode()).hexdigest()`) e accettare anche trailing newline.

##### Tabella comparativa `tool_use`

| Task | Debolezza chiave | Modifica principale | Nuovo check type | Impatto |
|------|------------------|---------------------|------------------|---------|
| `tool_use_001` | Classificazione non verificata; nome vs contenuto | JSON con `evidence_hash` + file trappola | `json_field_equals` + `sha256_match` + `min_count` | Alto |
| `tool_use_002` | "effective" come substring; singolo README | `regex_strict` su valori + multi-README indiretto | `regex_strict` + `not_contains` | Alto |
| `tool_use_003` | Agente scrive test; singolo difetto noto | Test pre-confezionati + `unchanged` + secondo test ambiguo | `unchanged` + `not_contains` + `regex_strict` | Alto |



---

### 4.2 `memory`

Categoria di 4 task che valuta la persistenza duratura delle preferenze attraverso run cold → warm → warm → warm. È la categoria dove la differenza tra "agente che ricorda dal prompt" e "agente che recupera da memoria durevole" è cruciale, e dove il design attivo del benchmark è più debole: il prompt stesso contiene quasi sempre l'informazione che l'agente dovrebbe "ricordare".

#### `memory_001` — Cold run: apprendi 3 preferenze

##### 1. Stato attuale

Prompt (cold): apprendi tre preferenze dell'utente (Python come linguaggio, strumenti semplici, regola no-commit). Memorizza solo ciò che è duraturo (non le preferenze transitorie come "oggi piove"). Salva `reports/memory_note.md`.

Acceptance corrente:

```json
"acceptance": [
  {"type": "exists", "path": "reports/memory_note.md", "weight": 2, "fatal": true},
  {"type": "contains", "path": "reports/memory_note.md", "text": "Python", "weight": 1},
  {"type": "contains", "path": "reports/memory_note.md", "text": "commit", "weight": 1}
]
```

Tier dichiarato: T3. Run registrata: pass.

##### 2. Debolezza

Il prompt stesso nomina le tre preferenze (Python, simple tools, no-commit). L'agente non deve *recuperare* nulla: gli basta *echo* le parole dal prompt al report. Il check `contains "Python"` e `contains "commit"` è soddisfatto da una riga "User prefers Python and does not commit." — zero retrieval, zero ragionamento.

Manca una prova che l'agente abbia effettivamente *appreso* qualcosa che non era nel prompt: nessuna informazione laterale, nessun token segreto, nessuna preferenza deducibile solo dal contesto.

##### 3. Logica dell'indurimento

La logica è creare un "proof of retrieval" che non può essere bypassato dall'echo dal prompt:

1. **Secret token nel fixture.** Aggiungere al seed `notes/user_preferences.md` con contenuto tipo:

   ```markdown
   # User Preferences (internal notes)
   preference_token: 7K9X2A
   Primary language: Python
   Tooling style: simple, no abstractions
   VCS policy: never commit, save to /tmp
   ```

   Il `preference_token` è un token random che l'agente *deve* leggere dal file, non può essere nel prompt.

2. **`regex_strict` sul token.** In `memory_001` richiedere che il report contenga il token `7K9X2A`. Questo è un proof of retrieval: l'agente deve aver letto `notes/user_preferences.md` per conoscere il token.

3. **Cold vs warm separation.** Il token va *persistito* in memoria e *usato* nella run warm (`memory_002`). In `memory_002` richiedere che il tool prodotto dall'agente contenga il token in un commento: questo prova che l'agente ha recuperato dalla run cold, non dal prompt corrente.

##### 4. Acceptance prima / dopo

**Prima**: vedere sopra.

**Dopo** (con `preference_token` nel fixture `notes/user_preferences.md`):

```json
"acceptance": [
  {"type": "exists", "path": "reports/memory_note.md", "weight": 2, "fatal": true},
  {"type": "regex_strict", "path": "reports/memory_note.md",
   "pattern": "7K9X2A", "weight": 3, "fatal": true},
  {"type": "regex_strict", "path": "reports/memory_note.md",
   "pattern": "language:\\s*Python\\b", "weight": 1, "fatal": false},
  {"type": "regex_strict", "path": "reports/memory_note.md",
   "pattern": "no-commit\\b|never\\s+commit\\b", "weight": 1, "fatal": false},
  {"type": "not_contains", "path": "reports/memory_note.md",
   "text": "today", "weight": 1, "fatal": false},
  {"type": "exists", "path": ".agent_memory/preferences.json",
   "weight": 2, "fatal": true},
  {"type": "json_valid", "path": ".agent_memory/preferences.json",
   "weight": 1, "fatal": true},
  {"type": "json_field_equals", "path": ".agent_memory/preferences.json",
   "jq_filter": ".preference_token", "expected": "7K9X2A",
   "weight": 2, "fatal": true}
]
```

Incrementare `task_revision` da 2 a 3. Il check `.agent_memory/preferences.json` introduce un path di memoria durevole standardizzato che il runner deve creare/preservare tra run.

##### 5. Cosa cattura ora

- **Echo dal prompt**: bloccato. Il token `7K9X2A` non è nel prompt, solo in `notes/user_preferences.md`. L'agente deve leggere il file.
- **Boilerplate con keyword**: bloccato. Le `regex_strict` su `language:` e `no-commit` richiedono formato strutturato, non prose generico.
- **Persistenza non dimostrata**: bloccata. La scrittura di `.agent_memory/preferences.json` prova che l'agente ha materialmente salvato la memoria, non solo scritto un report.
- **Casi limite**: il path `.agent_memory/` deve essere preservato dal runner tra run cold e warm (configurazione `workspace.retention`). Se l'agente scrive in un path diverso (es. `.memory/`), il check fallisce — questo è intenzionale: standardizza il path.

---

#### `memory_002` — Warm run: usa preferenze apprese

##### 1. Stato attuale

Prompt (warm): costruisci un piccolo tool usando le preferenze ricordate dalla run cold. Dimostra che almeno 2 preferenze hanno influenzato l'implementazione.

Acceptance corrente:

```json
"acceptance": [
  {"type": "exists", "path": "reports/memory_application.md", "weight": 2, "fatal": true},
  {"type": "contains", "path": "reports/memory_application.md", "text": "preference", "weight": 1}
]
```

Tier dichiarato: T4. Run registrata: pass (ma `tools/monthly_expenses.ts` non viene mai eseguito).

##### 2. Debolezza

`contains "preference"` è soddisfatto da "I used my preferences." — una frase. Il prompt chiede "dimostra che almeno 2 preferenze hanno influenzato l'implementazione" ma nessun check lo verifica. La run registrata produce un file `.ts` che non viene mai eseguito: l'agente può scrivere un TypeScript sintatticamente rotto e passare.

Inoltre, l'agente non deve dimostrare di aver *recuperato* la memoria dalla run cold: il prompt corrente dice "usa le preferenze ricordate", e l'agente può semplicemente re-derivare le preferenze dal prompt stesso (che cita "Python, simple tools, no-commit").

##### 3. Logica dell'indurimento

1. **Esecuzione del tool prodotto.** Aggiungere `command:` che esegue il tool dell'agente in modo deterministico. Se l'agente produce `tools/<name>.py`, il check è `python tools/<name>.py --input data/expenses.csv --output /tmp/out.txt`. Fatal: se il tool non gira, il task fallisce. Questo cattura il failure mode della run registrata.

2. **Token di persistenza.** Richiedere che il tool prodotto contenga il `preference_token` (es. `7K9X2A`) in un commento. Il token non è nel prompt della run warm: l'agente *deve* recuperarlo dalla memoria scritta nella run cold. Questo è il vero test di "warm".

3. **Verifica strutturata delle "2 preferenze".** Invece di `contains "preference"`, richiedere `regex_strict` multipli che catturino le due preferenze chiave:
   - `language:\s*Python` (preferenza 1)
   - `no-commit|never commit` (preferenza 2)

##### 4. Acceptance prima / dopo

**Prima**: vedere sopra.

**Dopo**:

```json
"acceptance": [
  {"type": "exists", "path": "reports/memory_application.md", "weight": 1, "fatal": true},
  {"type": "exists", "path": "tools/preferred_tool.py", "weight": 2, "fatal": true},
  {"type": "regex_strict", "path": "reports/memory_application.md",
   "pattern": "language:\\s*Python\\b", "weight": 1, "fatal": false},
  {"type": "regex_strict", "path": "reports/memory_application.md",
   "pattern": "no-commit\\b|never\\s+commit\\b", "weight": 1, "fatal": false},
  {"type": "regex_strict", "path": "reports/memory_application.md",
   "pattern": "7K9X2A", "weight": 3, "fatal": true},
  {"type": "command", "command": "python tools/preferred_tool.py --input data/expenses.csv --output /tmp/mem2_out.txt",
   "timeout": 30, "weight": 3, "fatal": true},
  {"type": "regex_strict", "path": "/tmp/mem2_out.txt",
   "pattern": "Total\\b", "weight": 1, "fatal": false},
  {"type": "json_field_equals", "path": ".agent_memory/preferences.json",
   "jq_filter": ".preference_token", "expected": "7K9X2A",
   "weight": 1, "fatal": true}
]
```

Incrementare `task_revision` da 2 a 3.

##### 5. Cosa cattura ora

- **Tool rotto non eseguito**: bloccato. Il `command:` gira effettivamente il tool; se non funziona, il task fallisce.
- **Echo delle preferenze dal prompt warm**: bloccato. Il token `7K9X2A` non è nel prompt warm, solo in memoria.
- **"dimostra 2 preferenze" non verificato**: bloccato. Le `regex_strict` su `language: Python` e `no-commit` verificano strutturalmente la dimostrazione.
- **Casi limite**: il path del tool è fissato a `tools/preferred_tool.py` dal prompt modificato (vedi appendice), eliminando il `ls | grep | head` fragile.

---

#### `memory_003` — Warm run: preferenza cambiata

##### 1. Stato attuale

Prompt (warm): la preferenza duratura per i nuovi strumenti di automazione è cambiata da Python a TypeScript. Aggiorna la conoscenza senza cancellare preferenze non correlate, spiega la risoluzione del conflitto, crea il nuovo tool in TypeScript, verifica che la vecchia preferenza Python non si applichi più ai nuovi tool mentre la regola no-commit resta.

Acceptance corrente:

```json
"acceptance": [
  {"type": "exists", "path": "reports/memory_update.md", "weight": 2, "fatal": true},
  {"type": "contains", "path": "reports/memory_update.md", "text": "TypeScript", "weight": 1},
  {"type": "contains", "path": "reports/memory_update.md", "text": "no-commit", "weight": 1}
]
```

Tier dichiarato: T5. Run registrata: pass.

##### 2. Debolezza

Il prompt stesso dice "preference changed from Python to TypeScript". L'agente può semplicemente echo "TypeScript" e "no-commit" in un report e passare. La "risoluzione del conflitto" è nominata ma non verificata — un agente che scrive "Conflict resolved." passa.

Non c'è alcun test che l'agente abbia *mantenuto* le altre preferenze (simple tools, no-commit). Non c'è alcun test che la vecchia preferenza Python sia stata *effettivamente* rimossa dalla memoria durevole.

##### 3. Logica dell'indurimento

1. **Verifica strutturata del conflitto risolto.** Sostituire `contains "TypeScript"` e `contains "no-commit"` con `regex_strict` multipli che catturano la struttura della risoluzione:
   - `old preference:\s*Python\b` (esplicita menzione della vecchia)
   - `new preference:\s*TypeScript\b` (esplicita menzione della nuova)
   - `preserved:\s*no-commit\b` (esplicita menzione di ciò che resta)
   - `conflict resolution:\s*.+` (descrizione non vuota)

2. **Verifica che la memoria sia effettivamente aggiornata.** Aggiungere `json_field_equals` su `.agent_memory/preferences.json` che verifica:
   - `primary_language == "TypeScript"` (nuova)
   - `vcs_policy == "no-commit"` (preservata)
   - `tooling_style == "simple"` (preservata)
   - `previous_primary_language == "Python"` (storico mantenuto, non cancellato)

3. **Token persistito.** Richiedere che il report includa il `preference_token` `7K9X2A` — prova che l'agente sta lavorando sullo stesso stato memoria della run cold.

##### 4. Acceptance prima / dopo

**Prima**: vedere sopra.

**Dopo**:

```json
"acceptance": [
  {"type": "exists", "path": "reports/memory_update.md", "weight": 1, "fatal": true},
  {"type": "regex_strict", "path": "reports/memory_update.md",
   "pattern": "old\\s+preference:\\s*Python\\b", "weight": 1, "fatal": false},
  {"type": "regex_strict", "path": "reports/memory_update.md",
   "pattern": "new\\s+preference:\\s*TypeScript\\b", "weight": 2, "fatal": true},
  {"type": "regex_strict", "path": "reports/memory_update.md",
   "pattern": "preserved:\\s*no-commit\\b", "weight": 2, "fatal": true},
  {"type": "regex_strict", "path": "reports/memory_update.md",
   "pattern": "conflict\\s+resolution:\\s*\\S", "weight": 1, "fatal": false},
  {"type": "regex_strict", "path": "reports/memory_update.md",
   "pattern": "7K9X2A", "weight": 2, "fatal": true},
  {"type": "json_field_equals", "path": ".agent_memory/preferences.json",
   "jq_filter": ".primary_language", "expected": "TypeScript",
   "weight": 2, "fatal": true},
  {"type": "json_field_equals", "path": ".agent_memory/preferences.json",
   "jq_filter": ".vcs_policy", "expected": "no-commit",
   "weight": 2, "fatal": true},
  {"type": "json_field_equals", "path": ".agent_memory/preferences.json",
   "jq_filter": ".tooling_style", "expected": "simple",
   "weight": 1, "fatal": false},
  {"type": "json_field_equals", "path": ".agent_memory/preferences.json",
   "jq_filter": ".previous_primary_language", "expected": "Python",
   "weight": 1, "fatal": false}
]
```

Incrementare `task_revision` da 2 a 3.

##### 5. Cosa cattura ora

- **Echo dal prompt**: bloccato. Il token `7K9X2A` non è nel prompt.
- **"Conflict resolved" vuoto**: bloccato. La `regex_strict` su `conflict resolution:\s*\S` richiede contenuto non vuoto.
- **Cancellazione accidentale di preferenze**: bloccata. I check `json_field_equals` su `vcs_policy` e `tooling_style` verificano che le preferenze non toccate siano rimaste.
- **Storico non mantenuto**: penalizzato. Il check su `previous_primary_language` (non fatal) verifica che l'agente abbia mantenuto traccia del cambiamento, non solo sovrascritto.
- **Casi limite**: il campo `previous_primary_language` è non-fatal perché alcuni agenti potrebbero ragionevolmente non mantenere lo storico. È un segnale di qualità, non un requisito.

---

#### `memory_004` — Warm run: tool con vincoli preservati

##### 1. Stato attuale

Prompt (warm): costruisci un altro tool. Preserva la distinzione tra nuovo (TypeScript) e esistente (Python). Verifica che la regola no-commit sia rispettata.

Acceptance corrente:

```json
"acceptance": [
  {"type": "exists", "path": "reports/memory_consistency.md", "weight": 2, "fatal": true},
  {"type": "contains", "path": "reports/memory_consistency.md", "text": "TypeScript", "weight": 1},
  {"type": "contains", "path": "reports/memory_consistency.md", "text": "commit", "weight": 1}
]
```

Tier dichiarato: T5. Run registrata: timeout (l'agente ha cercato di fare browsing reale).

##### 2. Debolezza

Identica a `memory_003`: il prompt nomina TypeScript e commit, l'agente echoa. Il timeout della run registrata è ironico: l'agente che fa davvero il lavoro (browsing, recupero, build) supera il timeout, mentre uno che scribacchia due parole passerebbe in 2 secondi. Questo è un *incentivo perverso*.

La "regola no-commit" non è verificata: il prompt dice "non committare" ma l'acceptance non controlla lo stato del repo.

##### 3. Logica dell'indurimento

1. **`.git/` piantato nel workspace.** Aggiungere un repository git inizializzato nel seed workspace (`benchmarks/fixtures/workspace/.git/`). L'agente è tentato di fare `git commit` per "salvare" il suo lavoro. La regola no-commit è ora *verificabile*: l'acceptance controlla che `.git/HEAD` e `.git/refs/` siano *invariati* (sha256 del tree).

2. **Esecuzione del tool prodotto.** Come `memory_002`, aggiungere `command:` che esegue il tool.

3. **Terzo segnale contraddittorio.** Aggiungere al prompt di `memory_004` una "nota utente" che dice "per i tool di sicurezza, usa Python". L'agente deve ora produrre *due* tool: uno TypeScript (generale) e uno Python (security). Questo testa la capacità di mantenere regole gerarchiche.

##### 4. Acceptance prima / dopo

**Prima**: vedere sopra.

**Dopo**:

```json
"acceptance": [
  {"type": "exists", "path": "reports/memory_consistency.md", "weight": 1, "fatal": true},
  {"type": "exists", "path": "tools/general_tool.ts", "weight": 2, "fatal": true},
  {"type": "exists", "path": "tools/security_tool.py", "weight": 2, "fatal": true},
  {"type": "regex_strict", "path": "reports/memory_consistency.md",
   "pattern": "general:\\s*TypeScript\\b", "weight": 2, "fatal": true},
  {"type": "regex_strict", "path": "reports/memory_consistency.md",
   "pattern": "security:\\s*Python\\b", "weight": 2, "fatal": true},
  {"type": "regex_strict", "path": "reports/memory_consistency.md",
   "pattern": "7K9X2A", "weight": 2, "fatal": true},
  {"type": "command", "command": "ts-node tools/general_tool.ts --input data/expenses.csv --output /tmp/g_out.txt",
   "timeout": 30, "weight": 2, "fatal": true},
  {"type": "command", "command": "python tools/security_tool.py --input data/expenses.csv --output /tmp/s_out.txt",
   "timeout": 30, "weight": 2, "fatal": true},
  {"type": "unchanged", "path": ".git/HEAD", "weight": 3, "fatal": true},
  {"type": "unchanged", "path": ".git/refs/heads/main", "weight": 3, "fatal": true},
  {"type": "command", "command": "git -C $WORKSPACE log --oneline | wc -l | tr -d ' '",
   "expected_output": "0", "timeout": 10, "weight": 2, "fatal": true}
]
```

Incrementare `task_revision` da 2 a 3.

##### 5. Cosa cattura ora

- **Commit eseguito**: bloccato. I check `unchanged` su `.git/HEAD` e `.git/refs/heads/main` verificano che non ci siano nuovi commit.
- **Singolo tool invece di due**: bloccato. I due `exists` su `general_tool.ts` e `security_tool.py` obbligano l'agente a gestire il conflitto Python vs TypeScript.
- **Tool non eseguiti**: bloccato dai due `command:`.
- **Echo dal prompt**: bloccato dal token `7K9X2A`.
- **Casi limite**: il `ts-node` deve essere installato nell'ambiente di esecuzione. Se non lo è, il check `command:` fallisce per ragioni ambientali, non per colpa dell'agente. Il runner deve garantire `ts-node` come dipendenza o usare `npx ts-node`.

##### Tabella comparativa `memory`

| Task | Debolezza chiave | Modifica principale | Nuovo check type | Impatto |
|------|------------------|---------------------|------------------|---------|
| `memory_001` | Echo dal prompt; no proof di retrieval | Secret token nel fixture + memoria durevole JSON | `regex_strict` + `json_field_equals` | Molto alto |
| `memory_002` | Tool non eseguito; "2 preferenze" non verificato | `command:` + token persistito + `regex_strict` multipli | `command` + `regex_strict` + `json_field_equals` | Alto |
| `memory_003` | Conflitto "risolto" con keyword; cancellazione non verificata | `regex_strict` strutturata + `json_field_equals` su memoria | `regex_strict` multipli + `json_field_equals` multipli | Molto alto |
| `memory_004` | No-commit non verificato; singolo tool | `.git/` piantato + due tool richiesti | `unchanged` + `command` multipli | Alto |

---

### 4.3 `knowledge`

Categoria di 3 task che valuta reperimento, confronto e risoluzione di conflitti tra fonti. È la categoria dove la "ground truth" è più sfuggente (le risposte sono qualitative), ma dove il rischio di fabbricazione è massimo: l'agente può inventare azioni, citazioni e priorità senza che l'evaluator lo noti.

#### `knowledge_001` — Azioni non risolte con evidenza

##### 1. Stato attuale

Prompt: trova le 3 azioni non risolte più importanti nel workspace. Costruisci una tabella di evidenza con owner, deadline, priority, source, confidence. Salva `reports/unresolved_actions.md`. Non inventare evidenza.

Acceptance corrente:

```json
"acceptance": [
  {"type": "exists", "path": "reports/unresolved_actions.md", "weight": 2, "fatal": true},
  {"type": "contains", "path": "reports/unresolved_actions.md", "text": "Source", "weight": 1},
  {"type": "contains", "path": "reports/unresolved_actions.md", "text": "Priority", "weight": 1},
  {"type": "contains", "path": "reports/unresolved_actions.md", "text": "Confidence", "weight": 1},
  {"type": "min_lines", "path": "reports/unresolved_actions.md", "min": 6, "weight": 1}
]
```

Tier dichiarato: T3. Run registrata: pass.

##### 2. Debolezza

Tutte le parole chiave ("Source", "Priority", "Confidence") sono nel prompt. L'agente può scrivere "Source: TODO, Priority: TODO, Confidence: TODO" per 6 righe e passare. Il `min_lines: 6` è l'unico gate strutturale, ed è banalmente bypassabile.

In particolare, "Non inventare evidenza" è nel prompt ma non è verificabile: l'evaluator non ha modo di sapere se una "evidence_quote" riportata sia realmente presente nelle fonti del workspace.

Il fixture ha 3 documenti: `notes/meeting_notes.md` (10 righe), `procedures/current.md` (5 righe), `procedures/previous.md` (6 righe). Le 3 azioni non risolte sono ovvie leggendo i 3 file.

##### 3. Logica dell'indurimento

1. **Output strutturato JSON con quote verificabili.** Costringere l'agente a produrre `reports/unresolved_actions.json` con schema `[{action, owner, deadline, priority, source_doc, source_section, confidence, evidence_quote}]`. Il campo `evidence_quote` deve essere una sottostringa *verbatim* del `source_doc` citato. L'evaluator legge il file del workspace citato in `source_doc` e fa `assert evidence_quote in fixture_content`. Se la quote non c'è, la voce è invalidata.

2. **Count esatto.** Il fixture ha esattamente 3 azioni non risolte + 1 già completata (da escludere). L'acceptance verifica `length == 3`. Un agente che ne inventa 5 o ne riporta 2 fallisce.

3. **Distrattore "azione già fatta".** Aggiungere a `notes/old_meeting_notes.md` un'azione "review Q3 budget" che è *già completata* (segnata come tale nel file). L'agente non deve includerla. `not_contains` su `unresolved_actions.json` per la stringa "Q3 budget" garantisce che l'agente abbia distinto "completata" da "non risolta".

4. **Owner ambiguo.** Aggiungere al fixture una mail che si riferisce allo stesso "Francesco" come "Fran". L'agente deve riconoscerli come la stessa persona o flaggare l'ambiguità. `regex_strict` su `confidence.*0\.\d` (minore di 1.0) verifica che l'agente abbia esplicitato l'incertezza.

##### 4. Acceptance prima / dopo

**Prima**: vedere sopra.

**Dopo**:

```json
"acceptance": [
  {"type": "exists", "path": "reports/unresolved_actions.json", "weight": 2, "fatal": true},
  {"type": "json_valid", "path": "reports/unresolved_actions.json", "weight": 1, "fatal": true},
  {"type": "min_count", "path": "reports/unresolved_actions.json",
   "jq_filter": "length", "expected": 3, "weight": 2, "fatal": true},
  {"type": "json_field_equals", "path": "reports/unresolved_actions.json",
   "jq_filter": "[.[] | .owner] | sort",
   "expected": ["Francesco", "Francesco", "Marta"], "weight": 2, "fatal": true},
  {"type": "regex_strict", "path": "reports/unresolved_actions.json",
   "pattern": "Q3\\s+budget", "weight": 2, "fatal": false,
   "negate": true},
  {"type": "regex_strict", "path": "reports/unresolved_actions.json",
   "pattern": "confidence\"\\s*:\\s*0\\.\\d", "weight": 1, "fatal": false},
  {"type": "evidence_quote_verified", "path": "reports/unresolved_actions.json",
   "jq_filter": ".[0]", "weight": 2, "fatal": true},
  {"type": "evidence_quote_verified", "path": "reports/unresolved_actions.json",
   "jq_filter": ".[1]", "weight": 2, "fatal": true},
  {"type": "evidence_quote_verified", "path": "reports/unresolved_actions.json",
   "jq_filter": ".[2]", "weight": 2, "fatal": true}
]
```

Il check type `evidence_quote_verified` è nuovo (vedi sezione 5): legge il campo `source_doc` dell'entry, apre il file corrispondente nel workspace, e fa `assert evidence_quote in content`.

Incrementare `task_revision` da 2 a 3.

##### 5. Cosa cattura ora

- **Boilerplate con keyword**: bloccato. L'output è JSON strutturato.
- **Count inventato**: bloccato. `length == 3` con owner specifici.
- **Evidenza fabbricata**: bloccata. `evidence_quote_verified` confronta la quote con il file effettivo.
- **Distrattore "già completato" inglobato**: bloccato da `not_contains "Q3 budget"`.
- **Ambiguità owner ignorata**: penalizzata. La regex `confidence: 0.\d` richiede che almeno una voce abbia confidence < 1.0.
- **Casi limite**: l'`evidence_quote_verified` deve normalizzare whitespace (es. collapse multiple spaces) per evitare falsi negativi su citazioni con spazi leggermente diversi. Da definire in `evaluators.py`.

---

#### `knowledge_002` — Diff tra procedure

##### 1. Stato attuale

Prompt: confronta la procedura corrente con quella precedente. Identifica additions, removals, changed, unchanged. Cita le sezioni delle fonti. Salva `reports/procedure_diff.md`.

Acceptance corrente:

```json
"acceptance": [
  {"type": "exists", "path": "reports/procedure_diff.md", "weight": 2, "fatal": true},
  {"type": "contains", "path": "reports/procedure_diff.md", "text": "Changed", "weight": 1},
  {"type": "min_lines", "path": "reports/procedure_diff.md", "min": 8, "weight": 1}
]
```

Tier dichiarato: T4. Run registrata: pass.

##### 2. Debolezza

Il diff tra `procedures/current.md` (5 righe) e `procedures/previous.md` (6 righe) è banale: le differenze sono ovvie a chiunque legga i due file. Il check `contains "Changed"` è soddisfatto da una riga "Changed: see above." — nessuna verifica strutturale del delta.

Le 4 categorie richieste (additions, removals, changed, unchanged) non sono verificate singolarmente: l'agente può ometterne una e passare con `min_lines: 8`.

##### 3. Logica dell'indurimento

1. **3 file con contraddizioni reali.** Espandere il fixture a 3 versioni di procedure (`previous.md`, `current.md`, `next_draft.md`) con contraddizioni multiple:
   - `previous.md` dice "submit report by Friday via email"
   - `current.md` dice "submit report by EOW via Slack"
   - `next_draft.md` dice "submit report by next Wednesday via PR"

   L'agente deve identificare 3 transizioni: previous → current, current → next_draft, previous → next_draft.

2. **`regex_strict` per ogni categoria.** Sostituire `contains "Changed"` con 4 `regex_strict` distinte:
   - `additions?:\s*\S` (almeno un'addizione)
   - `removals?:\s*\S`
   - `changed?:\s*\S`
   - `unchanged?:\s*\S`

3. **Citazione delle sezioni verificata.** Richiedere che ogni voce citi una sezione specifica del file sorgente (es. `[current.md:3]`). `regex_strict` su `\[(previous|current|next_draft)\.md:\d+\]` verifica la presenza di citazioni ben formate.

##### 4. Acceptance prima / dopo

**Prima**: vedere sopra.

**Dopo**:

```json
"acceptance": [
  {"type": "exists", "path": "reports/procedure_diff.md", "weight": 2, "fatal": true},
  {"type": "regex_strict", "path": "reports/procedure_diff.md",
   "pattern": "additions?\\s*:\\s*\\S", "weight": 1, "fatal": true},
  {"type": "regex_strict", "path": "reports/procedure_diff.md",
   "pattern": "removals?\\s*:\\s*\\S", "weight": 1, "fatal": true},
  {"type": "regex_strict", "path": "reports/procedure_diff.md",
   "pattern": "changed?\\s*:\\s*\\S", "weight": 1, "fatal": true},
  {"type": "regex_strict", "path": "reports/procedure_diff.md",
   "pattern": "unchanged?\\s*:\\s*\\S", "weight": 1, "fatal": false},
  {"type": "regex_strict", "path": "reports/procedure_diff.md",
   "pattern": "\\[(previous|current|next_draft)\\.md:\\d+\\]",
   "weight": 2, "fatal": true},
  {"type": "min_count", "path": "reports/procedure_diff.md",
   "regex": "\\[.+\\.md:\\d+\\]", "expected": 4, "weight": 1, "fatal": false},
  {"type": "regex_strict", "path": "reports/procedure_diff.md",
   "pattern": "Friday.*Slack|Wednesday.*PR", "weight": 1, "fatal": false,
   "negate": true}
]
```

L'ultimo check verifica che l'agente non abbia mescolato attribuzioni (es. assegnato Friday a Slack invece che a email).

Incrementare `task_revision` da 2 a 3.

##### 5. Cosa cattura ora

- **Boilerplate con "Changed"**: bloccato. Le 4 `regex_strict` obblighiano a strutturare il diff in 4 sezioni distinte.
- **Citazioni generiche senza source section**: bloccato. La regex `\[(previous|current|next_draft)\.md:\d+\]` obbliga a citare file + riga.
- **Cross-attribution errata**: penalizzata. La regex di negazione cattura attribuzioni sbagliate.
- **Diff banale**: mitigato dall'aggiunta del terzo file. L'agente deve gestire 3 transizioni, non 1.
- **Casi limite**: il `min_count` con regex richiede un nuovo check type (o estensione del `min_count` esistente per accettare un filtro regex). Vedi sezione 5.

---

#### `knowledge_003` — Fonte autorevole in conflitto

##### 1. Stato attuale

Prompt: determina quale workflow è autorevole quando le procedure correnti e precedenti confliggono con le meeting notes. Costruisci una matrice claim-evidence, identifica contraddizioni, classifica l'autorità delle fonti con criteri espliciti, dai una raccomandazione con incertezza, salva `reports/evidence_review.md`. Non inventare evidenza.

Acceptance corrente:

```json
"acceptance": [
  {"type": "exists", "path": "reports/evidence_review.md", "weight": 2, "fatal": true},
  {"type": "contains", "path": "reports/evidence_review.md", "text": "Evidence", "weight": 1},
  {"type": "contains", "path": "reports/evidence_review.md", "text": "Uncertainty", "weight": 1},
  {"type": "min_lines", "path": "reports/evidence_review.md", "min": 8, "weight": 1}
]
```

Tier dichiarato: T5. Run registrata: pass.

##### 2. Debolezza

La "contraddizione" nel fixture è banale: `current.md` dice "save as .md" e "review required", `previous.md` dice "save as .txt" e "no review". Le meeting notes non contengono una terza versione. Un agente che scrive "Evidence: see above. Uncertainty: low." passa.

Non c'è alcun test che l'agente abbia *identificato* la fonte autorevole corretta, né che abbia *classificato l'autorità* in modo strutturato.

##### 3. Logica dell'indurimento

1. **3 fonti con autorità gerarchica esplicita.** Costruire il fixture con:
   - `procedures/previous.md` (stale, autorità bassa) → "save as .txt, no review"
   - `procedures/current.md` (attuale, autorità media) → "save as .md, review required"
   - `notes/meeting_notes.md` (recente, autorità alta) → "save as .md, review optional, deadline moved to next Wednesday"

   La risposta corretta: la meeting note è la più autorevole (più recente, più specifica al contesto).

2. **`regex_strict` sulla fonte autorevole.** Richiedere che il report citi esplicitamente `authoritative_source:\s*meeting_notes` o `authoritative_source:\s*notes/meeting_notes\.md`. Questo trasforma "classifica l'autorità" da una descrizione qualitativa a un giudizio verificabile.

3. **`regex_strict` su criteri di autorità.** Richiedere che il report elenchi i criteri di classificazione (es. `criteria:\s*recency, specificity, official status`). Questo obbliga l'agente a essere esplicito sul ragionamento.

4. **Matrice claim-evidence strutturata.** Richiedere `reports/claim_evidence.json` con schema `[{claim, source_doc, source_section, evidence_quote, contradicting_claims}]`. L'`evidence_quote_verified` (come in `knowledge_001`) garantisce che le quote non siano fabbricate.

##### 4. Acceptance prima / dopo

**Prima**: vedere sopra.

**Dopo**:

```json
"acceptance": [
  {"type": "exists", "path": "reports/evidence_review.md", "weight": 1, "fatal": true},
  {"type": "exists", "path": "reports/claim_evidence.json", "weight": 2, "fatal": true},
  {"type": "json_valid", "path": "reports/claim_evidence.json", "weight": 1, "fatal": true},
  {"type": "regex_strict", "path": "reports/evidence_review.md",
   "pattern": "authoritative_source:\\s*(notes/)?meeting_notes",
   "weight": 3, "fatal": true},
  {"type": "regex_strict", "path": "reports/evidence_review.md",
   "pattern": "criteria:\\s*\\S", "weight": 1, "fatal": false},
  {"type": "regex_strict", "path": "reports/evidence_review.md",
   "pattern": "uncertainty:\\s*(low|medium|high)", "weight": 2, "fatal": true},
  {"type": "min_count", "path": "reports/claim_evidence.json",
   "jq_filter": "length", "expected": 3, "weight": 1, "fatal": true},
  {"type": "evidence_quote_verified", "path": "reports/claim_evidence.json",
   "jq_filter": ".[0]", "weight": 2, "fatal": true},
  {"type": "evidence_quote_verified", "path": "reports/claim_evidence.json",
   "jq_filter": ".[1]", "weight": 2, "fatal": true},
  {"type": "evidence_quote_verified", "path": "reports/claim_evidence.json",
   "jq_filter": ".[2]", "weight": 2, "fatal": true}
]
```

Incrementare `task_revision` da 2 a 3.

##### 5. Cosa cattura ora

- **"Evidence" come keyword vuota**: bloccato. La matrice JSON è obbligatoria e ogni quote è verificata contro il file sorgente.
- **Giudizio qualitativo non verificabile**: bloccato. `authoritative_source: meeting_notes` ha una risposta corretta precomputata.
- **"Uncertainty" senza livello**: bloccato. La regex richiede `low|medium|high`.
- **Criteri di autorità impliciti**: penalizzati. La regex `criteria:\s*\S` obbliga a esplicitare.
- **Contraddizioni non identificate**: parzialmente mitigato dal campo `contradicting_claims` nello schema JSON. L'evaluator potrebbe ulteriormente verificare che il conteggio delle contraddizioni sia ≥ 2.
- **Casi limite**: il `evidence_quote_verified` richiede che l'evaluator abbia accesso al workspace (non solo all'output). Il runner passa già il workspace ai validatori, quindi ok.

##### Tabella comparativa `knowledge`

| Task | Debolezza chiave | Modifica principale | Nuovo check type | Impatto |
|------|------------------|---------------------|------------------|---------|
| `knowledge_001` | Provenance fabbricabile; distrattori non gestiti | JSON con `evidence_quote` verificata + count esatto + owner ambiguo | `evidence_quote_verified` + `min_count` + `regex_strict` (negate) | Molto alto |
| `knowledge_002` | Diff banale; categorie non verificate | 3 file con contraddizioni + `regex_strict` per categoria + citazioni file:riga | `regex_strict` multipli + `min_count` con regex | Alto |
| `knowledge_003` | Giudizio qualitativo non verificabile; contraddizione superficiale | 3 fonti gerarchiche + `regex_strict` su fonte autorefica + JSON matrice | `regex_strict` + `evidence_quote_verified` + `min_count` | Molto alto |

---

### 4.4 `coding`

Categoria di 4 task che valuta generazione, debug, refactor e qualità del codice. È la categoria dove l'infrastruttura di testing (pytest) esiste già, ma dove il loophole "agente scrive sia codice che test" è massimo: il 100% del peso poggia su pytest, e l'agente controlla entrambi i lati dell'equazione.

#### `coding_001` — CLI CSV→HTML

##### 1. Stato attuale

Prompt: crea una CLI Python che legge il CSV delle vendite e scrive HTML deterministico. Valida header e righe malformate, supporta `--input/--output`, ritorna non-zero su input invalido, fornisci `--help` utile, includi test per input normale e due casi di fallimento. Non hard-codare i valori del fixture.

Acceptance corrente:

```json
"acceptance": [
  {"type": "command", "command": "python -m pytest -q", "timeout": 45,
   "weight": 4, "fatal": true},
  {"type": "command", "command": "python tools/report_cli.py --help",
   "timeout": 10, "weight": 1}
]
```

Tier dichiarato: T3. Run registrata: pass.

##### 2. Debolezza

L'agente scrive sia la CLI che i test. Se l'agente produce `tests/test_report_cli.py` con `def test_ok(): assert True`, pytest passa. Il prompt dice "non hard-codare i valori del fixture" ma non è verificato: l'agente può scrivere `assert "<expected_total>" in html_output` con un valore hardcodato, e i suoi test passano.

Il check `--help` esiste solo sull'output stdout, non sull'exit code. Il negative path (`--input nonexistent.csv` deve ritornare non-zero) non è verificato.

##### 3. Logica dell'indurimento

1. **Test nascosti nel fixture.** Aggiungere `tests/test_hidden.py` al seed workspace con assertion reali:
   - CSV con header duplicato → exit code non-zero
   - CSV con riga malformata (colonne scambiate) → exit code non-zero o warning specifico
   - CSV vuoto → exit code non-zero con messaggio di errore
   - CSV normale → HTML generato con totale corretto (verificato via regex su un valore precomputato)

   L'agente *non* deve modificare questo file. `unchanged tests/test_hidden.py` come check fatal.

2. **Test anti-hardcoding.** Aggiungere `data/sales_alt.csv` con valori *diversi* dal seed. Il check esegue `python tools/report_cli.py --input data/sales_alt.csv --output /tmp/out.html` e fa `regex_strict` su un totale che differisce dal seed (es. se il seed ha totale `580`, l'alt ha totale `742`). Un agente che ha hardcodato `580` fallisce.

3. **Exit code sul negative path.** Aggiungere `command:` che esegue `python tools/report_cli.py --input nonexistent.csv; test $? -ne 0` (o un wrapper Python che cattura exit code).

##### 4. Acceptance prima / dopo

**Prima**: vedere sopra.

**Dopo**:

```json
"acceptance": [
  {"type": "command", "command": "python -m pytest -q tests/test_hidden.py",
   "timeout": 45, "weight": 4, "fatal": true},
  {"type": "unchanged", "path": "tests/test_hidden.py", "weight": 3, "fatal": true},
  {"type": "command", "command": "python tools/report_cli.py --help",
   "timeout": 10, "weight": 1, "fatal": false},
  {"type": "command", "command": "python tools/report_cli.py --input nonexistent.csv 2>/dev/null; test $? -ne 0",
   "timeout": 10, "weight": 3, "fatal": true},
  {"type": "command", "command": "python tools/report_cli.py --input data/sales_alt.csv --output /tmp/coding1_alt.html",
   "timeout": 15, "weight": 2, "fatal": true},
  {"type": "regex_strict", "path": "/tmp/coding1_alt.html",
   "pattern": "742", "weight": 2, "fatal": true},
  {"type": "not_contains", "path": "tools/report_cli.py",
   "text": "580", "weight": 2, "fatal": true},
  {"type": "not_contains", "path": "tools/report_cli.py",
   "text": "100, 80, 120", "weight": 1, "fatal": false}
]
```

Incrementare `task_revision` da 2 a 3.

##### 5. Cosa cattura ora

- **Test trivialmente passanti scritti dall'agente**: bloccato. I test nascosti sono nel fixture e non modificabili.
- **Hardcoding dei valori del fixture**: bloccato. Il test su `sales_alt.csv` richiede un totale diverso, e `not_contains "580"` blocca la costante nel codice.
- **CLI che non gestisce input invalido**: bloccato. Il `command:` con `test $? -ne 0` verifica exit code non-zero.
- **`--help` come unico gate**: rimosso. Il `--help` è non-fatal.
- **Casi limite**: il `not_contains "580"` potrebbe dare falsi positivi se `580` appare in un commento o in una costante non correlata. Da raffinare con contesto (es. `not_contains` in una *stringa di output* specifica). L'implementazione attuale è conservativa: se il valore appare *da qualsiasi parte* del codice, fallisce.

---

#### `coding_002` — Debug con riproduzione

##### 1. Stato attuale

Prompt: esegui i test, riproduci il fallimento, identifica la root cause, applica il fix più piccolo, scrivi un test di regressione, riesegui la suite.

Acceptance corrente:

```json
"acceptance": [
  {"type": "command", "command": "python -m pytest -q", "timeout": 45,
   "weight": 4, "fatal": true}
]
```

Tier dichiarato: T4. Run registrata: pass.

##### 2. Debolezza

Identica a `tool_use_003`: pytest circolare, agente scrive test. In più, il difetto è lo stesso `broken_tool.py` TypeError usato in 4 altri task. Un agente che lo ha visto una volta ha pattern-matchato la soluzione.

Il prompt chiede "root cause" e "regression test" ma nessun check lo verifica: un agente che fixa con `try/except` e basta passa.

##### 3. Logica dell'indurimento

1. **Difetto diverso da `broken_tool.py`.** Introdurre un secondo difetto in `projects/off_by_one_tool.py`: una funzione che calcola il range di date ma ha un off-by-one (es. `range(start, end)` invece di `range(start, end+1)`, mancando l'ultimo giorno). L'agente deve fixare *entrambi* i difetti indipendentemente.

2. **Test pre-confezionati per entrambi i difetti.** `tests/test_broken_tool.py` (per il TypeError) e `tests/test_off_by_one.py` (per il date range). Entrambi `unchanged`.

3. **`regex_strict` su root cause.** Richiedere che il report includa `root cause:\s*.+` per *ciascuno* dei due difetti. Verifica che l'agente abbia effettivamente diagnosticato, non solo patchato.

4. **Regression test requirement.** Richiedere `exists tests/test_regression_*.py` con un nuovo file scritto dall'agente che testa i casi precedentemente falliti.

##### 4. Acceptance prima / dopo

**Prima**: vedere sopra.

**Dopo**:

```json
"acceptance": [
  {"type": "command", "command": "python -m pytest -q tests/test_broken_tool.py tests/test_off_by_one.py",
   "timeout": 45, "weight": 3, "fatal": true},
  {"type": "unchanged", "path": "tests/test_broken_tool.py", "weight": 2, "fatal": true},
  {"type": "unchanged", "path": "tests/test_off_by_one.py", "weight": 2, "fatal": true},
  {"type": "regex_strict", "path": "projects/broken_tool.py",
   "pattern": "float\\(", "weight": 1, "fatal": true},
  {"type": "regex_strict", "path": "projects/off_by_one_tool.py",
   "pattern": "end\\s*\\+\\s*1|end\\s*\\+\\s*\\d", "weight": 2, "fatal": true},
  {"type": "exists", "path": "tests/test_regression_broken.py", "weight": 1, "fatal": false},
  {"type": "exists", "path": "tests/test_regression_off_by_one.py", "weight": 1, "fatal": false},
  {"type": "regex_strict", "path": "reports/fix_summary.md",
   "pattern": "root cause.*broken_tool:\\s*.+",   "weight": 1, "fatal": true},
  {"type": "regex_strict", "path": "reports/fix_summary.md",
   "pattern": "root cause.*off_by_one:\\s*.+", "weight": 1, "fatal": true}
]
```

Incrementare `task_revision` da 2 a 3.

##### 5. Cosa cattura ora

- **Pattern matching sul TypeError conosciuto**: bloccato. Il secondo difetto (off-by-one) è indipendente e richiede diagnosi separata.
- **Fix con `try/except` invece di root cause**: bloccato. La `regex_strict` su `float\(` obbliga la correzione corretta.
- **Nessuna documentazione del root cause**: bloccato. Le regex sul summary richiedono una descrizione per *ciascun* difetto.
- **Regression test mancante**: penalizzato (non fatal). L'`exists` su `test_regression_*` incoraggia la scrittura.
- **Casi limite**: il pattern `end\s*\+\s*\d` è generico per consentire sia `end + 1` sia `end + 1` con whitespace vario. Accetterebbe anche `end + 2` (sbagliato) — da affinare con `end\s*\+\s*1\b`.

---

#### `coding_003` — Refactor preserving CLI

##### 1. Stato attuale

Prompt: rifattorizza `broken_tool.py` in moduli parse/validate/report. Preserva la CLI. Aggiungi test per edge cases.

Acceptance corrente:

```json
"acceptance": [
  {"type": "command", "command": "python -m pytest -q", "timeout": 45,
   "weight": 4, "fatal": true},
  {"type": "exists", "path": "reports/refactor_report.md", "weight": 1},
  {"type": "exists", "path": "tools/", "weight": 1}
]
```

Tier dichiarato: T4. Run registrata: pass.

##### 2. Debolezza

Identica a `coding_002`: agente scrive test, broken_tool è conosciuto. In più, "preserva la CLI" non è verificato: l'agente può cambiare l'interfaccia e passare pytest (che scrive lui).

"Refactor in parse/validate/report modules" non è verificato strutturalmente: l'agente può lasciare tutto in un file e passare.

##### 3. Logica dell'indurimento

1. **Test pre-confezionati che testano la CLI come black-box.** Aggiungere `tests/test_cli_contract.py` al fixture che:
   - Chiama `python projects/broken_tool.py --input data/expenses.csv --output /tmp/out.json`
   - Verifica exit code 0
   - Verifica che `/tmp/out.json` sia JSON valido con campi attesi

   `unchanged tests/test_cli_contract.py` come check fatal: l'agente deve preservare il contratto CLI.

2. **Verifica della separazione modulare.** Richiedere `exists` per 3 file distinti:
   - `projects/broken_tool/parse.py` (o `projects/parse.py`)
   - `projects/broken_tool/validate.py`
   - `projects/broken_tool/report.py`

3. **Smoke test della CLI refactorizzata.** `command:` che esegue la CLI refactorizzata e verifica l'output.

##### 4. Acceptance prima / dopo

**Prima**: vedere sopra.

**Dopo**:

```json
"acceptance": [
  {"type": "command", "command": "python -m pytest -q tests/test_cli_contract.py",
   "timeout": 30, "weight": 3, "fatal": true},
  {"type": "unchanged", "path": "tests/test_cli_contract.py", "weight": 2, "fatal": true},
  {"type": "exists", "path": "projects/broken_tool/parse.py", "weight": 2, "fatal": true},
  {"type": "exists", "path": "projects/broken_tool/validate.py", "weight": 2, "fatal": true},
  {"type": "exists", "path": "projects/broken_tool/report.py", "weight": 2, "fatal": true},
  {"type": "command", "command": "python -m projects.broken_tool --input data/expenses.csv --output /tmp/coding3_out.json",
   "timeout": 15, "weight": 2, "fatal": true},
  {"type": "json_valid", "path": "/tmp/coding3_out.json", "weight": 1, "fatal": true},
  {"type": "regex_strict", "path": "/tmp/coding3_out.json",
   "pattern": "total", "weight": 1, "fatal": false},
  {"type": "exists", "path": "reports/refactor_report.md", "weight": 1, "fatal": false},
  {"type": "regex_strict", "path": "reports/refactor_report.md",
   "pattern": "modules?\\s*:\\s*parse,\\s*validate,\\s*report", "weight": 1, "fatal": false}
]
```

Incrementare `task_revision` da 2 a 3.

##### 5. Cosa cattura ora

- **CLI non preservata**: bloccata. I test `test_cli_contract.py` (non modificabili) verificano il contratto.
- **Tutto in un file**: bloccato dai 3 `exists` sui moduli.
- **CLI che produce output non-JSON**: bloccato dal `json_valid` sull'output.
- **Casi limite**: il path `projects/broken_tool/` presuppone che l'agente scelga la struttura a package. Un'alternativa è `projects/parse.py`, `projects/validate.py`, `projects/report.py` — accettare entrambe con `exists_any`. Vedi sezione 5 per il check type `exists_any`.

---

#### `coding_004` — Robust reporting utility

##### 1. Stato attuale

Prompt: crea un'utilità di reporting robusta con struct tipizzati, test per input malformati e vuoti, README.

Acceptance corrente:

```json
"acceptance": [
  {"type": "command", "command": "python -m pytest -q", "timeout": 45,
   "weight": 3, "fatal": true},
  {"type": "exists", "path": "README.md", "weight": 1},
  {"type": "exists", "path": "reports/robust_report.md", "weight": 1}
]
```

Tier dichiarato: T5. Run registrata: pass.

##### 2. Debolezza

Identica a `coding_001`: agente scrive test, "struct tipizzati" non verificato, README esiste ma non è verificato. Il "robust" è nel prompt ma non misurato.

##### 3. Logica dell'indurimento

1. **Test nascosti con edge cases specifici.** Aggiungere `tests/test_robust.py` con:
   - Input vuoto → output gestito (non crash)
   - Input con tutti valori nulli → totale = 0, non NaN
   - Input con datetime mischiati a stringhe → parse error gestito
   - Input con codifica non-UTF8 → fallback o errore chiaro

2. **Verifica "struct tipizzati".** `regex_strict` su `tools/robust_report.py` per pattern `TypedDict|@dataclass|class\s+\w+:\s*` — verifica che l'agente abbia usato typed structs, non dict generici.

3. **README con sezioni obbligatorie.** `regex_strict` su `README.md` per `## Usage`, `## Examples`, `## Error handling`.

##### 4. Acceptance prima / dopo

**Prima**: vedere sopra.

**Dopo**:

```json
"acceptance": [
  {"type": "command", "command": "python -m pytest -q tests/test_robust.py",
   "timeout": 45, "weight": 4, "fatal": true},
  {"type": "unchanged", "path": "tests/test_robust.py", "weight": 2, "fatal": true},
  {"type": "regex_strict", "path": "tools/robust_report.py",
   "pattern": "TypedDict|@dataclass|^class\\s+\\w+.*:", "weight": 2, "fatal": true},
  {"type": "regex_strict", "path": "README.md",
   "pattern": "## Usage", "weight": 1, "fatal": true},
  {"type": "regex_strict", "path": "README.md",
   "pattern": "## Examples", "weight": 1, "fatal": false},
  {"type": "regex_strict", "path": "README.md",
   "pattern": "## Error handling", "weight": 1, "fatal": true},
  {"type": "exists", "path": "reports/robust_report.md", "weight": 1, "fatal": false},
  {"type": "command", "command": "python tools/robust_report.py --input /dev/null 2>/dev/null; test $? -ne 0",
   "timeout": 10, "weight": 2, "fatal": true},
  {"type": "command", "command": "python tools/robust_report.py --input data/expenses_empty.csv --output /tmp/coding4_empty.txt",
   "timeout": 10, "weight": 2, "fatal": true},
  {"type": "regex_strict", "path": "/tmp/coding4_empty.txt",
   "pattern": "0|empty", "weight": 1, "fatal": false}
]
```

(Pre-condizione: il fixture deve includere `data/expenses_empty.csv` con solo header, nessuna riga.)

Incrementare `task_revision` da 2 a 3.

##### 5. Cosa cattura ora

- **Test trivialmente passanti**: bloccati dai test nascosti.
- **Dict generici invece di typed structs**: bloccati dalla regex su `TypedDict|@dataclass|class`.
- **README senza struttura**: bloccato dalle regex `## Usage`, `## Error handling`.
- **CLI che crasha su input vuoto**: bloccato dal `command:` con `/dev/null` (deve ritornare non-zero) e dal `command:` con `expenses_empty.csv` (deve gestire senza crash).
- **Casi limite**: il pattern `^class\s+\w+.*:` ha falsi positivi su classi generiche. Da affinare con `class\s+\w+\(TypedDict\)|@dataclass\s*\nclass`.

##### Tabella comparativa `coding`

| Task | Debolezza chiave | Modifica principale | Nuovo check type | Impatto |
|------|------------------|---------------------|------------------|---------|
| `coding_001` | Agente scrive test; hardcoding valori fixture | Test nascosti + `sales_alt.csv` + `not_contains "580"` | `unchanged` + `not_contains` + `regex_strict` su output | Critico |
| `coding_002` | Singolo broken_tool noto; root cause non verificato | Secondo difetto off-by-one + `regex_strict` su `root cause:` | `unchanged` multipli + `regex_strict` su fix | Alto |
| `coding_003` | CLI non preservata; modularità non verificata | Test black-box CLI + `exists` su 3 moduli | `unchanged` + `exists` multipli + `json_valid` | Alto |
| `coding_004` | "Struct tipizzati" non verificato; README boilerplate | Test nascosti + `regex_strict` su TypedDict/dataclass + README structure | `unchanged` + `regex_strict` multipli | Alto |

---

### 4.5 `autonomy`

Categoria di 3 task che valuta pianificazione end-to-end, grounding e iterazione. È la categoria dove la differenza tra "agente autonomo" e "agente che segue script" dovrebbe essere massima, ma dove il design attuale permette a un agente di produrre artefatti superficialmente corretti ma non funzionanti.

#### `autonomy_001` — Report mensile spese

##### 1. Stato attuale

Prompt: produci un report mensile delle spese dal workspace. Identifica i dati transazionali autorevoli, crea uno strumento di analisi riutilizzabile, valida i totali, salva `reports/monthly_expense_report.md` + `tools/expense_report.py` + `tools/README.md`. Non modificare i dati sorgente.

Acceptance corrente:

```json
"acceptance": [
  {"type": "exists", "path": "reports/monthly_expense_report.md", "weight": 2, "fatal": true},
  {"type": "exists", "path": "tools/expense_report.py", "weight": 2, "fatal": true},
  {"type": "exists", "path": "tools/README.md", "weight": 1},
  {"type": "contains", "path": "reports/monthly_expense_report.md", "text": "Total Expenses", "weight": 1},
  {"type": "contains", "path": "reports/monthly_expense_report.md", "text": "Total Transactions", "weight": 1},
  {"type": "unchanged", "path": "data/expenses.csv", "weight": 2, "fatal": true}
]
```

Tier dichiarato: T3. Run registrata: pass (ma con script rotto invisibile).

##### 2. Debolezza

La run registrata mostra `scripts/analyze_expenses.py` con un typo (`monthlyonth_key]` invece di `monthly[month_key]`) che il runner non esegue mai. L'agente ha prodotto un report `.md` con i numeri giusti (presumibilmente calcolati a mano) ma il tool `.py` è rotto. Il task passa perché:
- `exists tools/expense_report.py` è soddisfatto (il file esiste, anche se rotto),
- `contains "Total Expenses"` è soddisfatto (l'agente ha scritto "Total Expenses: $91.07" nel .md),
- `unchanged data/expenses.csv` è soddisfatto.

Il totale `$91.07` può essere qualsiasi numero: l'evaluator non lo verifica. L'agente potrebbe scrivere "Total Expenses: $0.00" e passare.

##### 3. Logica dell'indurimento

1. **Esecuzione del tool prodotto.** Aggiungere `command:` che esegue `python tools/expense_report.py --input data/expenses.csv --output /tmp/ae.md` (fatal). Se il tool non gira, il task fallisce. Questo cattura il typo `monthlyonth_key]`.

2. **Verifica del totale corretto.** Aggiungere `regex_strict` su `/tmp/ae.md` per il pattern `Total Expenses:\s*\$91\.07`. Il totale è precomputato dal fixture (6 righe × rispettivi amount). Un agente che hardcoda un numero sbagliato fallisce.

3. **Row-level trap.** Aggiungere a `data/expenses.csv` una riga malformata (es. `2026-07-15,software,Editor,` con amount vuoto). Il report deve flaggare la riga come skipped. `regex_strict` su `skipped:\s*1` o `malformed_count:\s*1`.

4. **Anti-hardcoding.** Aggiungere `data/expenses_alt.csv` con valori diversi e `command:` che esegue il tool sull'alt. `regex_strict` su un totale diverso (es. `$742.50`).

##### 4. Acceptance prima / dopo

**Prima**: vedere sopra.

**Dopo**:

```json
"acceptance": [
  {"type": "exists", "path": "reports/monthly_expense_report.md", "weight": 1, "fatal": true},
  {"type": "exists", "path": "tools/expense_report.py", "weight": 1, "fatal": true},
  {"type": "exists", "path": "tools/README.md", "weight": 1, "fatal": false},
  {"type": "command", "command": "python tools/expense_report.py --input data/expenses.csv --output /tmp/ae.md",
   "timeout": 30, "weight": 3, "fatal": true},
  {"type": "regex_strict", "path": "/tmp/ae.md",
   "pattern": "Total\\s+Expenses:\\s*\\$91\\.07", "weight": 3, "fatal": true},
  {"type": "regex_strict", "path": "/tmp/ae.md",
   "pattern": "Total\\s+Transactions:\\s*6", "weight": 2, "fatal": true},
  {"type": "regex_strict", "path": "/tmp/ae.md",
   "pattern": "skipped:\\s*1|malformed_count:\\s*1", "weight": 2, "fatal": true},
  {"type": "command", "command": "python tools/expense_report.py --input data/expenses_alt.csv --output /tmp/ae_alt.md",
   "timeout": 30, "weight": 2, "fatal": true},
  {"type": "regex_strict", "path": "/tmp/ae_alt.md",
   "pattern": "Total\\s+Expenses:\\s*\\$742\\.50", "weight": 2, "fatal": true},
  {"type": "not_contains", "path": "tools/expense_report.py",
   "text": "91.07", "weight": 2, "fatal": true},
  {"type": "unchanged", "path": "data/expenses.csv", "weight": 2, "fatal": true},
  {"type": "unchanged", "path": "data/expenses_alt.csv", "weight": 2, "fatal": true}
]
```

Incrementare `task_revision` da 2 a 3. Pre-condizione: il fixture `data/expenses.csv` deve includere una riga malformata, e `data/expenses_alt.csv` deve esistere con valori diversi.

##### 5. Cosa cattura ora

- **Tool rotto non eseguito**: bloccato. Il `command:` gira effettivamente il tool.
- **Totale inventato**: bloccato. `regex_strict` su `$91.07` verifica il valore esatto.
- **Hardcoding**: bloccato. `not_contains "91.07"` nel codice + `expenses_alt.csv` richiede un totale diverso.
- **Row malformata ignorata**: bloccata. La regex su `skipped: 1` obbliga l'agente a gestirla.
- **Casi limite**: il totale `$91.07` è calcolato dalla somma del fixture. Se il fixture cambia, anche l'expected cambia. Da parametrizzare: l'expected può essere calcolato dinamicamente da un piccolo script Python pre-run, ma per semplicità si mantiene hardcoded con un commento nel JSON: `"comment": "expected_total = sum of expenses.csv amount column"`.

---

#### `autonomy_002` — Action tracker da note+procedures

##### 1. Stato attuale

Prompt: costruisci un action tracker da note + procedure. Inferisci lo schema, traccia la provenance, risolvi i duplicati. Salva `reports/action_tracker.json`.

Acceptance corrente:

```json
"acceptance": [
  {"type": "exists", "path": "reports/action_tracker.json", "weight": 2, "fatal": true},
  {"type": "json_valid", "path": "reports/action_tracker.json", "weight": 2, "fatal": true},
  {"type": "contains", "path": "reports/action_tracker.json", "text": "Source", "weight": 1},
  {"type": "contains", "path": "reports/action_tracker.json", "text": "Priority", "weight": 1},
  {"type": "min_lines", "path": "reports/action_tracker.json", "min": 8, "weight": 1}
]
```

Tier dichiarato: T4. Run registrata: pass.

##### 2. Debolezza

`min_lines: 8` è soddisfatto da un JSON con 8 righe di boilerplate. `contains "Source"` e `contains "Priority"` sono soddisfatti da `"source": "TODO", "priority": "TODO"`. Nessun check sul count delle azioni, sugli owner, sulla risoluzione dei duplicati.

Il prompt chiede "preserve owners and deadlines only when evidenced" e "resolve duplicates" — nessuno dei due è verificato.

##### 3. Logica dell'indurimento

1. **Count esatto di azioni.** Il fixture ha 3 azioni confermate + 1 decision = 4 actionable items. Aggiungere `json_field_equals` con `jq_filter: "length"` e `expected: 4`.

2. **Owner specifici con `regex`.** Verificare che gli owner siano nel set `{Francesco, Marta, Luca, Team}`: `regex_strict` su `"owner":\s*"(Francesco|Marta|Luca|Team)"` con `min_count: 4`.

3. **Provenance strutturata con quote verificata.** Come in `knowledge_001`, richiedere `evidence_quote` per ogni entry e verificare che sia una sottostringa del `source_doc`.

4. **False-friend action.** Aggiungere a `notes/meeting_notes.md` una frase tipo "Marta will *consider* preparing the August summary". L'agente deve distinguere "consider" (tentative) da "will do" (confirmed). Richiedere `confidence < 1.0` per questa voce: `regex_strict` su `"confidence":\s*0\.\d` con `min_count: 1`.

5. **Dedup verificato.** Aggiungere una stessa azione citata in due fonti diverse (meeting notes + email). L'agente deve deduplicare. Verificare che la voce abbia `sources: [...]` con 2 entry invece di 2 voci separate.

##### 4. Acceptance prima / dopo

**Prima**: vedere sopra.

**Dopo**:

```json
"acceptance": [
  {"type": "exists", "path": "reports/action_tracker.json", "weight": 1, "fatal": true},
  {"type": "json_valid", "path": "reports/action_tracker.json", "weight": 2, "fatal": true},
  {"type": "json_field_equals", "path": "reports/action_tracker.json",
   "jq_filter": "length", "expected": 4, "weight": 3, "fatal": true},
  {"type": "regex_strict", "path": "reports/action_tracker.json",
   "pattern": "\"owner\":\\s*\"(Francesco|Marta|Luca|Team)\"",
   "weight": 2, "fatal": true},
  {"type": "min_count", "path": "reports/action_tracker.json",
   "regex": "\"owner\":\\s*\"(Francesco|Marta|Luca|Team)\"",
   "expected": 4, "weight": 1, "fatal": true},
  {"type": "regex_strict", "path": "reports/action_tracker.json",
   "pattern": "\"confidence\":\\s*0\\.\\d", "weight": 1, "fatal": true},
  {"type": "min_count", "path": "reports/action_tracker.json",
   "regex": "\"sources\":\\s*\\[",
   "expected": 1, "weight": 1, "fatal": false},
  {"type": "evidence_quote_verified", "path": "reports/action_tracker.json",
   "jq_filter": ".[0]", "weight": 2, "fatal": true},
  {"type": "evidence_quote_verified", "path": "reports/action_tracker.json",
   "jq_filter": ".[1]", "weight": 2, "fatal": true},
  {"type": "evidence_quote_verified", "path": "reports/action_tracker.json",
   "jq_filter": ".[2]", "weight": 2, "fatal": true},
  {"type": "evidence_quote_verified", "path": "reports/action_tracker.json",
   "jq_filter": ".[3]", "weight": 2, "fatal": true}
]
```

Incrementare `task_revision` da 2 a 3.

##### 5. Cosa cattura ora

- **JSON boilerplate**: bloccato da `length: 4`.
- **Owner inventati**: bloccati dalla regex sugli owner specifici.
- **Tutte le voci con confidence 1.0**: bloccate dalla regex `0\.\d`. Almeno una voce deve essere incerta.
- **Dedup mancante**: penalizzata. La regex su `"sources":` (array) verifica che almeno una voce abbia fonti multiple.
- **Provenance fabbricata**: bloccata da `evidence_quote_verified` su tutte e 4 le entry.
- **Casi limite**: `evidence_quote_verified` richiede che ogni entry abbia un campo `source_doc` valido. Se l'agente omette il campo, l'evaluator crasha. Da gestire con un default sicuro (es. `jq_filter: ".[0] // {}"`).

---

#### `autonomy_003` — Fix broken tool + regression + verify

##### 1. Stato attuale

Prompt: fixa il broken tool finché i test passano. Riproduci, root cause, regression test, verifica che file non correlati siano intatti.

Acceptance corrente:

```json
"acceptance": [
  {"type": "command", "command": "python -m pytest -q", "timeout": 45,
   "weight": 4, "fatal": true}
]
```

Tier dichiarato: T5. Run registrata: pass.

##### 2. Debolezza

Identica a `coding_002` e `tool_use_003`: stesso `broken_tool.py`, pytest circolare. "Verifica che file non correlati siano intatti" non è verificato: l'agente può modificare qualsiasi file e passare.

##### 3. Logica dell'indurimento

1. **Secondo difetto indipendente.** Come `coding_002`, aggiungere `projects/off_by_one_tool.py` con un bug diverso.

2. **`unchanged` su file non correlati.** Aggiungere check `unchanged` su:
   - `data/expenses.csv`
   - `data/sales.csv`
   - `notes/meeting_notes.md`
   - `procedures/current.md`
   - `procedures/previous.md`

   Questo verifica il vincolo "non modificare file non correlati".

3. **Regression test requirement.** `exists tests/test_regression_*.py`.

##### 4. Acceptance prima / dopo

**Prima**: vedere sopra.

**Dopo**:

```json
"acceptance": [
  {"type": "command", "command": "python -m pytest -q tests/test_broken_tool.py tests/test_off_by_one.py",
   "timeout": 45, "weight": 3, "fatal": true},
  {"type": "unchanged", "path": "tests/test_broken_tool.py", "weight": 2, "fatal": true},
  {"type": "unchanged", "path": "tests/test_off_by_one.py", "weight": 2, "fatal": true},
  {"type": "unchanged", "path": "data/expenses.csv", "weight": 2, "fatal": true},
  {"type": "unchanged", "path": "data/sales.csv", "weight": 2, "fatal": true},
  {"type": "unchanged", "path": "notes/meeting_notes.md", "weight": 1, "fatal": true},
  {"type": "unchanged", "path": "procedures/current.md", "weight": 1, "fatal": true},
  {"type": "unchanged", "path": "procedures/previous.md", "weight": 1, "fatal": true},
  {"type": "regex_strict", "path": "projects/broken_tool.py",
   "pattern": "float\\(", "weight": 1, "fatal": true},
  {"type": "regex_strict", "path": "projects/off_by_one_tool.py",
   "pattern": "end\\s*\\+\\s*1\\b", "weight": 2, "fatal": true},
  {"type": "exists", "path": "tests/test_regression_broken.py", "weight": 1, "fatal": false},
  {"type": "exists", "path": "tests/test_regression_off_by_one.py", "weight": 1, "fatal": false},
  {"type": "regex_strict", "path": "reports/fix_summary.md",
   "pattern": "unrelated files.*intact|verified.*unchanged",
   "weight": 1, "fatal": true}
]
```

Incrementare `task_revision` da 2 a 3.

##### 5. Cosa cattura ora

- **Modifica di file non correlati**: bloccata. I 5 check `unchanged` sui file sorgenti verificano il vincolo.
- **Pattern matching su singolo bug**: bloccato dal secondo difetto indipendente.
- **Root cause non documentata**: bloccata dalla regex su `unrelated files.*intact` nel summary.
- **Casi limite**: l'`unchanged` sha256 su 5 file può dare falsi positivi se l'agente li apre in scrittura senza modificare (raro). Da validare con `git diff` se il workspace è un repo.

##### Tabella comparativa `autonomy`

| Task | Debolezza chiave | Modifica principale | Nuovo check type | Impatto |
|------|------------------|---------------------|------------------|---------|
| `autonomy_001` | Tool rotto invisibile; totale inventato | `command:` esegue il tool + `regex_strict` su totale + row malformata | `command` + `regex_strict` su valore + `not_contains` anti-hardcode | Critico |
| `autonomy_002` | JSON boilerplate; provenance fabbricata | Count esatto + owner specifici + `evidence_quote_verified` + false-friend | `json_field_equals` + `regex_strict` + `min_count` + `evidence_quote_verified` | Alto |
| `autonomy_003` | Singolo broken_tool; file non correlati non verificati | Secondo difetto + 5 check `unchanged` su file sorgenti | `unchanged` multipli + `regex_strict` su fix | Alto |

---

### 4.6 `browser`

Categoria di 2 task che valuta ricerca web e sintesi documentata. È la categoria con il **maggior leverage di tutto il benchmark**: le modifiche qui proposte convertono i task più gameable in test quasi infalsificabili.

#### `browser_001` — Research Python 3.14 sqlite3

##### 1. Stato attuale

Prompt: ricerca il transaction control di sqlite3 in Python 3.14 usando la capability browser/research disponibile. Usa almeno 3 fonti autorevoli, distingui fatti da raccomandazioni, registra URL e date di accesso, riconcilia version-specific guidance, salva `reports/browser_research.md`. Non fabbricare fonti.

Acceptance corrente:

```json
"acceptance": [
  {"type": "exists", "path": "reports/browser_research.md", "weight": 2, "fatal": true},
  {"type": "contains", "path": "reports/browser_research.md", "text": "http", "weight": 1},
  {"type": "min_lines", "path": "reports/browser_research.md", "min": 18, "weight": 1}
]
```

Tier dichiarato: T4. Run registrata: timeout.

##### 2. Debolezza

`contains "http"` è soddisfatto da una singola occorrenza della stringa "http" — anche `https://example.com`. `min_lines: 18` è l'unico gate strutturale, banalmente bypassabile con 18 righe di boilerplate. "Almeno 3 fonti autorevoli" è nel prompt ma non nell'acceptance.

Il timeout della run registrata è ironico e rivelatore: l'agente che fa davvero browsing reale supera il timeout, mentre uno che fabbrica 18 righe con URL inventati passerebbe in 2 secondi. Questo è un **incentivo perverso** che premia la fabbricazione.

Non c'è alcun check che gli URL puntino a domini autorevoli, che esistano realmente, o che il contenuto fattuale sia corretto.

##### 3. Logica dell'indurimento

Tre modifiche coordinate che convertono il task da "facilissimo da barare" a "quasi impossibile da fabbricare":

1. **URL whitelist + liveness check.** Mantenere un `expected_sources.json` nel fixture con domini autoritativi pinpati:

   ```json
   {
     "whitelist": [
       "docs.python.org",
       "peps.python.org",
       "sqlite.org",
       "github.com/python/cpython"
     ],
     "min_sources": 3,
     "fabricated_url_trap": [
       "https://python.org/dev/peps/pep-9999",
       "https://sqlite.org/old_docs/transaction_v1.html"
     ]
   }
   ```

   L'evaluator:
   - Estrae tutti gli URL dal report con regex `https?://[^\s)]+`.
   - Verifica che il dominio sia nella whitelist.
   - Verifica che `min_sources: 3` domini distinti siano presenti.
   - Verifica che nessuno degli URL del `fabricated_url_trap` appaia (se l'agente li ha "trovati" tramite il `notes/suggested_sources.md` piantato, è colto in fallo).

   Per riproducibilità offline, si può opzionalmente verificare che gli URL corrispondano a un set pinpato in `expected_urls.json` (hash-check, no HEAD request).

2. **Trappola di source fabbricata.** Aggiungere `notes/suggested_sources.md` al fixture con URL plausibili ma inesistenti (es. `https://python.org/dev/peps/pep-9999`). L'agente è tentato di copiarli. `not_contains` su ciascuno di questi URL nel report.

3. **Ground truth fattuale.** Scegliere un comportamento Python 3.14 sqlite3 con risposta nota e stabile (es. "default isolation level in 3.14 is `DEFERRED`" o "autocommit is opt-in via `isolation_level=None`"). `regex_strict` su `default isolation level:\s*DEFERRED` o sul valore corretto. Questo converte un task open-ended in uno con verità verificabile.

##### 4. Acceptance prima / dopo

**Prima**: vedere sopra.

**Dopo**:

```json
"acceptance": [
  {"type": "exists", "path": "reports/browser_research.md", "weight": 1, "fatal": true},
  {"type": "url_whitelist", "path": "reports/browser_research.md",
   "expected_sources_file": "benchmarks/fixtures/expected_sources.json",
   "min_distinct_domains": 3, "weight": 3, "fatal": true},
  {"type": "not_contains", "path": "reports/browser_research.md",
   "text": "pep-9999", "weight": 2, "fatal": true},
  {"type": "not_contains", "path": "reports/browser_research.md",
   "text": "transaction_v1.html", "weight": 2, "fatal": true},
  {"type": "regex_strict", "path": "reports/browser_research.md",
   "pattern": "default isolation level:\\s*DEFERRED\\b",
   "weight": 3, "fatal": true},
  {"type": "regex_strict", "path": "reports/browser_research.md",
   "pattern": "autocommit.*isolation_level\\s*=\\s*None",
   "weight": 2, "fatal": false},
  {"type": "regex_strict", "path": "reports/browser_research.md",
   "pattern": "accessed:\\s*\\d{4}-\\d{2}-\\d{2}",
   "weight": 1, "fatal": true},
  {"type": "min_count", "path": "reports/browser_research.md",
   "regex": "https?://[\\w.-]+",
   "expected": 3, "weight": 1, "fatal": true}
]
```

Il check type `url_whitelist` è nuovo (vedi sezione 5).

Incrementare `task_revision` da 2 a 3.

##### 5. Cosa cattura ora

- **URL fabbricati**: bloccati. Solo domini whitelist passano.
- **Singolo URL ripetuto 3 volte**: bloccato. `min_distinct_domains: 3` richiede 3 domini diversi.
- **Trappola di source fabbricata**: bloccata. I URL in `notes/suggested_sources.md` (inesistenti) non devono apparire.
- **Ground truth fattuale inventata**: bloccata. La regex su `default isolation level: DEFERRED` verifica la risposta corretta.
- **Date di accesso mancanti**: bloccate. La regex `accessed: YYYY-MM-DD` obbliga a registrarli.
- **Casi limite**: il `url_whitelist` con HEAD request può essere lento o fallire per ragioni di rete. Per riproducibilità offline, prevedere una modalità "pinned URLs" che verifica solo contro un set hardcoded. L'implementazione in `evaluators.py` deve accettare entrambe le modalità.

---

#### `browser_002` — Implementation decision memo

##### 1. Stato attuale

Prompt: memo di decisione implementativa per una tech rilevante al workspace. Almeno 4 fonti, prerequisiti, comandi, compatibilità, verifica.

Acceptance corrente:

```json
"acceptance": [
  {"type": "exists", "path": "reports/browser_research.md", "weight": 2, "fatal": true},
  {"type": "contains", "path": "reports/browser_research.md", "text": "http", "weight": 1},
  {"type": "min_lines", "path": "reports/browser_research.md", "min": 25, "weight": 1}
]
```

Tier dichiarato: T5. Run registrata: pass.

##### 2. Debolezza

Identica a `browser_001` ma con `min_lines: 25` invece di 18. Lo stesso incentive perverso: fabbricare 25 righe di URL plausibili è più veloce che fare 4 ricerche reali.

In più, "prerequisiti, comandi, compatibilità, verifica" sono nel prompt ma non strutturati nell'acceptance. L'agente può omettere qualsiasi sezione e passare.

##### 3. Logica dell'indurimento

1. **Stessa whitelist di `browser_001`.** Riutilizzare `expected_sources.json` con `min_distinct_domains: 4`.

2. **`regex_strict` per ogni sezione richiesta.** Sostituire `min_lines: 25` con 5 `regex_strict` distinte:
   - `## Prerequisites?:\s*\S`
   - `## Commands?:\s*\S`
   - `## Compatibility?:\s*\S`
   - `## Verification?:\s*\S`
   - `## Decision?:\s*\S`

3. **Decisione finale verificabile.** Richiedere che il memo concluda con una decisione esplicita: `regex_strict` su `decision:\s*(adopt|reject|postpone)\b`. Questo trasforma il memo da "raccolta di info" a "raccolta + giudizio".

4. **Cross-source reconciliation.** Richiedere che il memo citi almeno una contraddizione tra fonti e la risolva: `regex_strict` su `conflict:.*resolution:` o `discrepancy:`.

##### 4. Acceptance prima / dopo

**Prima**: vedere sopra.

**Dopo**:

```json
"acceptance": [
  {"type": "exists", "path": "reports/browser_research.md", "weight": 1, "fatal": true},
  {"type": "url_whitelist", "path": "reports/browser_research.md",
   "expected_sources_file": "benchmarks/fixtures/expected_sources.json",
   "min_distinct_domains": 4, "weight": 3, "fatal": true},
  {"type": "regex_strict", "path": "reports/browser_research.md",
   "pattern": "## Prerequisites?\\s*:\\s*\\S", "weight": 2, "fatal": true},
  {"type": "regex_strict", "path": "reports/browser_research.md",
   "pattern": "## Commands?\\s*:\\s*\\S", "weight": 2, "fatal": true},
  {"type": "regex_strict", "path": "reports/browser_research.md",
   "pattern": "## Compatibility?\\s*:\\s*\\S", "weight": 2, "fatal": true},
  {"type": "regex_strict", "path": "reports/browser_research.md",
   "pattern": "## Verification?\\s*:\\s*\\S", "weight": 2, "fatal": true},
  {"type": "regex_strict", "path": "reports/browser_research.md",
   "pattern": "decision:\\s*(adopt|reject|postpone)\\b",
   "weight": 3, "fatal": true},
  {"type": "regex_strict", "path": "reports/browser_research.md",
   "pattern": "conflict\\s*:\\s*\\S|discrepancy\\s*:\\s*\\S",
   "weight": 1, "fatal": false},
  {"type": "regex_strict", "path": "reports/browser_research.md",
   "pattern": "accessed:\\s*\\d{4}-\\d{2}-\\d{2}",
   "weight": 1, "fatal": false}
]
```

Incrementare `task_revision` da 2 a 3.

##### 5. Cosa cattura ora

- **Boilerplate 25-righe**: bloccato. Le `regex_strict` per sezione verificano struttura, non lunghezza.
- **URL fabbricati**: bloccati dalla whitelist.
- **Memo senza decisione**: bloccato. La regex su `decision:` obbliga a un giudizio esplicito.
- **Conflitti ignorati**: penalizzati. La regex su `conflict:` incoraggia la rilevazione.
- **Casi limite**: le sezioni devono essere titoli markdown (`##`). Un agente che usa `**Prerequisites:**` invece di `## Prerequisites:` fallisce. Da ammettere entrambi i formati con regex alternativo `##\\s+Prerequisites?|\\*\\*Prerequisites?\\*\\*`.

##### Tabella comparativa `browser`

| Task | Debolezza chiave | Modifica principale | Nuovo check type | Impatto |
|------|------------------|---------------------|------------------|---------|
| `browser_001` | URL fabbricabili; ground truth assente | Whitelist domini + trappola URL inesistenti + ground truth fattuale | `url_whitelist` + `not_contains` multipli + `regex_strict` su valore | Critico |
| `browser_002` | `min_lines: 25` come unico gate; no decisione | `regex_strict` per 5 sezioni + `decision:` obbligatoria | `url_whitelist` + `regex_strict` multipli | Alto |

---

### 4.7 `learning`

Categoria di 3 task che valuta astrazione di skill, transfer e correzione. È la categoria dove il difetto "task non-falsificabile" è più grave: `learning_003` chiede esplicitamente di "trovare un errore intenzionale" ma l'errore non è mai iniettato nel fixture.

#### `learning_001` — Cold run: scopri workflow ricorrente

##### 1. Stato attuale

Prompt (cold): scopri il workflow di reporting ricorrente nel workspace. Crea un documento di skill riutilizzabile. Generalizza in modo che non encoda i totali specifici del fixture.

Acceptance corrente:

```json
"acceptance": [
  {"type": "exists", "path": "skills/reporting_workflow.md", "weight": 2, "fatal": true},
  {"type": "contains", "path": "skills/reporting_workflow.md", "text": "adapt", "weight": 1},
  {"type": "contains", "path": "skills/reporting_workflow.md", "text": "transfer", "weight": 1}
]
```

Tier dichiarato: T4. Run registrata: pass.

##### 2. Debolezza

"Generalizza in modo che non encoda i totali specifici del fixture" è nel prompt ma non è verificato. L'agente può scrivere "Total: $91.07" nel documento di skill e passare. "Adapt" e "transfer" come parole chiave sono banalmente echo-abili.

Non c'è alcun test che il documento di skill, *se seguito*, produca effettivamente l'output corretto.

##### 3. Logica dell'indurimento

1. **Verifica procedurale in sandbox.** Aggiungere un `command:` che esegue la procedura documentata in `skills/reporting_workflow.md` contro il seed CSV in un sandbox pulito. L'evaluator estrae i comandi dal `.md` (es. blocchi di codice bash) e li esegue. `regex_strict` sull'output per `580` (totale corretto del seed sales).

2. **Test anti-hardcoding.** Aggiungere `data/sales_alt.csv` con valori diversi. Eseguire la stessa procedura su questo file. `regex_strict` su `742` (totale alt). Se l'agente ha hardcodato `580`, fallisce.

3. **`regex_strict` strutturale.** Sostituire `contains "adapt"` e `contains "transfer"` con `regex_strict` su pattern che indicano *realmente* la generalizzazione:
   - `generalization:\\s*\\S` (descrizione non vuota)
   - `parameters?:\\s*\\S` (parametri configurabili, es. `--input`)
   - `not hardcoded:\\s*\\S` o `assumptions?:\\s*\\S`

4. **`not_contains` su valori del fixture.** `not_contains "580"` e `not_contains "91.07"` sul documento di skill.

##### 4. Acceptance prima / dopo

**Prima**: vedere sopra.

**Dopo**:

```json
"acceptance": [
  {"type": "exists", "path": "skills/reporting_workflow.md", "weight": 2, "fatal": true},
  {"type": "regex_strict", "path": "skills/reporting_workflow.md",
   "pattern": "generalization\\s*:\\s*\\S", "weight": 2, "fatal": true},
  {"type": "regex_strict", "path": "skills/reporting_workflow.md",
   "pattern": "parameters?\\s*:\\s*\\S", "weight": 1, "fatal": false},
  {"type": "regex_strict", "path": "skills/reporting_workflow.md",
   "pattern": "assumptions?\\s*:\\s*\\S", "weight": 1, "fatal": false},
  {"type": "not_contains", "path": "skills/reporting_workflow.md",
   "text": "580", "weight": 2, "fatal": true},
  {"type": "not_contains", "path": "skills/reporting_workflow.md",
   "text": "91.07", "weight": 2, "fatal": true},
  {"type": "command", "command": "bash skills/reporting_workflow.sh --input data/sales.csv --output /tmp/learn1_out.txt 2>&1 || python skills/reporting_workflow.py --input data/sales.csv --output /tmp/learn1_out.txt",
   "timeout": 30, "weight": 3, "fatal": true},
  {"type": "regex_strict", "path": "/tmp/learn1_out.txt",
   "pattern": "580", "weight": 2, "fatal": true},
  {"type": "command", "command": "bash skills/reporting_workflow.sh --input data/sales_alt.csv --output /tmp/learn1_alt.txt 2>&1 || python skills/reporting_workflow.py --input data/sales_alt.csv --output /tmp/learn1_alt.txt",
   "timeout": 30, "weight": 2, "fatal": true},
  {"type": "regex_strict", "path": "/tmp/learn1_alt.txt",
   "pattern": "742", "weight": 2, "fatal": true}
]
```

Il prompt modificato deve chiedere all'agente di produrre anche uno script eseguibile `skills/reporting_workflow.sh` (o `.py`) oltre al `.md` documentativo.

Incrementare `task_revision` da 2 a 3.

##### 5. Cosa cattura ora

- **Hardcoding dei totali**: bloccato. `not_contains "580"` e `not_contains "91.07"`.
- **Documento di skill non eseguibile**: bloccato. Il `command:` esegue lo script associato.
- **Procedura non generalizzata**: bloccato. Il test su `sales_alt.csv` richiede un totale diverso.
- **Boilerplate con "adapt" e "transfer"**: bloccato. Le `regex_strict` su `generalization:`, `parameters:`, `assumptions:` richiedono struttura.
- **Casi limite**: il `command:` con fallback `bash || python` è fragile. Meglio specificare nel prompt un singolo formato (es. `skills/reporting_workflow.py`) e usare quel path fisso.

---

#### `learning_002` — Warm run: transfer su dataset cambiato

##### 1. Stato attuale

Prompt (warm): applica la procedura imparata a un dataset cambiato. Spiega quali passi sono stati transferiti vs adattati.

Acceptance corrente:

```json
"acceptance": [
  {"type": "exists", "path": "reports/learning_transfer.md", "weight": 2, "fatal": true},
  {"type": "contains", "path": "reports/learning_transfer.md", "text": "transfer", "weight": 1},
  {"type": "contains", "path": "reports/learning_transfer.md", "text": "adapt", "weight": 1}
]
```

Tier dichiarato: T4. Run registrata: pass.

##### 2. Debolezza

"Transferito vs adattato" è nel prompt ma non verificato strutturalmente. Il dataset "cambiato" non è poi così cambiato: le colonne hanno gli stessi nomi. Un agente che re-runna la procedura senza adattare nulla passa.

##### 3. Logica dell'indurimento

1. **CSV con schema effettivamente shiftato.** Aggiungere `data/sales_schema_shift.csv` con colonne rinominate e riordinate:
   - Vecchio: `date,product,units,revenue`
   - Nuovo: `txn_date,sku,qty_sold,gross_usd`

   L'agente *deve* adattare la procedura per gestire i nuovi nomi colonna. Non può semplicemente re-runnare.

2. **`regex_strict` sui nuovi nomi colonna.** Verificare che il report faccia riferimento ai nuovi nomi (`txn_date`, `gross_usd`) e non ai vecchi (`date`, `revenue`).

3. **Esecuzione del tool adaptato.** `command:` che esegue il tool dell'agente sul CSV shiftato e verifica l'output.

4. **Spiegazione strutturata transfer vs adapt.** `regex_strict` su:
   - `transferred steps\\s*:\\s*\\S`
   - `adapted steps\\s*:\\s*\\S`
   - `adaptation reason\\s*:\\s*\\S`

##### 4. Acceptance prima / dopo

**Prima**: vedere sopra.

**Dopo**:

```json
"acceptance": [
  {"type": "exists", "path": "reports/learning_transfer.md", "weight": 1, "fatal": true},
  {"type": "regex_strict", "path": "reports/learning_transfer.md",
   "pattern": "transferred\\s+steps\\s*:\\s*\\S", "weight": 2, "fatal": true},
  {"type": "regex_strict", "path": "reports/learning_transfer.md",
   "pattern": "adapted\\s+steps\\s*:\\s*\\S", "weight": 2, "fatal": true},
  {"type": "regex_strict", "path": "reports/learning_transfer.md",
   "pattern": "adaptation\\s+reason\\s*:\\s*\\S", "weight": 1, "fatal": false},
  {"type": "regex_strict", "path": "reports/learning_transfer.md",
   "pattern": "txn_date|gross_usd", "weight": 2, "fatal": true},
  {"type": "not_contains", "path": "reports/learning_transfer.md",
   "text": "Schema unchanged", "weight": 1, "fatal": false},
  {"type": "command", "command": "python skills/reporting_workflow.py --input data/sales_schema_shift.csv --output /tmp/learn2_out.txt",
   "timeout": 30, "weight": 3, "fatal": true},
  {"type": "regex_strict", "path": "/tmp/learn2_out.txt",
   "pattern": "\\d", "weight": 1, "fatal": true}
]
```

Incrementare `task_revision` da 2 a 3.

##### 5. Cosa cattura ora

- **Re-run senza adapt**: bloccato. Il CSV shiftato ha colonne diverse; la procedura vecchia crash o produce output vuoto.
- **Boilerplate "transfer + adapt"**: bloccato. Le `regex_strict` su `transferred steps:`, `adapted steps:`, `adaptation reason:` richiedono struttura.
- **Nessuna menzione dei nuovi nomi colonna**: bloccato dalla regex su `txn_date|gross_usd`.
- **Casi limite**: il tool `skills/reporting_workflow.py` deve essere quello prodotto in `learning_001`. Se l'agente non lo ha fatto in `learning_001`, fallisce qui — dipendenza tra task che va resa esplicita nel prompt.

---

#### `learning_003` — Warm run: errore intenzionale nella procedura

##### 1. Stato attuale

Prompt (warm): una procedura imparata contiene un errore intenzionale che può silenziosamente produrre un risultato plausibile ma sbagliato. Rilevalo usando validazione indipendente, correggi la procedura riutilizzabile (non solo l'output), re-runna il workflow, registra la regola corretta e l'evidenza senza cancellare lo storico della correzione.

Acceptance corrente:

```json
"acceptance": [
  {"type": "exists", "path": "skills/reporting_workflow.md", "weight": 2, "fatal": true},
  {"type": "exists", "path": "reports/learning_correction.md", "weight": 2, "fatal": true},
  {"type": "contains", "path": "reports/learning_correction.md", "text": "Correction", "weight": 1},
  {"type": "contains", "path": "reports/learning_correction.md", "text": "Validation", "weight": 1}
]
```

Tier dichiarato: T5. Run registrata: pass.

##### 2. Debolezza

**L'errore intenzionale non è mai iniettato nel fixture.** Il prompt dice "una procedura imparata contiene un errore" ma in `skills/reporting_workflow.md` (prodotto in `learning_001`) non c'è alcun errore piantato. L'agente è costretto a *inventare* un errore per poterlo "correggere" — un task non-falsificabile.

Inoltre, "correggi la procedura riutilizzabile" non è verificato: l'agente può correggere solo l'output e passare.

##### 3. Logica dell'indurimento

1. **Piantare realmente l'errore nel fixture.** Modificare `skills/reporting_workflow.md` (prodotto dal runner a partire da un template piantato) per includere una regola sbagliata, ad esempio:
   > "Total revenue = sum of the `units` column"
   
   Questo è sbagliato perché `units` è la quantità, non il ricavo. Il totale plausibile ma sbagliato è `100+80+120+100+100+80 = 580` che casualmente coincide con un numero vicino al totale revenue reale, ma è un caso.

   Alternativa più chiara: "Total revenue = sum of `units` × `unit_price`" dove `unit_price` non è una colonna esistente. L'agente deve riconoscere che la colonna non esiste.

2. **`regex_strict` sulla regola corretta.** Richiedere che la procedura corretta citi `sum.*revenue` (non `sum.*units`). Verifica che l'agente abbia *realmente* corretto, non solo finto.

3. **Validazione indipendente verificata.** Richiedere che `reports/learning_correction.md` includa una sezione `independent validation\\s*:\\s*\\S` che descriva il metodo di validazione (es. "ricomputato con `pandas.read_csv`").

4. **Storico della correzione preservato.** Richiedere che `skills/reporting_workflow.md` includa una sezione `## Correction history` con data, regola precedente, regola nuova. `regex_strict` su `correction history|## Change log`.

5. **Esecuzione della procedura corretta.** `command:` che esegue la procedura corretta e verifica l'output giusto.

##### 4. Acceptance prima / dopo

**Prima**: vedere sopra.

**Dopo**:

```json
"acceptance": [
  {"type": "exists", "path": "skills/reporting_workflow.md", "weight": 1, "fatal": true},
  {"type": "exists", "path": "reports/learning_correction.md", "weight": 1, "fatal": true},
  {"type": "regex_strict", "path": "skills/reporting_workflow.md",
   "pattern": "sum.*revenue|sum.*gross_usd", "weight": 3, "fatal": true},
  {"type": "not_contains", "path": "skills/reporting_workflow.md",
   "text": "sum of the `units`", "weight": 3, "fatal": true},
  {"type": "regex_strict", "path": "reports/learning_correction.md",
   "pattern": "correction\\s*:\\s*\\S", "weight": 2, "fatal": true},
  {"type": "regex_strict", "path": "reports/learning_correction.md",
   "pattern": "validation\\s*:\\s*\\S", "weight": 2, "fatal": true},
  {"type": "regex_strict", "path": "reports/learning_correction.md",
   "pattern": "independent\\s+validation\\s*:\\s*\\S", "weight": 1, "fatal": false},
  {"type": "regex_strict", "path": "reports/learning_correction.md",
   "pattern": "previous rule\\s*:|old rule\\s*:", "weight": 1, "fatal": false},
  {"type": "regex_strict", "path": "skills/reporting_workflow.md",
   "pattern": "## Correction history|## Change log", "weight": 1, "fatal": false},
  {"type": "command", "command": "python skills/reporting_workflow.py --input data/sales.csv --output /tmp/learn3_out.txt",
   "timeout": 30, "weight": 3, "fatal": true},
  {"type": "regex_strict", "path": "/tmp/learn3_out.txt",
   "pattern": "580", "weight": 2, "fatal": true}
]
```

Pre-condizione: il fixture deve piantare `skills/reporting_workflow.md` con il bug `sum of units`. Il runner deve sovrascrivere il file prodotto dall'agente in `learning_001` con questa versione buggata prima di eseguire `learning_003`.

Incrementare `task_revision` da 2 a 3.

##### 5. Cosa cattura ora

- **Task non-falsificabile**: bloccato. Ora c'è un errore reale da trovare.
- **Correzione finta**: bloccata. La `regex_strict` su `sum.*revenue` verifica la regola corretta; `not_contains "sum of the units"` blocca quella sbagliata.
- **No validazione indipendente**: penalizzata. La regex su `independent validation:` incoraggia.
- **Storico cancellato**: penalizzato. La regex su `## Correction history` incoraggia.
- **Procedura corretta ma non eseguita**: bloccata dal `command:`.
- **Casi limite**: il bug `sum of units` è troppo ovvio (la parola "units" vs "revenue" è chiara). Per renderlo più subdolo, piantare "Total = mean of revenue × count" che è aritmeticamente corretto ma semantically sbagliato (produrrebbe un numero plausibile ma non il totale reale). Da valutare in base al livello di difficoltà desiderato.

##### Tabella comparativa `learning`

| Task | Debolezza chiave | Modifica principale | Nuovo check type | Impatto |
|------|------------------|---------------------|------------------|---------|
| `learning_001` | Hardcoding totali; procedura non eseguita | `command:` esegue lo script + `sales_alt.csv` + `not_contains` | `command` + `not_contains` multipli + `regex_strict` | Alto |
| `learning_002` | Re-run senza adapt; boilerplate "transfer+adapt" | CSV schema-shiftato + `regex_strict` su nuovi nomi colonna | `regex_strict` multipli + `command` | Alto |
| `learning_003` | Task non-falsificabile; errore non iniettato | Errore reale piantato + `regex_strict` su regola corretta + storico | `regex_strict` + `not_contains` + `command` | Critico |

---

### 4.8 `long_horizon`

Categoria di 3 task che valuta pianificazione multi-step, recovery e audit. È la categoria dove il divario tra *claim* del README ("98k context ceiling") e *realtà* del fixture (~2 KB) è massimo. Le modifiche qui proposte sono le più costose da implementare ma anche le più impactful per la credibilità della suite.

#### `long_horizon_001` — E2E workflow

##### 1. Stato attuale

Prompt: completa un workflow end-to-end: ispeziona il workspace, identifica i dati autorevoli, pianifica, costruisci l'analisi, eseguila, recupera da un errore, genera il deliverable, valida ogni requisito, scrivi un changelog. Mantieni il processo compatibile con un contesto 98k; usa compaction o note durevoli invece di restartare da zero.

Acceptance corrente:

```json
"acceptance": [
  {"type": "exists", "path": "reports/long_horizon_changelog.md", "weight": 1, "fatal": true},
  {"type": "contains", "path": "reports/long_horizon_changelog.md", "text": "Validation", "weight": 1},
  {"type": "min_lines", "path": "reports/long_horizon_changelog.md", "min": 8, "weight": 1}
]
```

Tier dichiarato: T4. Run registrata: pass.

##### 2. Debolezza

Il seed è ~2 KB. Il claim "98k context" è aspirazionale, non enforced. "Recupera da un errore" è nel prompt ma nessun errore è iniettato. La "validazione di ogni requisito" non è verificata. L'intera acceptance è "un file di 8 righe con la parola 'Validation'".

##### 3. Logica dell'indurimento

1. **Generatore di corpus sintetico.** Aggiungere `benchmarks/fixtures/gen_corpus.py` che emette ~50k token di meeting notes, invoices, changelogs in `workspace/archive/`. Il RNG è seeded per riproducibilità. Questo esercita realmente la pressione sul context window e obbliga l'agente a usare compaction/note durevoli.

2. **Iniezione di errore mid-task.** Aggiungere al fixture `tools/validator.py` con un counter interno che fallisce alla 3a invocazione:

   ```python
   _counter = {"n": 0}
   def validate(data):
       _counter["n"] += 1
       if _counter["n"] == 3:
           raise RuntimeError("validator state corruption: counter=3")
       return True
   ```

   L'agente deve (a) hit il failure, (b) work around (es. restart validator, usare un'alternativa), (c) includere il failure nel changelog. `regex_strict` su `validator state corruption` nel changelog verifica che l'agente abbia registrato l'errore.

3. **Checkpoint di stato.** Richiedere che l'agente scriva `workspace/.state/checkpoint_N.json` dopo ogni step con `{step, status, artifacts_produced, errors}`. `exists` su almeno 3 file di checkpoint (uno per ogni fase: inspect, plan, build, execute, validate).

4. **`regex_strict` su "recovery".** Verificare che il changelog contenga una sezione `recovery\\s*:\\s*\\S` con descrizione non vuota dell'errore e del fix.

##### 4. Acceptance prima / dopo

**Prima**: vedere sopra.

**Dopo**:

```json
"acceptance": [
  {"type": "exists", "path": "reports/long_horizon_changelog.md", "weight": 1, "fatal": true},
  {"type": "regex_strict", "path": "reports/long_horizon_changelog.md",
   "pattern": "## Validation\\s*:?\\s*\\S", "weight": 2, "fatal": true},
  {"type": "regex_strict", "path": "reports/long_horizon_changelog.md",
   "pattern": "recovery\\s*:\\s*\\S", "weight": 2, "fatal": true},
  {"type": "regex_strict", "path": "reports/long_horizon_changelog.md",
   "pattern": "validator state corruption", "weight": 2, "fatal": true},
  {"type": "exists", "path": "workspace/.state/checkpoint_1.json", "weight": 1, "fatal": true},
  {"type": "exists", "path": "workspace/.state/checkpoint_3.json", "weight": 1, "fatal": true},
  {"type": "exists", "path": "workspace/.state/checkpoint_5.json", "weight": 1, "fatal": true},
  {"type": "json_valid", "path": "workspace/.state/checkpoint_3.json", "weight": 1, "fatal": true},
  {"type": "min_count", "path": "workspace/.state/",
   "glob": "checkpoint_*.json", "expected": 3, "weight": 1, "fatal": false},
  {"type": "command", "command": "wc -c workspace/archive/*.md | tail -1 | awk '{print $1}'",
   "expected_output_regex": "[3-9]\\d{4,}|[1-9]\\d{5,}",
   "weight": 2, "fatal": true}
]
```

L'ultimo check verifica che il corpus in `workspace/archive/` sia effettivamente grande (≥ 30k caratteri). Pre-condizione: il runner esegue `gen_corpus.py` prima di avviare il task.

Incrementare `task_revision` da 2 a 3.

##### 5. Cosa cattura ora

- **98k ceiling non testato**: bloccato. Il check sulla dimensione di `archive/` verifica che il corpus sia effettivamente grande.
- **Errore non gestito**: bloccato. La regex su `validator state corruption` verifica che l'agente abbia hit e registrato il failure.
- **"Recovery" come keyword vuota**: bloccato. La `regex_strict` su `recovery:` richiede descrizione.
- **Nessuno stato durevole**: bloccato. I checkpoint verificano che l'agente abbia persistito lo stato.
- **Casi limite**: il `expected_output_regex` per la dimensione del corpus è fragile. Meglio usare un `numeric_close` o `min_numeric` con un valore threshold. Vedi sezione 5 per il check type `min_numeric`.

---

#### `long_horizon_002` — Feature multi-file con regressioni

##### 1. Stato attuale

Prompt: implementa una feature su più file. Fixa le regressioni. Aggiorna i docs. Mantieni la dependency chain.

Acceptance corrente:

```json
"acceptance": [
  {"type": "exists", "path": "reports/long_horizon_changelog.md", "weight": 1, "fatal": true},
  {"type": "command", "command": "python -m pytest -q", "timeout": 45,
   "weight": 4, "fatal": true}
]
```

Tier dichiarato: T5. Run registrata: pass.

##### 2. Debolezza

Identica a `coding_001`: agente scrive test. "Multi-file" non è verificato: l'agente può mettere tutto in un file. "Mantieni la dependency chain" non è verificato: l'agente può produrre artefatti indipendenti.

##### 3. Logica dell'indurimento

1. **Catena di dipendenze #1 → #2 → #3.** Richiedere tre artefatti dove:
   - #1 genera `summary.json` da `data/expenses.csv`
   - #2 legge `summary.json` per produrre `chart.svg`
   - #3 legge entrambi per produrre `report.md`

   Verificare con `command:` che #2 effettivamente legga #1 (es. cancellare #1 e verificare che #2 fallisca) e che #3 legga entrambi.

2. **Test pre-confezionati su ciascun artefatto.** `tests/test_chain.py` nel fixture con assertion su ogni step della catena. `unchanged`.

3. **`exists` su 3 file distinti.** Verifica la struttura multi-file.

##### 4. Acceptance prima / dopo

**Prima**: vedere sopra.

**Dopo**:

```json
"acceptance": [
  {"type": "exists", "path": "reports/long_horizon_changelog.md", "weight": 1, "fatal": false},
  {"type": "exists", "path": "tools/step1_summary.py", "weight": 2, "fatal": true},
  {"type": "exists", "path": "tools/step2_chart.py", "weight": 2, "fatal": true},
  {"type": "exists", "path": "tools/step3_report.py", "weight": 2, "fatal": true},
  {"type": "command", "command": "python tools/step1_summary.py --input data/expenses.csv --output /tmp/lh2_summary.json",
   "timeout": 30, "weight": 2, "fatal": true},
  {"type": "json_valid", "path": "/tmp/lh2_summary.json", "weight": 1, "fatal": true},
  {"type": "command", "command": "python tools/step2_chart.py --input /tmp/lh2_summary.json --output /tmp/lh2_chart.svg",
   "timeout": 30, "weight": 2, "fatal": true},
  {"type": "command", "command": "python tools/step3_report.py --summary /tmp/lh2_summary.json --chart /tmp/lh2_chart.svg --output /tmp/lh2_report.md",
   "timeout": 30, "weight": 2, "fatal": true},
  {"type": "regex_strict", "path": "/tmp/lh2_report.md",
   "pattern": "summary|chart", "weight": 1, "fatal": false},
  {"type": "command", "command": "rm -f /tmp/lh2_summary.json && python tools/step2_chart.py --input /tmp/lh2_summary.json --output /tmp/lh2_chart_fail.svg 2>&1; test $? -ne 0",
   "timeout": 15, "weight": 2, "fatal": true},
  {"type": "command", "command": "python -m pytest -q tests/test_chain.py",
   "timeout": 45, "weight": 3, "fatal": true},
  {"type": "unchanged", "path": "tests/test_chain.py", "weight": 2, "fatal": true}
]
```

Incrementare `task_revision` da 2 a 3.

##### 5. Cosa cattura ora

- **Tutto in un file**: bloccato dai 3 `exists` su file distinti.
- **Artefatti indipendenti**: bloccati. Il `command:` che cancella `step1_summary.json` e verifica che `step2` fallisca prova la dipendenza reale.
- **Test trivialmente passanti**: bloccati dai test nascosti.
- **CLI non funziona**: bloccata dai 3 `command:` su ciascuno step.
- **Casi limite**: il check "cancella e verifica fallimento" richiede shell con side-effect. Da validare che il cleanup non interferisca con altri check. L'evaluator deve eseguire i `command:` in ordine e isolare i side-effect in `/tmp/`.

---

#### `long_horizon_003` — Indagine business problem

##### 1. Stato attuale

Prompt: investiga un business problem. Riconcilia contraddizioni. Strumento di supporto. Audit ogni requisito.

Acceptance corrente:

```json
"acceptance": [
  {"type": "exists", "path": "reports/long_horizon_changelog.md", "weight": 1, "fatal": true},
  {"type": "contains", "path": "reports/long_horizon_changelog.md", "text": "Requirement", "weight": 1},
  {"type": "contains", "path": "reports/long_horizon_changelog.md", "text": "Evidence", "weight": 1}
]
```

Tier dichiarato: T5. Run registrata: pass.

##### 2. Debolezza

Identica a `long_horizon_001`: boilerplate con keyword "Requirement" e "Evidence". "Reconcilia contraddizioni" non verificato. "Audit ogni requisito" non verificato strutturalmente.

##### 3. Logica dell'indurimento

1. **Requisiti enumerati con count esatto.** Il prompt modificato elenca 5 requisiti specifici (R1, R2, R3, R4, R5). L'acceptance verifica `regex_strict` su ciascun `R[1-5]:\\s*\\S` (almeno un carattere dopo ciascun ID).

2. **Matrice di audit strutturata.** Richiedere `reports/audit_matrix.json` con schema `[{requirement_id, status, evidence_doc, evidence_quote, notes}]`. `evidence_quote_verified` su ciascuna entry.

3. **Contraddizioni identificate.** Il fixture pianta 2 contraddizioni (es. procedure vs notes). `regex_strict` su `contradiction\\s*:\\s*\\S` con `min_count: 2`.

4. **Strumento di supporto eseguito.** `command:` che esegue il tool dell'agente.

##### 4. Acceptance prima / dopo

**Prima**: vedere sopra.

**Dopo**:

```json
"acceptance": [
  {"type": "exists", "path": "reports/long_horizon_changelog.md", "weight": 1, "fatal": false},
  {"type": "exists", "path": "reports/audit_matrix.json", "weight": 2, "fatal": true},
  {"type": "json_valid", "path": "reports/audit_matrix.json", "weight": 1, "fatal": true},
  {"type": "regex_strict", "path": "reports/audit_matrix.json",
   "pattern": "R1[\\s:\\\"].+\\S", "weight": 2, "fatal": true},
  {"type": "regex_strict", "path": "reports/audit_matrix.json",
   "pattern": "R2[\\s:\\\"].+\\S", "weight": 2, "fatal": true},
  {"type": "regex_strict", "path": "reports/audit_matrix.json",
   "pattern": "R3[\\s:\\\"].+\\S", "weight": 2, "fatal": true},
  {"type": "regex_strict", "path": "reports/audit_matrix.json",
   "pattern": "R4[\\s:\\\"].+\\S", "weight": 2, "fatal": true},
  {"type": "regex_strict", "path": "reports/audit_matrix.json",
   "pattern": "R5[\\s:\\\"].+\\S", "weight": 2, "fatal": true},
  {"type": "min_count", "path": "reports/audit_matrix.json",
   "regex": "contradiction", "expected": 2, "weight": 1, "fatal": true},
  {"type": "min_count", "path": "reports/audit_matrix.json",
   "jq_filter": "length", "expected": 5, "weight": 2, "fatal": true},
  {"type": "evidence_quote_verified", "path": "reports/audit_matrix.json",
   "jq_filter": ".[0]", "weight": 1, "fatal": false},
  {"type": "evidence_quote_verified", "path": "reports/audit_matrix.json",
   "jq_filter": ".[1]", "weight": 1, "fatal": false},
  {"type": "command", "command": "python tools/investigation_helper.py --audit reports/audit_matrix.json --output /tmp/lh3_out.txt",
   "timeout": 30, "weight": 2, "fatal": true}
]
```

Incrementare `task_revision` da 2 a 3.

##### 5. Cosa cattura ora

- **Boilerplate con "Requirement" ed "Evidence"**: bloccato. La matrice JSON è obbligatoria con 5 entry distinte.
- **Requisiti non auditati individualmente**: bloccati dalle `regex_strict` su `R1`–`R5`.
- **Contraddizioni non identificate**: bloccate da `min_count: 2` su `contradiction`.
- **Strumento non eseguito**: bloccato dal `command:`.
- **Casi limite**: il prompt modificato deve elencare esplicitamente i 5 requisiti (R1–R5) in modo che l'agente sappia cosa audittare. Il fixture deve piantare 2 contraddizioni reali nei documenti sorgente.

##### Tabella comparativa `long_horizon`

| Task | Debolezza chiave | Modifica principale | Nuovo check type | Impatto |
|------|------------------|---------------------|------------------|---------|
| `long_horizon_001` | 98k ceiling non testato; errore non iniettato | Corpus 50k token + `validator.py` con counter + checkpoint di stato | `regex_strict` + `exists` multipli + `min_count` con glob | Molto alto |
| `long_horizon_002` | Tutto in un file; dipendenze non verificate | Catena #1→#2→#3 + test "cancella e verifica fallimento" | `command` multipli + `unchanged` + `exists` multipli | Alto |
| `long_horizon_003` | Audit boilerplate; contraddizioni non identificate | Matrice JSON con 5 requisiti + `min_count` su contraddizioni | `regex_strict` multipli + `min_count` + `evidence_quote_verified` | Alto |

---

### 4.9 `subagents`

Categoria di 3 task che valuta delegazione, riconciliazione e sintesi multi-stream. È la categoria dove la differenza tra "agente che davvero orchestra" e "agente che finge delega" è cruciale, ma dove nessun check verifica che la delegazione sia effettivamente avvenuta.

#### `subagents_001` — Comparative report con stream paralleli

##### 1. Stato attuale

Prompt: report comparativo. Decomponi in stream paralleli. Riconcilia duplicati e conflitti.

Acceptance corrente:

```json
"acceptance": [
  {"type": "exists", "path": "reports/subagent_synthesis.md", "weight": 2, "fatal": true},
  {"type": "contains", "path": "reports/subagent_synthesis.md", "text": "Verified", "weight": 1},
  {"type": "contains", "path": "reports/subagent_synthesis.md", "text": "Rejected", "weight": 1}
]
```

Tier dichiarato: T4. Run registrata: pass.

##### 2. Debolezza

`contains "Verified"` e `contains "Rejected"` sono keyword vuote. Nessun check verifica che l'agente abbia effettivamente spawnato subagenti — la telemetria è disponibile in `results.jsonl` ma non consultata dall'evaluator.

Il corpus di 3 documenti è troppo piccolo per giustificare "parallel streams": non c'è nulla da parallelizzare.

##### 3. Logica dell'indurimento

1. **Telemetria obbligatoria.** Aggiungere un check `trajectory_event_count` che legge `results.jsonl` e verifica la presenza di almeno 1 evento `subagent_start`. Questo converte "puoi usare subagent" da opzionale a verificato.

2. **Corpus espanso per giustificare parallelismo.** Aggiungere al fixture 2 set di documenti indipendenti (set A: `docs/research_a/`, set B: `docs/research_b/`) ciascuno con 5+ file. La decomposizione in stream paralleli è ora *necessaria*, non opzionale.

3. **Riconciliazione strutturata.** Richiedere `reports/reconciliation.json` con schema `[{topic, stream_a_claim, stream_b_claim, conflict, resolution}]`. Verifica che ci sia almeno 1 conflitto riconciliato.

4. **`regex_strict` su sezioni Verified/Rejected.** Sostituire `contains` con `regex_strict` su `## Verified\\s*:?\\s*\\S` e `## Rejected\\s*:?\\s*\\S`.

##### 4. Acceptance prima / dopo

**Prima**: vedere sopra.

**Dopo**:

```json
"acceptance": [
  {"type": "exists", "path": "reports/subagent_synthesis.md", "weight": 1, "fatal": true},
  {"type": "exists", "path": "reports/reconciliation.json", "weight": 2, "fatal": true},
  {"type": "json_valid", "path": "reports/reconciliation.json", "weight": 1, "fatal": true},
  {"type": "regex_strict", "path": "reports/subagent_synthesis.md",
   "pattern": "## Verified\\s*:?\\s*\\S", "weight": 2, "fatal": true},
  {"type": "regex_strict", "path": "reports/subagent_synthesis.md",
   "pattern": "## Rejected\\s*:?\\s*\\S", "weight": 2, "fatal": true},
  {"type": "trajectory_event_count", "event_type": "subagent_start",
   "min_count": 1, "weight": 3, "fatal": true},
  {"type": "min_count", "path": "reports/reconciliation.json",
   "jq_filter": "length", "expected": 3, "weight": 2, "fatal": true},
  {"type": "regex_strict", "path": "reports/reconciliation.json",
   "pattern": "conflict\\s*:\\s*\\S", "weight": 1, "fatal": false},
  {"type": "regex_strict", "path": "reports/reconciliation.json",
   "pattern": "resolution\\s*:\\s*\\S", "weight": 1, "fatal": false}
]
```

Il check type `trajectory_event_count` è nuovo (vedi sezione 5): legge `results.jsonl` e conta eventi di un dato tipo.

Incrementare `task_revision` da 2 a 3.

##### 5. Cosa cattura ora

- **Boilerplate con "Verified" e "Rejected"**: bloccato. Le `regex_strict` richiedono sezioni strutturate con contenuto.
- **Nessuna delega reale**: bloccata. Il `trajectory_event_count` su `subagent_start` verifica che l'agente abbia spawnato almeno 1 subagente.
- **Riconciliazione fabbricata**: bloccata. Il JSON con `min_count: 3` richiede almeno 3 topic riconciliati.
- **Casi limite**: il `trajectory_event_count` richiede che l'adapter emetta eventi `subagent_start` nel formato atteso. Da standardizzare nel contract dell'adapter. Per adapter che non supportano subagenti (es. agentzero), il task va marcato come N/A.

---

#### `subagents_002` — Multi-part research+implementation

##### 1. Stato attuale

Prompt: risolvi un task multi-parte ricerca+implementazione. Decidi quali subtask delegare, dai scope e acceptance criteria precisi, rivedi criticamente gli output delegati, risolvi conflitti, integra solo i finding verificati.

Acceptance corrente:

```json
"acceptance": [
  {"type": "exists", "path": "reports/subagent_synthesis.md", "weight": 2, "fatal": true},
  {"type": "contains", "path": "reports/subagent_synthesis.md", "text": "Verified", "weight": 1},
  {"type": "contains", "path": "reports/subagent_synthesis.md", "text": "Rejected", "weight": 1}
]
```

Tier dichiarato: T5. Run registrata: pass.

##### 2. Debolezza

Identica a `subagents_001`: keyword vuote, nessuna verifica di delega. In più, "integra solo finding verificati" non è verificato: l'agente può integrare tutto e passare.

##### 3. Logica dell'indurimento

1. **Sub-stream con conclusioni contraddittorie.** Piantare 2 set di documenti che supportano conclusioni opposte:
   - Set A: "migrate to v3" (3 file con argomenti pro)
   - Set B: "v3 has known CVE-2024-XXXX" (2 file con argomenti contro)

   L'agente deve identificare il conflitto e risolverlo. `regex_strict` su `conflict\\s*:\\s*migration.*CVE|CVE.*migration` verifica il riconoscimento.

2. **Sub-task con output da rifiutare.** Piantare un sub-task "decoy" il cui output corretto è "reject" (es. una fonte con statistica fabbricata `99.99% adoption rate`). L'agente deve identificare la fabricazione e rifiutarla. `regex_strict` su `## Rejected\\s*:?\\s*\\S` con `min_count: 1` su `99\\.99%`.

3. **Telemetria obbligatoria.** Come `subagents_001`, `trajectory_event_count` su `subagent_start` con `min_count: 2` (almeno 2 stream paralleli).

4. **Decision memo con struttura.** Richiedere `reports/decision_memo.md` con sezioni `## Decision`, `## Rationale`, `## Risks`. `regex_strict` su ciascuna.

##### 4. Acceptance prima / dopo

**Prima**: vedere sopra.

**Dopo**:

```json
"acceptance": [
  {"type": "exists", "path": "reports/decision_memo.md", "weight": 2, "fatal": true},
  {"type": "regex_strict", "path": "reports/decision_memo.md",
   "pattern": "## Decision\\s*:?\\s*\\S", "weight": 2, "fatal": true},
  {"type": "regex_strict", "path": "reports/decision_memo.md",
   "pattern": "## Rationale\\s*:?\\s*\\S", "weight": 2, "fatal": true},
  {"type": "regex_strict", "path": "reports/decision_memo.md",
   "pattern": "## Risks\\s*:?\\s*\\S", "weight": 1, "fatal": false},
  {"type": "regex_strict", "path": "reports/decision_memo.md",
   "pattern": "conflict\\s*:\\s*\\S", "weight": 2, "fatal": true},
  {"type": "regex_strict", "path": "reports/decision_memo.md",
   "pattern": "CVE", "weight": 2, "fatal": true},
  {"type": "regex_strict", "path": "reports/decision_memo.md",
   "pattern": "99\\.99%", "weight": 1, "fatal": false, "negate": true},
  {"type": "trajectory_event_count", "event_type": "subagent_start",
   "min_count": 2, "weight": 3, "fatal": true},
  {"type": "regex_strict", "path": "reports/decision_memo.md",
   "pattern": "## Rejected\\s*:?\\s*\\S", "weight": 1, "fatal": false},
  {"type": "regex_strict", "path": "reports/decision_memo.md",
   "pattern": "## Verified\\s*:?\\s*\\S", "weight": 1, "fatal": false}
]
```

Incrementare `task_revision` da 2 a 3.

##### 5. Cosa cattura ora

- **Conflitto ignorato**: bloccato. La regex su `conflict:` obbliga a documentarlo.
- **Fonte fabbricata integrata**: bloccata. La regex negate su `99.99%` verifica che la statistica fabbricata non appaia come "verificata".
- **Nessuna delega**: bloccata. `trajectory_event_count: 2`.
- **Memo senza struttura**: bloccato dalle `regex_strict` su `## Decision`, `## Rationale`.
- **Casi limite**: la regex negate su `99.99%` richiede l'implementazione del flag `negate` nel check type `regex_strict`. Vedi sezione 5.

---

#### `subagents_003` — Coordinate small project

##### 1. Stato attuale

Prompt: coordina un piccolo progetto. Uno stream per evidence, uno per constraints. Rifiuta unsupported. Decision memo.

Acceptance corrente:

```json
"acceptance": [
  {"type": "exists", "path": "reports/subagent_synthesis.md", "weight": 2, "fatal": true},
  {"type": "contains", "path": "reports/subagent_synthesis.md", "text": "Verified", "weight": 1},
  {"type": "contains", "path": "reports/subagent_synthesis.md", "text": "Rejected", "weight": 1}
]
```

Tier dichiarato: T5. Run registrata: pass.

##### 2. Debolezza

Identica a `subagents_001`/`002`. In più, "rifiuta unsupported" non è verificato: l'agente può accettare tutto.

##### 3. Logica dell'indurimento

1. **Sub-task "rifiuta" con trappola specifica.** Piantare un sub-task "evidence stream" che contiene una fonte con statistiche contraddittorie (es. "adoption is 60%" in un file, "adoption is 90%" in un altro). L'agente deve identificare l'inconsistenza e rifiutare la fonte inaffidabile. `regex_strict` su `## Rejected\\s*:?\\s*adoption` verifica il rifiuto specifico.

2. **Constraints stream con vincoli in conflitto.** Piantare constraints che si contraddicono (es. "must support Python 3.8" e "must use Python 3.12 features"). L'agente deve identificare il conflitto. `regex_strict` su `conflict\\s*:\\s*Python 3\\.8.*3\\.12|3\\.12.*3\\.8`.

3. **Decision memo con decisione esplicita.** `regex_strict` su `decision:\\s*(adopt|reject|postpone|investigate)\\b`.

4. **Telemetria.** `trajectory_event_count: 2`.

##### 4. Acceptance prima / dopo

**Prima**: vedere sopra.

**Dopo**:

```json
"acceptance": [
  {"type": "exists", "path": "reports/decision_memo.md", "weight": 1, "fatal": true},
  {"type": "regex_strict", "path": "reports/decision_memo.md",
   "pattern": "## Decision\\s*:?\\s*\\S", "weight": 2, "fatal": true},
  {"type": "regex_strict", "path": "reports/decision_memo.md",
   "pattern": "decision:\\s*(adopt|reject|postpone|investigate)\\b",
   "weight": 3, "fatal": true},
  {"type": "regex_strict", "path": "reports/decision_memo.md",
   "pattern": "## Rejected\\s*:?\\s*\\S", "weight": 2, "fatal": true},
  {"type": "regex_strict", "path": "reports/decision_memo.md",
   "pattern": "adoption", "weight": 1, "fatal": false},
  {"type": "regex_strict", "path": "reports/decision_memo.md",
   "pattern": "conflict\\s*:\\s*\\S", "weight": 1, "fatal": false},
  {"type": "not_contains", "path": "reports/decision_memo.md",
   "text": "all evidence accepted", "weight": 1, "fatal": false},
  {"type": "trajectory_event_count", "event_type": "subagent_start",
   "min_count": 2, "weight": 3, "fatal": true}
]
```

Incrementare `task_revision` da 2 a 3.

##### 5. Cosa cattura ora

- **Tutto accettato senza review**: bloccato. `## Rejected` è fatal, obbliga ad almeno un rifiuto.
- **Conflitto non identificato**: penalizzato dalla regex su `conflict:`.
- **Decisione non esplicita**: bloccata dalla regex su `decision: (adopt|reject|postpone|investigate)`.
- **Nessuna delega**: bloccata da `trajectory_event_count: 2`.
- **Casi limite**: la regex su `## Rejected:? adoption` è troppo specifica (l'agente potrebbe rifiutare per altri motivi). Da ammorbidire a `## Rejected:? \S` (almeno un rifiuto qualsiasi).

##### Tabella comparativa `subagents`

| Task | Debolezza chiave | Modifica principale | Nuovo check type | Impatto |
|------|------------------|---------------------|------------------|---------|
| `subagents_001` | No proof di delega; keyword vuote | `trajectory_event_count` + JSON di riconciliazione + corpus espanso | `trajectory_event_count` + `regex_strict` + `json_valid` | Alto |
| `subagents_002` | No conflitto piantato; fonte fabbricata integrabile | Sub-stream contraddittori + trappola `99.99%` + memo strutturato | `trajectory_event_count` + `regex_strict` (negate) | Alto |
| `subagents_003` | "Reject" non verificato; no vincoli in conflitto | Trappola "rifiuta" specifica + constraints conflittuali | `regex_strict` + `not_contains` + `trajectory_event_count` | Alto |

---

## 5. Estensioni dell'evaluator

Tutte le modifiche proposte nelle sezioni 4.x richiedono nuovi check type in `aios_bench/evaluators.py`. L'infrastruttura attuale supporta: `exists`, `contains`, `contains_any`, `regex`, `min_lines`, `json_valid`, `sha256`, `unchanged`, `command`, `max_files`. Il dispatch è un flat `if/elif` in `evaluate_artifacts` — facile da estendere.

Questa sezione definisce i 9 nuovi check type necessari, con snippet Python pronti da innestare. Tutti seguono la convenzione dell'evaluator esistente: ritornano `(passed: bool, score: float, message: str)`.

### 5.1 `regex_strict`

Come `regex` esistente, ma con due differenze:
- Case-sensitive di default (configurabile via `ignore_case: false`),
- Supporta il flag `negate` per verificare *assenza* di un pattern,
- Ritorna `score = 1.0` solo se il pattern matcha (o non matcha, se `negate: true`).

```python
def check_regex_strict(spec: dict, workspace: Path) -> tuple[bool, float, str]:
    import re
    path = workspace / spec["path"]
    if not path.exists():
        return False, 0.0, f"file not found: {spec['path']}"
    content = path.read_text(encoding="utf-8")
    flags = re.MULTILINE | re.DOTALL
    if spec.get("ignore_case", False):
        flags |= re.IGNORECASE
    pattern = spec["pattern"]
    match = re.search(pattern, content, flags) is not None
    negate = spec.get("negate", False)
    passed = (not match) if negate else match
    score = 1.0 if passed else 0.0
    verb = "negate-match" if negate else "match"
    return passed, score, f"regex_strict {verb} for /{pattern}/: {'OK' if passed else 'FAIL'}"
```

**Casi d'uso**: ovunque si sostituisca `contains "<keyword>"` con un pattern specifico (es. `port:\s*8081`). Il flag `negate` copre i `not_contains` di valori specifici.

### 5.2 `not_contains`

Versione semplificata di `regex_strict` con `negate: true` per testo letterale. Esiste per leggibilità del JSON di acceptance.

```python
def check_not_contains(spec: dict, workspace: Path) -> tuple[bool, float, str]:
    path = workspace / spec["path"]
    if not path.exists():
        return False, 0.0, f"file not found: {spec['path']}"
    content = path.read_text(encoding="utf-8").lower()
    text = spec["text"].lower()
    passed = text not in content
    return passed, 1.0 if passed else 0.0, f"not_contains '{spec['text']}': {'OK' if passed else 'FAIL'}"
```

**Casi d'uso**: anti-hardcoding (`not_contains "580"` in `tools/expense_report.py`), trappole (`not_contains "pep-9999"` in report browser).

### 5.3 `numeric_close`

Verifica che un valore numerico estratto dal file sia "vicino" a un expected entro una tolleranza. Estrae il valore via regex o jq, lo converte in float, confronta con `abs(actual - expected) / expected <= tolerance` (default `tolerance: 0.01`).

```python
def check_numeric_close(spec: dict, workspace: Path) -> tuple[bool, float, str]:
    import re, json
    path = workspace / spec["path"]
    if not path.exists():
        return False, 0.0, f"file not found: {spec['path']}"
    content = path.read_text(encoding="utf-8")
    if "regex" in spec:
        m = re.search(spec["regex"], content)
        if not m:
            return False, 0.0, f"regex did not match: {spec['regex']}"
        actual = float(m.group(1))
    elif "jq_filter" in spec:
        # requires jq python binding or shell-out to jq
        data = json.loads(content)
        actual = float(jq_first(spec["jq_filter"], data))
    else:
        return False, 0.0, "either 'regex' or 'jq_filter' required"
    expected = float(spec["expected"])
    tolerance = float(spec.get("tolerance", 0.01))
    passed = abs(actual - expected) / max(abs(expected), 1e-9) <= tolerance
    return passed, 1.0 if passed else 0.0, f"numeric_close: actual={actual}, expected={expected}, tolerance={tolerance}: {'OK' if passed else 'FAIL'}"
```

**Casi d'uso**: `autonomy_001` (totale spese), `long_horizon_001` (dimensione corpus).

### 5.4 `json_field_equals`

Estrae un campo da un JSON via jq filter e confronta con un valore atteso. Supporta `expected` come scalar, list (confronto ordinato) o dict.

```python
def check_json_field_equals(spec: dict, workspace: Path) -> tuple[bool, float, str]:
    import json
    path = workspace / spec["path"]
    if not path.exists():
        return False, 0.0, f"file not found: {spec['path']}"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return False, 0.0, f"invalid JSON: {e}"
    actual = jq_first(spec["jq_filter"], data)
    expected = spec["expected"]
    if isinstance(expected, list) and isinstance(actual, list):
        passed = sorted(map(str, actual)) == sorted(map(str, expected))
    else:
        passed = str(actual) == str(expected)
    return passed, 1.0 if passed else 0.0, f"json_field_equals {spec['jq_filter']}: actual={actual!r}, expected={expected!r}: {'OK' if passed else 'FAIL'}"
```

Richiede `jq` come dipendenza (Python binding `jq` o shell-out). Da aggiungere a `setup.sh`.

**Casi d'uso**: `tool_use_001` (classification per file), `memory_001-004` (campi memoria durevole), `knowledge_001` (count azioni), `autonomy_002` (count + owner).

### 5.5 `sha256_match`

Estrae un hash dal JSON dell'agente (via jq filter), ricalcola l'hash del file corrispondente nel workspace, confronta. È il cuore del "proof of inspection" in `tool_use_001`.

```python
def check_sha256_match(spec: dict, workspace: Path) -> tuple[bool, float, str]:
    import hashlib, json
    json_path = workspace / spec["path"]
    if not json_path.exists():
        return False, 0.0, f"file not found: {spec['path']}"
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return False, 0.0, f"invalid JSON: {e}"
    actual_hash = jq_first(spec["jq_filter"], data)
    if not actual_hash or not isinstance(actual_hash, str):
        return False, 0.0, f"jq_filter did not yield a string: {actual_hash!r}"
    target_path = workspace / spec["expected_sha256_of"]
    if not target_path.exists():
        return False, 0.0, f"target file not found: {spec['expected_sha256_of']}"
    target_content = target_path.read_bytes()
    expected_hash = hashlib.sha256(target_content).hexdigest()
    passed = actual_hash.lower() == expected_hash.lower()
    return passed, 1.0 if passed else 0.0, f"sha256_match for {spec['expected_sha256_of']}: {'OK' if passed else 'FAIL'} (actual={actual_hash[:12]}..., expected={expected_hash[:12]}...)"
```

**Casi d'uso**: `tool_use_001` (evidence_hash per ogni file classificato).

### 5.6 `min_count`

Conta occorrenze di un pattern regex in un file (o via jq filter su JSON) e verifica che siano ≥ expected. Estende il `min_lines` esistente per supportare pattern arbitrari.

```python
def check_min_count(spec: dict, workspace: Path) -> tuple[bool, float, str]:
    import re, json
    path = workspace / spec["path"]
    if not path.exists():
        return False, 0.0, f"file not found: {spec['path']}"
    content = path.read_text(encoding="utf-8")
    if "regex" in spec:
        actual = len(re.findall(spec["regex"], content, re.MULTILINE | re.DOTALL))
    elif "jq_filter" in spec:
        data = json.loads(content)
        result = jq_first(spec["jq_filter"], data)
        actual = len(result) if isinstance(result, list) else int(result)
    elif "glob" in spec:
        # spec["path"] is a directory, count files matching glob
        actual = len(list((workspace / spec["path"]).glob(spec["glob"])))
    else:
        return False, 0.0, "either 'regex', 'jq_filter', or 'glob' required"
    expected = int(spec["expected"])
    passed = actual >= expected
    return passed, 1.0 if passed else 0.0, f"min_count: actual={actual}, expected>={expected}: {'OK' if passed else 'FAIL'}"
```

**Casi d'uso**: `knowledge_001` (3 azioni), `autonomy_002` (4 owner), `long_horizon_001` (3 checkpoint), `subagents_001` (3 reconciliation).

### 5.7 `evidence_quote_verified`

Verifica che un campo `evidence_quote` in una entry JSON sia una sottostringa *verbatim* del file `source_doc` citato. Normalizza whitespace per evitare falsi negativi.

```python
def check_evidence_quote_verified(spec: dict, workspace: Path) -> tuple[bool, float, str]:
    import json, re
    json_path = workspace / spec["path"]
    if not json_path.exists():
        return False, 0.0, f"file not found: {spec['path']}"
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return False, 0.0, f"invalid JSON: {e}"
    entry = jq_first(spec["jq_filter"], data)
    if not isinstance(entry, dict):
        return False, 0.0, f"jq_filter did not yield a dict: {entry!r}"
    source_doc = entry.get("source_doc") or entry.get("source")
    evidence_quote = entry.get("evidence_quote") or entry.get("quote") or entry.get("evidence")
    if not source_doc or not evidence_quote:
        return False, 0.0, f"entry missing source_doc or evidence_quote: {entry!r}"
    source_path = workspace / source_doc
    if not source_path.exists():
        return False, 0.0, f"source_doc not found: {source_doc}"
    source_content = source_path.read_text(encoding="utf-8")
    # normalize whitespace: collapse multiple spaces to single
    norm = lambda s: re.sub(r"\s+", " ", s).strip()
    passed = norm(evidence_quote) in norm(source_content)
    return passed, 1.0 if passed else 0.0, f"evidence_quote_verified in {source_doc}: {'OK' if passed else 'FAIL'}"
```

**Casi d'uso**: `knowledge_001`, `knowledge_003`, `autonomy_002`, `long_horizon_003`. Questo è il check type più importante per bloccare la fabbricazione di evidenza.

### 5.8 `url_whitelist`

Estrae tutti gli URL da un file markdown, verifica che i domini siano in una whitelist, conta domini distinti, verifica che nessun URL della blacklist appaia.

```python
def check_url_whitelist(spec: dict, workspace: Path) -> tuple[bool, float, str]:
    import re, json
    from urllib.parse import urlparse
    path = workspace / spec["path"]
    if not path.exists():
        return False, 0.0, f"file not found: {spec['path']}"
    content = path.read_text(encoding="utf-8")
    urls = re.findall(r"https?://[^\s)\"]+", content)
    if not urls:
        return False, 0.0, "no URLs found"
    expected_file = workspace / spec["expected_sources_file"]
    if not expected_file.exists():
        # fall back to project-relative path
        expected_file = Path(spec["expected_sources_file"])
    config = json.loads(expected_file.read_text(encoding="utf-8"))
    whitelist = set(config["whitelist"])
    blacklist = set(config.get("fabricated_url_trap", []))
    domains_found = set()
    blacklisted_found = []
    for url in urls:
        domain = urlparse(url).netloc.lower()
        # strip www.
        domain = re.sub(r"^www\.", "", domain)
        if domain in whitelist:
            domains_found.add(domain)
        if url in blacklist or domain in {urlparse(b).netloc for b in blacklist}:
            blacklisted_found.append(url)
    min_distinct = int(spec.get("min_distinct_domains", 1))
    passed = (len(domains_found) >= min_distinct) and not blacklisted_found
    msg = f"url_whitelist: domains_found={sorted(domains_found)}, min_distinct>={min_distinct}, blacklisted={blacklisted_found}"
    return passed, 1.0 if passed else 0.0, msg
```

**Casi d'uso**: `browser_001`, `browser_002`. Questo è il check type più importante per bloccare la fabbricazione di fonti.

### 5.9 `trajectory_event_count`

Legge `results.jsonl` (prodotto dal runner) e conta eventi di un dato tipo. Verifica che siano ≥ min_count.

```python
def check_trajectory_event_count(spec: dict, workspace: Path, run_dir: Path) -> tuple[bool, float, str]:
    import json
    results_path = run_dir / "results.jsonl"
    if not results_path.exists():
        return False, 0.0, f"results.jsonl not found in {run_dir}"
    event_type = spec["event_type"]
    min_count = int(spec.get("min_count", 1))
    count = 0
    with results_path.open() as f:
        for line in f:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("type") == event_type or event.get("event_type") == event_type:
                count += 1
    passed = count >= min_count
    return passed, 1.0 if passed else 0.0, f"trajectory_event_count '{event_type}': actual={count}, expected>={min_count}: {'OK' if passed else 'FAIL'}"
```

Richiede che il runner passi `run_dir` all'evaluator (modifica al signature di `evaluate_artifacts`). Da coordinare con `aios_bench/runner.py`.

**Casi d'uso**: `subagents_001`, `subagents_002`, `subagents_003`. Converte "puoi usare subagenti" da opzionale a verificato.

### 5.10 `min_numeric`

Verifica che un valore numerico (estratto via regex o shell command) sia ≥ di un threshold. Diverso da `numeric_close` perché verifica un *minimo*, non una *vicinanza*.

```python
def check_min_numeric(spec: dict, workspace: Path) -> tuple[bool, float, str]:
    import re, subprocess
    if "regex" in spec:
        path = workspace / spec["path"]
        content = path.read_text(encoding="utf-8")
        m = re.search(spec["regex"], content)
        if not m:
            return False, 0.0, f"regex did not match"
        actual = float(m.group(1))
    elif "command" in spec:
        result = subprocess.run(spec["command"], shell=True, capture_output=True, text=True, cwd=workspace)
        if result.returncode != 0:
            return False, 0.0, f"command failed: {result.stderr}"
        try:
            actual = float(result.stdout.strip())
        except ValueError:
            return False, 0.0, f"command output not numeric: {result.stdout!r}"
    else:
        return False, 0.0, "either 'regex' or 'command' required"
    threshold = float(spec["threshold"])
    passed = actual >= threshold
    return passed, 1.0 if passed else 0.0, f"min_numeric: actual={actual}, threshold>={threshold}: {'OK' if passed else 'FAIL'}"
```

**Casi d'uso**: `long_horizon_001` (dimensione corpus ≥ 30000 caratteri).

### 5.11 Implementazione nel dispatch

Modificare `evaluate_artifacts` in `aios_bench/evaluators.py` per aggiungere i nuovi branch:

```python
def evaluate_artifacts(acceptance: list, workspace: Path, run_dir: Path = None) -> tuple[float, list]:
    total_weight = 0
    earned = 0
    results = []
    for spec in acceptance:
        check_type = spec["type"]
        if check_type == "exists":
            passed, score, msg = check_exists(spec, workspace)
        elif check_type == "contains":
            passed, score, msg = check_contains(spec, workspace)
        # ... existing checks ...
        elif check_type == "regex_strict":
            passed, score, msg = check_regex_strict(spec, workspace)
        elif check_type == "not_contains":
            passed, score, msg = check_not_contains(spec, workspace)
        elif check_type == "numeric_close":
            passed, score, msg = check_numeric_close(spec, workspace)
        elif check_type == "json_field_equals":
            passed, score, msg = check_json_field_equals(spec, workspace)
        elif check_type == "sha256_match":
            passed, score, msg = check_sha256_match(spec, workspace)
        elif check_type == "min_count":
            passed, score, msg = check_min_count(spec, workspace)
        elif check_type == "evidence_quote_verified":
            passed, score, msg = check_evidence_quote_verified(spec, workspace)
        elif check_type == "url_whitelist":
            passed, score, msg = check_url_whitelist(spec, workspace)
        elif check_type == "trajectory_event_count":
            if run_dir is None:
                raise ValueError("trajectory_event_count requires run_dir")
            passed, score, msg = check_trajectory_event_count(spec, workspace, run_dir)
        elif check_type == "min_numeric":
            passed, score, msg = check_min_numeric(spec, workspace)
        else:
            raise ValueError(f"unknown check type: {check_type}")
        # ... rest of weighting logic ...
```

### 5.12 Dipendenze e setup

- `jq` (Python binding o shell-out): richiesto per `json_field_equals`, `sha256_match`, `min_count` (con jq_filter), `evidence_quote_verified`. Aggiungere a `setup.sh`: `pip install jq` o verificare `jq` binario.
- `requests` (opzionale): per `url_whitelist` con HEAD check online. Per modalità offline, il check si basa solo sulla whitelist/blacklist statica.
- `git`: già richiesto per `unchanged` su `.git/` in `memory_004`.


---

## 6. Roadmap implementativa in 3 fasi

Le 28 modifiche proposte sono tra loro indipendenti ma hanno impatto e sforzo molto diversi. Questa sezione propone una sequenza in 3 fasi che massimizza il ritorno: ogni fase è auto-contenuta, rilasciabile separatamente, e produce un benchmark misurabilmente più duro della precedente.

### Fase 1 — Quick-wins (1–2 giornate di lavoro, basso rischio)

**Obiettivo**: convertire i 5 task più gameable in test reali senza modificare il fixture. Solo modifiche a `frontier_v2.json` e `evaluators.py`.

**Task target**:
- `autonomy_001` — esegui il tool dell'agente + verifica totale `$91.07`
- `browser_001` — URL whitelist + ground truth `DEFERRED`
- `knowledge_001` — JSON con `evidence_quote_verified`
- `coding_001` — test nascosti + `not_contains "580"`
- `learning_003` — piantare l'errore `sum of units` in `skills/reporting_workflow.md`

**Check types da implementare in `evaluators.py`**:
- `regex_strict` (sezione 5.1)
- `not_contains` (sezione 5.2)
- `numeric_close` (sezione 5.3)
- `json_field_equals` (sezione 5.4)
- `evidence_quote_verified` (sezione 5.7)
- `min_count` (sezione 5.6)

**Modifiche al fixture** (minime):
- `benchmarks/fixtures/workspace/skills/reporting_workflow.md`: aggiungere la regola buggata `sum of the units column` per `learning_003`.
- `benchmarks/fixtures/workspace/expected_sources.json`: nuovo file con whitelist domini + trappola URL per `browser_001`.
- `benchmarks/fixtures/workspace/tests/test_hidden.py`: nuovo file con test nascosti per `coding_001`.

**Validazione**:
- Eseguire il runner con piagent × Qwen (la run registrata) e verificare che i 5 task target ora falliscono o passano con score più basso.
- Eseguire il test suite `tests/test_evaluators.py` con i nuovi check types.

**Definition of Done**:
- Tutti i 5 task target hanno `task_revision` incrementato a 3.
- `evaluators.py` contiene i 6 nuovi check type con copertura di test.
- La run registrata mostra un pass-rate più basso (target: dal 88% al 50–60% sui 5 task modificati).

**Rischio**: basso. Le modifiche sono additive (nuovi check type, nuovi file di fixture), non rompono i task esistenti.

### Fase 2 — Fixture refactor (3–5 giornate, rischio medio)

**Obiettivo**: espandere il fixture per esercitare realmente le dimensioni dichiarate (long_horizon, memory, multi-file). Modifiche a `benchmarks/fixtures/workspace/` e `frontier_v2.json`.

**Task target**:
- `tool_use_001` — file trappola `legacy_sales.csv` + `archive/sales_2023.csv` + JSON con `evidence_hash`
- `tool_use_002` — multi-README indiretto + regex su valori effettivi
- `tool_use_003` — secondo test ambiguo + `unchanged` su file di test
- `memory_001-004` — secret token `7K9X2A` in `notes/user_preferences.md` + `.agent_memory/preferences.json` standard path + `.git/` piantato per `memory_004`
- `coding_002` — secondo difetto `off_by_one_tool.py`
- `coding_003` — test black-box CLI + 3 moduli richiesti
- `coding_004` — test nascosti + README strutturato
- `autonomy_001` — riga malformata in `expenses.csv` + `expenses_alt.csv` anti-hardcoding
- `autonomy_002` — false-friend action + 4 entry esatte
- `autonomy_003` — 5 check `unchanged` su file sorgenti
- `learning_001-002` — `sales_alt.csv` + `sales_schema_shift.csv` + esecuzione procedura
- `subagents_001-003` — corpus espanso `docs/research_a/`, `docs/research_b/` + sub-stream contraddittori + `trajectory_event_count`

**Check types da implementare**:
- `sha256_match` (sezione 5.5)
- `url_whitelist` (sezione 5.8) — per `browser_002`
- `trajectory_event_count` (sezione 5.9)

**Modifiche al fixture**:
- Aggiungere 8 nuovi file al seed workspace (file trappola, dataset alternativi, secondo difetto, ecc.).
- Aggiungere `.git/` inizializzato al seed per `memory_004`.
- Aggiungere `docs/research_a/` e `docs/research_b/` con 5+ file ciascuno per `subagents`.

**Modifiche al runner**:
- `aios_bench/runner.py`: passare `run_dir` a `evaluate_artifacts` per supportare `trajectory_event_count`.
- `aios_bench/runner.py`: preservare `.agent_memory/` tra run cold/warm per i task `memory`.

**Validazione**:
- Eseguire il runner end-to-end con almeno 2 adapter (piagent, opencode).
- Verificare che ogni task modificato ha score più basso rispetto alla run registrata.
- Eseguire `tests/test_retention.py` per verificare la persistenza di `.agent_memory/`.

**Definition of Done**:
- Tutti i 20 task in questa fase hanno `task_revision` incrementato a 3.
- Il fixture workspace ha ~30 file (vs ~10 attuali).
- La run end-to-end completa senza errori di valutazione.

**Rischio**: medio. Le modifiche al runner (`run_dir` propagation, `.agent_memory/` retention) possono rompere la resumability. Da testare con il meccanismo di `task_revision` (se il revision è cambiato, il runner ignora i risultati cached).

### Fase 3 — Suite-level changes (1–2 settimane, rischio alto)

**Obiettivo**: aggiungere il livello di ground-truth deterministico a tutte le categorie e una track multi-turn. Modifiche architetturali.

**Task target**:
- `long_horizon_001-003` — `gen_corpus.py` per corpus 50k token + `tools/validator.py` con counter + checkpoint di stato
- `browser_001-002` — modalità `url_whitelist` con HEAD check online + modalità pinned URLs offline
- `knowledge_002-003` — 3 file di procedure con contraddizioni reali + 3 fonti gerarchiche

**Modifiche architetturali**:
- Aggiungere `benchmarks/fixtures/generate.py <seed> <variant>` con 4 varianti: `clean`, `messy`, `adversarial`, `large`. Il runner genera la variante prima di ogni task.
- Aggiungere una track multi-turn in `aios_bench/runner.py`: turno 1 = task originale, turno 2 = update contraddittorio, turno 3 = richiesta di diff. Lo scoring è la media sui 3 turni.
- Aggiungere `expected/` directory nel fixture con valori attesi precomputati per ciascun task (es. `expected/autonomy_001_total.txt` contiene `91.07`).

**Check types da implementare**:
- `min_numeric` (sezione 5.10)

**Validazione**:
- Eseguire la track multi-turn su almeno 3 task (es. `autonomy_001`, `memory_003`, `long_horizon_001`).
- Verificare che il pass-rate su track multi-turn è significativamente più basso del single-turn.
- Eseguire `gen_corpus.py` con 4 seed diversi e verificare determinismo.

**Definition of Done**:
- `long_horizon_*` ha corpus ≥ 30k caratteri (verificato da `min_numeric`).
- Track multi-turn disponibile via flag `--track=multi_turn`.
- `gen_corpus.py` produce 4 varianti deterministiche.

**Rischio**: alto. Le modifiche architetturali (multi-turn, generatore di fixture) possono introdurre regressioni nella resumability e nella riproducibilità. Da sviluppare in branch separato, mergeare solo dopo che la Fase 2 è stabile da almeno 1 settimana.

### Sequenza temporale consigliata

| Settimana | Fase | Output |
|-----------|------|--------|
| 1 | Fase 1 | PR con 5 task induriti + 6 nuovi check type |
| 2–3 | Fase 2 | PR con 20 task induriti + 3 nuovi check type + fixture espanso |
| 4 | Stabilizzazione | Bug-fix su Fase 1+2, documentazione, test end-to-end |
| 5–6 | Fase 3 | PR con `gen_corpus.py` + track multi-turn + 1 nuovo check type |
| 7 | Release | v2.0 della suite, deprecare `frontier_v2.json` a favore di `frontier_v3.json` |


---

## 7. Riferimenti cross-benchmark

Questa sezione mappa le modifiche che si *propagano* su più task — modificare un singolo elemento del fixture o dell'evaluator ha effetti su più task, e queste dipendenze vanno gestite esplicitamente per evitare regressioni.

### 7.1 `broken_tool.py` — il difetto condiviso

**Status quo**: il file `benchmarks/fixtures/workspace/projects/broken_tool.py` contiene una funzione `monthly_total` che solleva `TypeError` quando riceve input misto (`[10, 20, "30"]`). Il difetto è usato in **5 task**:

| Task | Come usa il difetto |
|------|---------------------|
| `tool_use_003` | "diagnostica, fixa, rerun, prova" — il difetto è il target principale |
| `coding_002` | "debug con riproduzione" — stesso difetto come target |
| `coding_003` | "refactor broken_tool in parse/validate/report" — usa il file come base |
| `autonomy_003` | "fix broken tool + regression" — stesso difetto come target |
| `learning_003` | "errore intenzionale nella procedura" — *non* usa `broken_tool.py` ma eredita il pattern "trova e correggi" |

**Impatto delle modifiche**: modificare `broken_tool.py` (es. cambiare il tipo di difetto da TypeError a off-by-one) invalida simultaneamente 4 task. Le `task_revision` di tutti e 4 vanno incrementate.

**Raccomandazione**: non modificare `broken_tool.py` (TypeError) ma *aggiungere* un secondo file `projects/off_by_one_tool.py` con un difetto indipendente. Questo:
- mantiene la backward compatibilità (i task esistenti non si rompono),
- aggiunge complessità (l'agente non può pattern-matchare un singolo bug noto),
- è un cambiamento puramente additivo.

I 5 task che usano `broken_tool.py` vanno poi *modificati singolarmente* per richiedere anche la risoluzione di `off_by_one_tool.py` — vedi sezioni 4.1, 4.4, 4.5.

### 7.2 Fixture seed — la radice comune

**Status quo**: tutti i 28 task partono dallo stesso seed `benchmarks/fixtures/workspace/` copiato da `BenchmarkRunner._workspace`. Modificare il seed invalida *tutti* i task.

**Dipendenze critiche**:
- `data/expenses.csv` (6 righe): usato in `autonomy_001`, `memory_002`, `learning_001`, `coding_004` (via anti-hardcoding test). Aggiungere una riga malformata (per `autonomy_001`) invalida anche i totali attesi in `memory_002` e `learning_001`.
- `data/sales.csv` (6 righe): usato in `coding_001`, `learning_001-002`. Lo `sales_alt.csv` anti-hardcoding (per `coding_001` e `learning_001`) deve avere lo stesso schema ma valori diversi.
- `notes/meeting_notes.md`: usato in `knowledge_001`, `knowledge_003`, `autonomy_002`, `long_horizon_003`. Aggiungere la false-friend action (per `autonomy_002`) cambia il count di azioni non risolte da 3 a 4 (3 confermate + 1 tentative), invalidando il `min_count: 3` di `knowledge_001`.

**Raccomandazione**: sviluppare le modifiche al seed in un branch separato, aggiornare *tutti* gli `expected` di tutti i task in un singolo commit, e bumpare `task_revision` su tutti i 28 task simultaneamente.

### 7.3 `tools/` directory — path di output standardizzato

**Status quo**: molti task richiedono all'agente di produrre file in `tools/`. La naming è lasciata all'agente, il che rende i check `command:` fragili (`ls tools/ | grep -v README | head -1`).

**Raccomandazione**: standardizzare i path di output nel prompt modificato:
- `tools/expense_report.py` per `autonomy_001`
- `tools/preferred_tool.py` per `memory_002`
- `tools/general_tool.ts` + `tools/security_tool.py` per `memory_004`
- `tools/robust_report.py` per `coding_004`
- `tools/step1_summary.py`, `tools/step2_chart.py`, `tools/step3_report.py` per `long_horizon_002`
- `tools/investigation_helper.py` per `long_horizon_003`

Questo semplifica i check `command:` e li rende deterministici.

### 7.4 `.agent_memory/` — path di memoria durevole

**Status quo**: non esiste uno standard per dove l'agente deve persistere la memoria tra run cold/warm. Ogni adapter fa come preferisce.

**Raccomandazione**: standardizzare il path `.agent_memory/` nel runner:
- Il runner crea `.agent_memory/` prima della run cold.
- Il runner preserva `.agent_memory/` tra run cold/warm (configurazione `workspace.retention`).
- Il task `memory_001` richiede esplicitamente la scrittura di `.agent_memory/preferences.json`.

Questo richiede modifica a `aios_bench/runner.py` (sezione `workspace.retention`) e ai 6 adapter (perché rispettino il path).

### 7.5 `tests/` directory — test pre-confezionati

**Status quo**: non esistono test nel seed. L'agente scrive sia codice che test.

**Raccomandazione**: aggiungere al seed una directory `tests/` con test nascosti per ciascun task di coding:
- `tests/test_hidden_report_cli.py` per `coding_001`
- `tests/test_broken_tool.py` per `tool_use_003`, `coding_002`, `autonomy_003`
- `tests/test_off_by_one.py` per gli stessi (dopo aggiunta del secondo difetto)
- `tests/test_helpers.py` per `tool_use_003` (test ambiguo)
- `tests/test_cli_contract.py` per `coding_003`
- `tests/test_robust.py` per `coding_004`
- `tests/test_chain.py` per `long_horizon_002`

Tutti questi file vanno aggiunti al seed e protetti con `unchanged` (sha256) nei rispettivi task.

### 7.6 `expected/` directory — valori attesi precomputati

**Status quo**: i valori attesi (es. totale `$91.07`, totale alt `$742.50`) sono hardcodati nel JSON di acceptance.

**Raccomandazione**: spostare i valori attesi in `benchmarks/fixtures/expected/` come file JSON:
- `expected/autonomy_001.json`: `{"total_expenses": 91.07, "total_transactions": 6, "skipped": 1}`
- `expected/coding_001.json`: `{"seed_total": 580, "alt_total": 742}`
- `expected/browser_001.json`: `{"default_isolation_level": "DEFERRED", "whitelist": [...], "blacklist": [...]}`

I check type (`numeric_close`, `regex_strict`, `url_whitelist`) leggono gli expected da questi file invece di averli inline. Questo separa il "cosa misurare" (nel JSON di acceptance) dal "quanto è il valore" (nel file expected), permettendo di rigenerare i valori attesi se il fixture cambia.

### 7.7 Prompt modificati — appendice separata

Le modifiche all'`acceptance` richiedono spesso modifiche al `prompt` del task (es. specificare il path standardizzato dell'output, elencare i requisiti R1–R5, menzionare il secret token). Queste modifiche al prompt vanno fatte in `frontier_v2.json` nel campo `prompt` di ciascun task. Vedi Appendice B per i prompt completi riscritti.


---

## 8. Appendice: catalogo completo delle modifiche

Questa appendice riepiloga in forma tabellare tutte le modifiche proposte, organizzate per file da modificare. È la "checklist di implementazione" per la PR.

### 8.1 Modifiche a `aios_bench/evaluators.py`

Aggiungere 10 nuovi check type (snippet completi in sezione 5):

| # | Check type | LOC stimati | Dipendenze |
|---|------------|-------------|------------|
| 1 | `regex_strict` | ~20 | `re` (stdlib) |
| 2 | `not_contains` | ~10 | nessuna |
| 3 | `numeric_close` | ~25 | `re`, `json` |
| 4 | `json_field_equals` | ~25 | `jq` (pip) o shell-out |
| 5 | `sha256_match` | ~25 | `hashlib`, `json`, `jq` |
| 6 | `min_count` | ~25 | `re`, `json`, `jq` |
| 7 | `evidence_quote_verified` | ~30 | `json`, `jq` |
| 8 | `url_whitelist` | ~35 | `re`, `json`, `urllib.parse`, opz. `requests` |
| 9 | `trajectory_event_count` | ~20 | `json` |
| 10 | `min_numeric` | ~25 | `re`, `subprocess` |

Modificare `evaluate_artifacts` per dispatch sui nuovi tipi (sezione 5.11). Modificare il signature per accettare `run_dir` (per `trajectory_event_count`).

Totale: ~240 LOC + 10 entry nel dispatch.

### 8.2 Modifiche a `aios_bench/runner.py`

- Passare `run_dir` a `evaluate_artifacts` in `BenchmarkRunner.run_task`.
- Aggiungere `workspace.retention` config: lista di path da preservare tra run cold/warm (default: `[".agent_memory/"]`).
- Verificare che `shutil.copytree` del seed non sovrascriva i path in `retention` se già esistenti dal run precedente.

LOC stimati: ~30.

### 8.3 Modifiche a `benchmarks/tasks/frontier_v2.json`

Per ciascuno dei 28 task:
- Sostituire il campo `acceptance` con la versione "Dopo" delle sezioni 4.x.
- Incrementare `task_revision` da 2 a 3.
- Modificare il campo `prompt` per specificare path standardizzati, secret token, requisiti enumerati (R1–R5), ecc.

LOC stimati: ~1500 (JSON, ma più lungo per i prompt riscritti).

### 8.4 Modifiche a `benchmarks/fixtures/workspace/`

Aggiungere i seguenti file:

| Path | Scopo | Task che lo usano |
|------|-------|-------------------|
| `notes/user_preferences.md` | Secret token `7K9X2A` + preferenze | `memory_001-004` |
| `data/legacy_sales.csv` | File trappola (nome "legacy" ma autorevole) | `tool_use_001` |
| `archive/sales_2023.csv` | File trappola (nome autorevole ma decoy) | `tool_use_001` |
| `docs/README.md` | README stale (`port: 8080`) | `tool_use_002` |
| `archive/README_2025.md` | README archivio (`port: 8081`) | `tool_use_002` |
| `config/app.yaml` | Config reale (`port: 8081, env: production`) | `tool_use_002` |
| `tools/run_server.py` | Codice consumer che legge `config/app.yaml` | `tool_use_002` |
| `tests/test_broken_tool.py` | Test nascosti per il TypeError | `tool_use_003`, `coding_002`, `autonomy_003` |
| `tests/test_off_by_one.py` | Test nascosti per il nuovo difetto | `coding_002`, `autonomy_003` |
| `tests/test_helpers.py` | Test ambiguo (mock che referenzia `broken_tool`) | `tool_use_003` |
| `projects/off_by_one_tool.py` | Secondo difetto (off-by-one date range) | `coding_002`, `autonomy_003` |
| `tests/test_hidden_report_cli.py` | Test nascosti per `coding_001` | `coding_001` |
| `data/sales_alt.csv` | CSV con valori diversi per anti-hardcoding | `coding_001`, `autonomy_001`, `learning_001` |
| `data/expenses_alt.csv` | CSV spese con valori diversi | `autonomy_001` |
| `data/expenses.csv` (modificato) | Aggiungere riga malformata | `autonomy_001` |
| `data/sales_schema_shift.csv` | CSV con colonne rinominate | `learning_002` |
| `tests/test_cli_contract.py` | Test black-box per CLI refactor | `coding_003` |
| `tests/test_robust.py` | Test nascosti per `coding_004` | `coding_004` |
| `data/expenses_empty.csv` | CSV con solo header | `coding_004` |
| `skills/reporting_workflow.md` | Procedura con bug `sum of units` | `learning_003` |
| `skills/reporting_workflow.py` | Script template (vuoto, da completare) | `learning_001-003` |
| `notes/suggested_sources.md` | URL inesistenti come trappola | `browser_001-002` |
| `procedures/next_draft.md` | Terza versione di procedure | `knowledge_002-003` |
| `notes/old_meeting_notes.md` | Distrattore "azione già completata" | `knowledge_001` |
| `tools/validator.py` | Validator con counter che fallisce al 3° invocazione | `long_horizon_001` |
| `docs/research_a/` (5 file) | Set di documenti pro-migrazione | `subagents_001-003` |
| `docs/research_b/` (3 file) | Set di documenti contro-migrazione (CVE) | `subagents_002` |
| `notes/security_note.md` | Nota "per tool di sicurezza usa Python" | `memory_004` |
| `.git/` (inizializzato) | Repo git per verificare no-commit | `memory_004` |

Totale: ~25 nuovi file + 2 modifiche a file esistenti.

### 8.5 Nuovi file a livello di progetto

| Path | Scopo |
|------|-------|
| `benchmarks/fixtures/expected_sources.json` | Whitelist domini + trappola URL per `browser` |
| `benchmarks/fixtures/expected/` (directory) | Valori attesi precomputati per ciascun task |
| `benchmarks/fixtures/gen_corpus.py` | Generatore di corpus sintetico per `long_horizon` |
| `benchmarks/fixtures/generate.py` | Generatore parametrico di fixture (varianti clean/messy/adversarial/large) |
| `tests/test_evaluators_extended.py` | Test unitari per i 10 nuovi check type |

### 8.6 Modifiche a `setup.sh` / `pyproject.toml`

- Aggiungere dipendenza `jq` (Python binding).
- Aggiungere dipendenza `requests` (opzionale, per `url_whitelist` online).
- Verificare `git` e `ts-node` disponibili nell'ambiente.

### 8.7 Documentazione

- Aggiornare `docs/harness-setup.md` con i nuovi check type e i nuovi fixture.
- Aggiornare `README.md` con la spiegazione delle 3 fasi di hardening.
- Aggiungere `docs/HARDENING.md` con il riepilogo delle modifiche e la motivation (questo report, riassunto).

### 8.8 Deprecation

- I file `benchmarks/tasks/specs/{autonomy_001,tool_use_003}.json` sono morti (overridden da inline acceptance). Eliminarli.
- I file legacy `benchmarks/tasks/{autonomy,browser,coding,knowledge,learning,long_horizon,memory,subagents,tool_use}.json` (senza `_v2`) sono già deprecati. Eliminarli se non usati dai test.

### 8.9 Riepilogo conteggi

| Categoria | File modificati | File creati | LOC stimati |
|-----------|-----------------|-------------|-------------|
| Evaluator | 1 (`evaluators.py`) | 0 | ~240 |
| Runner | 1 (`runner.py`) | 0 | ~30 |
| Catalogo task | 1 (`frontier_v2.json`) | 0 | ~1500 |
| Fixture | 2 (modificati) | ~25 | ~500 |
| Nuovi script | 0 | 4 | ~400 |
| Test | 1 (`test_evaluators.py` modificato) | 1 (`test_evaluators_extended.py`) | ~300 |
| Docs | 3 | 1 | ~200 |
| **Totale** | **9** | **~31** | **~3170** |

Stima di sforzo: 1–2 settimane di lavoro full-time per uno sviluppatore con familiarità con la codebase. Si allinea alla roadmap in 3 fasi della sezione 6.

### 8.10 Metriche di successo

Per verificare che l'hardening ha funzionato, misurare prima e dopo:

| Metrica | Prima (run registrata) | Dopo (target) |
|---------|----------------------|---------------|
| Pass-rate globale | 23/26 = 88% | 35–55% |
| Score medio | 87.2 | 50–70 |
| Tasks con `acceptance_score = 1.0` | ~20/28 | <10/28 |
| Tasks che verificano correttezza numerica | 0/28 | ≥10/28 |
| Tasks che eseguono tool prodotti dall'agente | 0/28 | ≥8/28 |
| Tasks con fixture > 5KB | 0/28 | ≥3/28 (long_horizon) |
| Tasks multi-turn | 0/28 | ≥3/28 (Fase 3) |

Se il pass-rate post-hardening resta > 70%, l'hardening non è stato sufficiente. Se scende sotto il 20%, l'hardening è stato eccessivo (i task sono troppo difficili anche per agenti capaci).

---

*Fine del report.*
