# AIOS-bench — Report di irrobustimento dei task

> Historical audit of pre-v3 behavior. It is retained as design history and
> must not be used as the current execution or scoring specification.

**Repository analizzata:** `Cartaz/AIOS-bench`
**Oggetto del report:** logica delle modifiche proposte ai 28 task del catalogo `frontier_v2.json`, task per task, per aumentarne la difficoltà genuina e la resistenza al "gaming".

---

## 1. Metodologia

L'analisi si basa su tre fonti incrociate:

1. Il codice del valutatore (`aios_bench/evaluators.py`), che definisce cosa è *effettivamente* verificabile oggi (check di tipo `exists`, `contains`, `regex`, `json_valid`, `sha256`, `unchanged`, `command`, `max_files`).
2. Il catalogo dei 28 task attivi (`benchmarks/tasks/frontier_v2.json`) e i loro `acceptance` check reali.
3. I risultati di un run reale già eseguito (harness `piagent`, modello Qwen locale, 26/28 task completati, 88.5% di successo) — usati come prova empirica di *dove* il benchmark si lascia effettivamente ingannare, non solo di dove sembra debole sulla carta.

Per ogni task riporto: stato attuale, problema identificato, modifica proposta, e la logica che la giustifica.

---

## 2. Problemi sistemici (comuni a più task)

Prima del dettaglio task-per-task, quattro problemi trasversali motivano gran parte delle modifiche proposte:

| # | Problema | Evidenza | Conseguenza |
|---|----------|----------|-------------|
| S1 | I check di accettazione sono quasi tutti `contains` su parole chiave, non verifica semantica/numerica | Nessun task attivo verifica un valore calcolato esatto | Un report con i numeri sbagliati ma le parole giuste passa |
| S2 | Il check `unchanged` (hash contro la fixture originale) esiste nel codice ma non è usato in **nessuno** dei 28 task | `grep '"unchanged"' frontier_v2.json` → 0 occorrenze | Vincoli espliciti tipo "do not modify source data" non sono mai verificati |
| S3 | La fixture condivisa è minuscola (7 file, ~6 righe per CSV) | `tool_use_001` ("inspect recursively") risolto con **1 tool call**, 424 token, score 100/100 | I task "di esplorazione/scala" non richiedono alcuna esplorazione reale |
| S4 | Nessuna verifica sulla telemetria di processo (subagenti, memoria) già raccolta ma non collegata all'accettazione | `subagent_start`/`subagent_end` sono eventi tracciati in `telemetry.py` ma mai controllati in `acceptance` | Un agente può "dichiarare" delega/memoria a parole senza averla mai usata |

Queste quattro correzioni da sole chiuderebbero la maggior parte dei varchi individuati nel run reale, prima ancora di toccare i singoli prompt.

---

## 3. Modifiche task per task

### Categoria: `autonomy`

#### autonomy_001 (T3 → proposto T4)
- **Check attuali:** esistenza di `reports/monthly_expense_report.md` e `tools/expense_report.py`; presenza delle stringhe "Total Expenses" e "Total Transactions".
- **Problema:** nessuna verifica che il totale calcolato sia corretto. Esisteva un file legacy (`specs/autonomy_001.json`, non collegato al task attivo) che controllava il valore esatto `"91.07"` — la rimozione di quel controllo è una regressione di rigore, non una scelta di design.
- **Modifica proposta:** ingrandire `data/expenses.csv` (200+ righe, valute miste, rimborsi negativi, righe duplicate) e aggiungere un check `contains` sul totale corretto ricalcolato indipendentemente, oppure un check `command` che esegue uno script di riferimento e confronta l'output con quello dell'agente.
- **Logica:** un task "produce un report finanziario" senza verifica del numero finale non misura affidabilità, misura solo capacità di formattare un file Markdown.

#### autonomy_002 (T4, invariato nel tier)
- **Check attuali:** `json_valid` su `action_tracker.json`; presenza di "Source" e "Priority" nel `.md`.
- **Problema:** "distinguere azioni confermate da suggerimenti" ed "evitare fatti inventati" non sono verificabili con `contains` — un agente può scrivere qualunque cosa purché contenga le due parole chiave.
- **Modifica proposta:** definire nella fixture (`notes/meeting_notes.md`) un set noto di azioni confermate vs. ambigue, e aggiungere un check `regex` o `command` (piccolo script Python di validazione) che confronti il JSON prodotto contro uno schema atteso con conteggio minimo di campi `source` popolati correttamente.
- **Logica:** rende falsificabile il vincolo di provenance, che oggi è solo dichiarativo.

#### autonomy_003 (T5, invariato)
- **Check attuali:** `python -m pytest -q` (peso 4, fatal) + esistenza di `reports/autonomy_changelog.md`.
- **Problema:** è il task meglio verificato del lotto (usa il test runner reale come oracolo), ma `projects/broken_tool.py` ha un bug troppo ovvio (somma `int + str`) risolvibile senza reale debug.
- **Modifica proposta:** sostituire con un bug più subdolo (es. un edge case che produce un risultato plausibile ma numericamente sbagliato solo per determinati input, rilevabile solo con test aggiuntivi mirati) e aggiungere `unchanged` sui file di test esistenti per impedire che vengano indeboliti invece che il codice corretto.
- **Logica:** oggi il vincolo "do not weaken tests" è scritto nel prompt ma non verificato via hash — è esattamente il tipo di scorciatoia che un modello debole userebbe.

---

### Categoria: `browser`

#### browser_001 (T4, invariato)
- **Check attuali:** esistenza file, presenza di "http", minimo 18 righe.
- **Problema:** non c'è alcuna verifica che le fonti citate siano reali o pertinenti — un URL plausibile ma inventato passa.
- **Modifica proposta:** aggiungere una fase di verifica post-hoc (fuori dal punteggio in tempo reale, se necessario) che esegua fetch degli URL salvati e controlli che il dominio sia in una whitelist di fonti autorevoli (docs ufficiali Python, non forum), più un check `regex` che richieda almeno 3 URL distinti (non lo stesso ripetuto tre volte).
- **Logica:** "usa almeno tre fonti autorevoli" è oggi un vincolo di facciata; senza verifica di realtà delle fonti il task premia la fluidità del testo, non la ricerca.

#### browser_002 (T5, invariato)
- **Check attuali:** esistenza file, "Source", "Verification", minimo 25 righe.
- **Problema:** stesso limite di browser_001, aggravato dal fatto che il task richiede *quattro* fonti e la riconciliazione di guidance contrastante per versione — nessuno di questi due elementi è verificato.
- **Modifica proposta:** check `regex` che richieda una tabella con almeno 4 righe distinte nella sezione "Source"; verifica di dominio come sopra; eventualmente un secondo file richiesto (`reports/version_conflicts.md`) con almeno 2 conflitti espliciti identificati, verificabile con `min_lines` + `regex` mirato.
- **Logica:** separare "sintesi" da "conteggio minimo di fonti distinte realmente usate" rende il task discriminante invece che superabile con un unico paragrafo ben scritto.

---

### Categoria: `coding`

#### coding_001 (T3, invariato)
- **Check attuali:** esistenza `tools/report_cli.py`; comando `--help` funzionante; suite di test.
- **Problema:** "valida header e righe malformate" non è testato contro dati malformati *reali* della fixture — l'agente scrive da solo i propri casi di test, quindi si autovaluta.
- **Modifica proposta:** aggiungere a `data/sales.csv` alcune righe realmente malformate (campo mancante, tipo errato, encoding non standard) e un check `command` che esegua `tools/report_cli.py` su un file di input malformato *fornito dal benchmark* (non scritto dall'agente), verificando l'exit code atteso.
- **Logica:** un oracolo esterno di malformazione è l'unico modo per impedire che l'agente si scriva test "facili" ad hoc.

#### coding_002 (T4, invariato)
- **Check attuali:** suite di test (peso 4, fatal); `reports/debugging.md` con almeno 5 righe.
- **Problema:** ragionevolmente solido, ma "diagnose the root cause" non è verificato nel contenuto del report — bastano 5 righe qualsiasi.
- **Modifica proposta:** aggiungere `contains_any` sul report per termini tecnici specifici legati alla causa reale del bug (evita che il changelog sia generico), e alzare `min_lines` a un valore proporzionato alla complessità del bug introdotto.
- **Logica:** allineare la verifica testuale al contenuto tecnico reale, non solo alla lunghezza.

#### coding_003 (T4, invariato)
- **Check attuali:** suite di test (fatal) + esistenza `reports/refactor.md`.
- **Problema:** "preserve the CLI interface" non è verificato — un refactor che rompe silenziosamente l'interfaccia a riga di comando passerebbe se i test esistenti non la coprono.
- **Modifica proposta:** aggiungere un check `command` dedicato che invochi lo strumento con gli argomenti originali e verifichi l'output atteso, indipendente dalla suite di test scritta/modificata dall'agente.
- **Logica:** separare la verifica di interfaccia da quella di test interni evita che un refactor "tecnicamente verde" nasconda una breaking change.

#### coding_004 (T5, invariato)
- **Check attuali:** suite di test (fatal, timeout 60s); `reports/coding_quality.md`; esistenza `README.md`.
- **Problema:** "exercise an invalid-input path, fix any issue discovered" è un requisito procedurale non verificabile con i check attuali — non c'è modo di sapere se l'agente ha davvero eseguito quel percorso.
- **Modifica proposta:** fornire nella fixture un caso di input invalido con un bug noto e nascosto, verificabile solo eseguendo lo strumento su quell'input specifico (check `command` dedicato, separato dalla suite generale).
- **Logica:** rende falsificabile un passaggio del prompt che oggi è pura fiducia sulla parola dell'agente.

---

### Categoria: `knowledge`

#### knowledge_001 (T3, invariato)
- **Check attuali:** esistenza file; "Source"; "Confidence".
- **Problema:** "le tre azioni più importanti non risolte" non ha una risposta di riferimento — qualunque terzina passa, corretta o no.
- **Modifica proposta:** arricchire `notes/meeting_notes.md` con più azioni (8-10, alcune palesemente meno prioritarie) e un secondo documento di priorità implicita, poi aggiungere un check `contains_any` sui 2-3 elementi che *devono* comparire secondo un answer-key definito in fase di progettazione del task.
- **Logica:** senza answer-key anche parziale, "identifica le priorità corrette" è indistinguibile da "scrivi tre azioni qualsiasi".

#### knowledge_002 (T4, invariato)
- **Check attuali:** `json_valid`; esistenza `.md`; "Changed".
- **Problema:** il diff tra `procedures/current.md` e `procedures/previous.md` è oggi banale (4 vs 5 step, differenza ovvia) — non testa realmente capacità di comparazione fine.
- **Modifica proposta:** rendere le due procedure più simili tra loro con differenze sottili (riordino di step equivalenti da non segnalare come "changed", una modifica di soglia numerica da segnalare), e verificare nel JSON che il campo `changes` abbia esattamente il conteggio atteso di modifiche sostanziali (né di più né di meno).
- **Logica:** un diff "quasi banale" non discrimina; un diff con falsi positivi potenziali (riordini innocui) sì.

#### knowledge_003 (T5, invariato)
- **Check attuali:** esistenza file; "Evidence"; "Uncertainty"; minimo 20 righe.
- **Problema:** il task chiede di risolvere un conflitto tra procedure e meeting notes, ma nella fixture attuale non esiste un conflitto esplicito tra questi due documenti — il compito è teoricamente impossibile da eseguire come descritto.
- **Modifica proposta:** introdurre un conflitto reale e verificabile (es. `notes/meeting_notes.md` istruisce di usare `.txt`, `procedures/current.md` richiede `.md`) e un check `regex` che verifichi che la raccomandazione finale scelga esplicitamente la fonte più autorevole con motivazione.
- **Logica:** un task di "conflict resolution" ha bisogno di un conflitto reale nella fixture, non solo nel prompt.

---

### Categoria: `learning`

#### learning_001 (T4, invariato)
- **Check attuali:** esistenza `skills/reporting_workflow.md`; "Validation"; "Recovery".
- **Problema:** il workspace viene ricreato da zero a ogni task (`_workspace()` in `runner.py` fa `rmtree` + `copytree` dalla fixture pristina). Il file di skill creato qui non sopravvive al task successivo a meno che l'harness abbia una propria memoria esterna — che per l'unico harness testato finora (`piagent`) non è nemmeno dichiarata come capability nell'adapter.
- **Modifica proposta:** o (a) limitare esplicitamente questa catena di task (`learning_001→003`) agli harness con `"skills"` o `"memory"` in `capabilities`, oppure (b) introdurre un meccanismo di stato di workspace persistente tra i task di una stessa catena, invece del reset totale.
- **Logica:** senza una di queste due correzioni, il task misura la capacità dell'harness di avere memoria esterna, non la capacità dell'agente di generalizzare una procedura — e oggi lo fa in modo silenzioso e non dichiarato.

#### learning_002 (T4, invariato)
- **Check attuali:** esistenza file; "adapt"; "transfer".
- **Problema:** eredita il problema di continuità di learning_001; inoltre "prefer the learned procedure" non è verificabile senza sapere se la procedura era davvero disponibile.
- **Modifica proposta:** condizionato alla correzione di learning_001, aggiungere un check che confronti il contenuto di `reports/learning_transfer.md` con la presenza di riferimenti specifici alla procedura appresa (non genericamente "transfer").
- **Logica:** stesso principio di knowledge_002 — la parola chiave da sola non prova che il trasferimento sia avvenuto.

#### learning_003 (T5, invariato)
- **Check attuali:** esistenza `skills/reporting_workflow.md` *corretto* + `reports/learning_correction.md` con "Correction".
- **Problema:** il task presuppone che esista già una skill con un errore intenzionale al suo interno — ma la fixture pristina non contiene alcuna cartella `skills/`. L'agente deve quindi ricreare da zero, nello stesso singolo task, sia l'errore che la sua correzione: il task com'è scritto non testa individuazione di un errore preesistente, ma la capacità di simulare l'intero arco narrativo in un colpo solo.
- **Modifica proposta:** popolare la fixture con un file `skills/reporting_workflow.md` reale contenente un errore plausibile e nascosto (es. una formula di calcolo del totale con un off-by-one), definito in anticipo, e un check `regex` che verifichi la correzione specifica di *quella* regola.
- **Logica:** un task di "rilevamento di un errore silenzioso" richiede che l'errore esista realmente nell'input, non che l'agente lo inventi e lo risolva nello stesso respiro.

---

### Categoria: `long_horizon`

#### long_horizon_001 (T4, invariato)
- **Check attuali:** esistenza file; "Validation"; minimo 8 righe.
- **Problema:** la policy di contesto a 98k token dichiarata nel README non è mai messa sotto stress dalla fixture (che è minuscola); "recover from an error" non è verificato — non c'è un errore reale da recuperare.
- **Modifica proposta:** iniettare nella fixture un errore di runtime deterministico e riproducibile a metà del workflow (es. un file di configurazione mancante che va creato al volo), verificabile con un check `command` che esegua l'intero pipeline end-to-end.
- **Logica:** "recovery" è un vincolo comportamentale che va reso osservabile con un fallimento reale, non solo enunciato nel prompt.

#### long_horizon_002 (T5, invariato)
- **Check attuali:** suite di test (fatal); esistenza `README.md`.
- **Problema:** è il task con meno check (2) dell'intero catalogo nonostante sia Tier 5; "maintain a dependency chain between changes and checks" non ha alcun riscontro verificabile.
- **Modifica proposta:** aggiungere almeno un check `regex` sul README che richieda una sezione esplicita di cambiamenti/rationale, e un secondo check `command` mirato sulla feature richiesta specificamente (non solo la suite generale).
- **Logica:** due check per un task Tier 5 è sproporzionatamente poco rispetto alla complessità dichiarata nel prompt.

#### long_horizon_003 (T5, invariato)
- **Check attuali:** esistenza file; "Requirement"; "Evidence".
- **Problema:** "audit every original requirement and correct omissions" richiede che esistano requisiti originali numerati/tracciabili — oggi il prompt non ne definisce un elenco verificabile.
- **Modifica proposta:** strutturare il prompt con una checklist esplicita di requisiti numerati nella fixture (es. `notes/requirements.md`), e un check `regex` che richieda che ciascun requisito compaia nel report finale con uno stato (soddisfatto/non soddisfatto).
- **Logica:** un audit ha senso solo contro una lista di riferimento nota; oggi la lista esiste solo nella testa di chi legge il prompt.

---

### Categoria: `memory`

#### memory_001 (T3, invariato)
- **Check attuali:** `contains: "Python"` + `contains: "commit"` in `reports/memory_note.md`.
- **Problema:** nel run reale questo task è passato in **34 secondi con 2 tool call** — il check verifica solo che due parole compaiano in un file, non che una memoria persistente sia stata effettivamente scritta da qualche parte recuperabile in un task successivo.
- **Modifica proposta:** aggiungere una verifica esterna al workspace, ove tecnicamente possibile per l'harness in uso (es. controllo su uno store di memoria dichiarato via `capabilities`), oppure — più praticamente — richiedere che `memory_002` dimostri il recupero *senza* che il testo delle preferenze sia ripetuto nel prompt del task successivo (oggi il prompt di ogni task è indipendente, quindi non c'è modo di forzare un vero richiamo di memoria).
- **Logica:** "impara una preferenza durevole" è per definizione un test che deve estendersi oltre il singolo task; oggi è verificato interamente dentro il singolo task, il che lo rende una tautologia.

#### memory_002 (T4, invariato)
- **Check attuali:** esistenza file; `contains: "preference"`.
- **Problema:** "retrieve memory rather than asking the user to repeat it" non è falsificabile: il prompt del task ripete implicitamente tutto il contesto necessario nella fixture, quindi l'agente non ha mai realmente bisogno di richiamare memoria.
- **Modifica proposta:** rimuovere ogni riferimento esplicito alle preferenze dal prompt di questo task (che oggi le richiama indirettamente) e verificare, tramite due implementazioni concrete generate ("prima" e "dopo" l'aggiornamento memoria_003), che le convenzioni realmente cambino.
- **Logica:** un test di memoria deve rendere impossibile il successo senza memoria; oggi è possibile.

#### memory_003 (T5, invariato)
- **Check attuali:** esistenza file; "TypeScript"; "no-commit".
- **Problema:** "verify the old Python preference is no longer applied to new tools" non è verificato nel codice prodotto, solo a parole nel report.
- **Modifica proposta:** aggiungere un check `regex`/`command` che ispezioni il file del nuovo tool creato e confermi che sia effettivamente in TypeScript (estensione `.ts`, sintassi valida) e non Python.
- **Logica:** verificare l'artefatto concreto (il codice) invece del solo report descrittivo elimina la possibilità di "raccontare" un cambiamento mai avvenuto.

#### memory_004 (T5, invariato)
- **Check attuali:** esistenza file; "TypeScript"; "commit".
- **Problema:** è il task fallito nel run reale (timeout a 900s, 41 tool call, 10 retry) — probabile segno che il task, così com'è scritto, genera loop di incertezza nel modello senza una via di uscita chiara. Inoltre "explicitly check that no forbidden Git commit was created" non è verificabile: **non esiste un repository git nella fixture**, quindi non c'è nulla da commit-are e il vincolo è per costruzione infalsificabile.
- **Modifica proposta:** inizializzare un repository git reale nella fixture (`git init` + commit iniziale) così il vincolo negativo sia effettivamente testabile con un check `command` (`git log --oneline | wc -l` invariato); rivedere il prompt per ridurre l'ambiguità che ha causato il timeout nel run reale.
- **Logica:** un vincolo negativo ("non fare X") ha senso solo se X è materialmente possibile nell'ambiente fornito.

---

### Categoria: `subagents`

#### subagents_001 (T4, invariato)
- **Check attuali:** esistenza file; "Source"; "Conflict".
- **Problema:** "decompose into independent research streams... delegate only when it improves" non è mai verificato a livello di processo — il sistema raccoglie già eventi `subagent_start`/`subagent_end` in `telemetry.py`, ma nessun task li richiede nell'accettazione.
- **Modifica proposta:** aggiungere alla logica di scoring (non solo di questo task, ma della categoria) un requisito minimo sugli eventi di sub-agente quando l'harness dichiara la capability `"delegation"`/`"subagents"`, con fallback esplicito e trasparente per gli harness che non la supportano.
- **Logica:** un task che si chiama "subagents" dovrebbe fallire se nessun sub-agente è mai stato invocato, non solo se il report finale non contiene la parola "Conflict".

#### subagents_002 (T5, invariato)
- **Check attuali:** esistenza file; "Verified"; "Rejected".
- **Problema:** stesso limite di subagents_001, aggravato dal fatto che "critically review delegated outputs" richiede che esista effettivamente un output potenzialmente errato da rigettare — la fixture non definisce alcun input contraddittorio per la delega.
- **Modifica proposta:** fornire nella fixture due fonti di informazione in conflitto esplicito tra loro (analogamente a knowledge_003) così che "reject unsupported conclusions" abbia un referente concreto e verificabile via `regex` sul contenuto rigettato.
- **Logica:** senza un conflitto reale da risolvere, "rigetta conclusioni non supportate" non ha nulla da rigettare.

#### subagents_003 (T5, invariato)
- **Check attuali:** esistenza file; "Verification"; "Evidence".
- **Problema:** identico pattern dei due precedenti — nessuna verifica di processo, nessun conflitto reale nella fixture tra "evidence stream" e "implementation constraints stream".
- **Modifica proposta:** stesse due correzioni di subagents_001/002 applicate coerentemente a questo task, più un checklist di verifica esplicita nel prompt (analogamente a long_horizon_003) da riscontrare nel documento finale.
- **Logica:** rendere l'intera categoria `subagents` coerente internamente, non solo il singolo task.

---

### Categoria: `tool_use`

#### tool_use_001 (T3, invariato)
- **Check attuali:** esistenza file; "Authoritative"; "Decoy".
- **Problema:** è il task con l'evidenza più diretta di debolezza — risolto nel run reale con **1 tool call** e punteggio 100/100. La fixture non contiene nemmeno un file che sia plausibilmente un "decoy"; il check richiede solo che la parola compaia nel report.
- **Modifica proposta:** ingrandire sostanzialmente la struttura di cartelle (sotto-cartelle multiple, file con nomi fuorvianti tipo `FINAL_true_v2.csv` che è in realtà un dato obsoleto, un vero backup datato), e aggiungere un check `contains_any` che richieda la classificazione corretta di almeno un file decoy *specifico e noto*.
- **Logica:** questo è il caso più chiaro nell'intero catalogo di un task la cui difficoltà dichiarata (Tier 3, ma con l'obiettivo di "classificare file in base al contenuto, non al nome") è completamente vanificata dalla fixture sottostante.

#### tool_use_002 (T4, invariato)
- **Check attuali:** esistenza file; "effective"; "verified".
- **Problema:** "follow its references... resolve indirection" presuppone una catena di riferimenti tra file che nella fixture attuale è pressoché piatta (il README rimanda a poco).
- **Modifica proposta:** costruire una catena di indirizione reale di 2-3 livelli (README → file di configurazione → file di implementazione che sovrascrive un default), verificabile con un check `regex` che richieda la citazione del valore finale corretto risultante dalla catena.
- **Logica:** "risolvere l'indirezione" richiede che l'indirezione esista davvero, non solo nel nome del task.

#### tool_use_003 (T5, invariato)
- **Check attuali:** solo `python -m pytest -q` (peso 4, fatal) — nessun altro check.
- **Problema:** è tecnicamente il più solido (usa un oracolo esterno reale), ma è anche l'unico task dell'intero catalogo con un singolo check totale: non c'è verifica che la correzione sia stata "minima" come richiesto dal prompt ("fix only that file").
- **Modifica proposta:** aggiungere un check `unchanged`/`sha256` su tutti gli altri file del progetto tranne quello identificato come responsabile del bug, per verificare oggettivamente il vincolo "minimal change" oggi solo dichiarativo.
- **Logica:** è l'esempio più diretto di dove il check `unchanged` già esistente nel codice andrebbe applicato: il prompt lo richiede esplicitamente ("fix only that file") e il meccanismo per verificarlo esiste già, semplicemente non è collegato.

---

## 4. Sintesi delle priorità

Se si dovesse intervenire in ordine di impatto/costo:

1. **Collegare `unchanged`/`sha256` ai task che già dichiarano vincoli "non modificare"** (`autonomy_001`, `autonomy_003`, `coding_003`, `tool_use_002`, `tool_use_003`, `memory_004`) — zero nuovo codice, solo configurazione JSON.
2. **Aggiungere ground-truth numerico verificabile** dove oggi manca (`autonomy_001`, `autonomy_002`, `knowledge_001/002`) — richiede solo di ricalcolare un valore atteso e aggiungerlo come check.
3. **Ingrandire la fixture condivisa** (righe CSV, decoy reali, catena di indirezione, conflitti reali tra documenti) — è la modifica di maggior impatto complessivo perché sblocca miglioramenti in almeno 8 task diversi (`tool_use_001/002`, `knowledge_001/003`, `subagents_002/003`, `autonomy_001`, `coding_001`).
4. **Collegare la telemetria di sub-agenti/memoria già raccolta all'accettazione** — richiede modifiche più profonde a `evaluators.py`/`runner.py`, ma chiude sistematicamente la categoria `subagents` e parzialmente `memory`/`learning`.
5. **Rivedere la persistenza di workspace tra task della stessa catena** (`memory_*`, `learning_*`) — è il cambiamento più costoso architetturalmente, ma è l'unico modo per rendere questi task davvero probativi invece che dipendenti da una memoria esterna non dichiarata dell'harness.
