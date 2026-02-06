# Token Counter - Manuale d'uso

Script per il conteggio reale dei token nella knowledge base di AIR Coach. Utilizza il SDK di Google Generative AI per contare i token esattamente come li conteggia il modello, e produce stime di costo basate sul pricing di Gemini Flash.

## Indice

- [Prerequisiti](#prerequisiti)
- [Uso rapido](#uso-rapido)
- [Opzioni](#opzioni)
- [Modalita di caricamento documenti](#modalita-di-caricamento-documenti)
- [Cache Probe](#cache-probe)
- [Output](#output)
- [Interpretazione dei risultati](#interpretazione-dei-risultati)
- [Esempi completi](#esempi-completi)
- [Risoluzione problemi](#risoluzione-problemi)

---

## Prerequisiti

1. **Python 3.7+** con il virtual environment del progetto attivato
2. **`GOOGLE_API_KEY`** configurata nel file `.env` (o come variabile d'ambiente)
3. Per la modalita S3: le variabili AWS (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `BUCKET_NAME`) devono essere configurate

Lo script non richiede dipendenze aggiuntive rispetto a quelle gia installate nel progetto.

## Uso rapido

```bash
# Dalla root del progetto (serverless-AIR-coach/)

# Conteggio da directory locale
python scripts/count_tokens.py --local ../Knowledge-AIR-Coach/docs/

# Conteggio da S3 (richiede credenziali AWS)
python scripts/count_tokens.py
```

## Opzioni

| Opzione | Tipo | Default | Descrizione |
|---------|------|---------|-------------|
| `--local <path>` | string | _(S3)_ | Percorso alla directory locale contenente i file `.md` |
| `--probe-cache` | flag | `false` | Esegue un probe per verificare se il caching implicito e attivo |
| `--model <name>` | string | da `FORCED_MODEL` o `gemini-2.0-flash` | Modello da usare per il conteggio token |

## Modalita di caricamento documenti

### Modalita locale (`--local`)

Carica tutti i file `.md` da una directory locale. Ideale per lo sviluppo e per conteggi rapidi senza accesso a S3.

```bash
python scripts/count_tokens.py --local ../Knowledge-AIR-Coach/docs/
```

Lo script:
- Cerca tutti i file `*.md` nella directory specificata
- Li ordina alfabeticamente
- Esce con errore se la directory non esiste o non contiene file `.md`

### Modalita S3 (default)

Carica i file `.md` dal bucket S3 configurato nel `.env`. Questo riflette esattamente i documenti che il sistema carica in produzione.

```bash
python scripts/count_tokens.py
```

Richiede che le seguenti variabili siano configurate:
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `BUCKET_NAME`

## Cache Probe

L'opzione `--probe-cache` invia una richiesta minimale al modello con l'intero contesto concatenato e verifica il campo `cached_content_token_count` nella risposta. Questo permette di capire se il caching implicito di Google e attivo.

```bash
python scripts/count_tokens.py --local ../Knowledge-AIR-Coach/docs/ --probe-cache
```

Il probe:
1. Concatena tutti i documenti
2. Invia al modello con il prompt "Rispondi solo: OK" e `max_output_tokens: 5`
3. Legge `usage_metadata` dalla risposta
4. Riporta: input tokens, cached tokens, output tokens e cache ratio

**Nota**: il caching implicito di Google si attiva tipicamente dopo che lo stesso contesto e stato inviato piu volte. Una singola esecuzione potrebbe non mostrare cache hits.

## Output

### Tabella documenti

Lo script produce una tabella con il dettaglio per ogni documento:

```
Document                                              Bytes     Tokens       %
--------------------------------------------------------------------------------
00 - AIR Coach.md                                     8,234      2,100    4.2%
01 - Introduzione e Contesto Generale.md             12,567      3,200    6.4%
02 - Formazione.md                                   25,890      6,500   13.0%
...
--------------------------------------------------------------------------------
TOTAL                                               198,432     50,000  100.0%
```

| Colonna | Descrizione |
|---------|-------------|
| **Document** | Nome del file |
| **Bytes** | Dimensione in byte (UTF-8) |
| **Tokens** | Conteggio reale dei token (da Google SDK) |
| **%** | Percentuale sul totale dei token |

### Stime di costo

Dopo la tabella, lo script mostra le stime di costo basate sul pricing di Gemini Flash:

```
--- Cost Estimates (Gemini Flash) ---
  Context tokens:             50,000
  Cost per request (no cache):  $0.005000
  Cost per request (cached):    $0.001250
  Savings with cache:           75%

  At 50 requests/day:
    Monthly (no cache): $    7.50
    Monthly (cached):   $    1.88
    Monthly savings:    $    5.63
```

I prezzi utilizzati sono:
- **Input (no cache)**: $0.10 / 1M token
- **Input (cached)**: $0.025 / 1M token (75% di risparmio)

Le proiezioni mensili sono calcolate per 50, 100 e 500 richieste al giorno.

### Cache Probe (opzionale)

Se attivato con `--probe-cache`:

```
--- Cache Probe ---
  Input tokens:       185,000
  Cached tokens:      150,000
  Output tokens:            2
  Cache ratio:          81.1%
  -> Implicit caching is ACTIVE
```

## Interpretazione dei risultati

### Token count totale

Il numero totale di token nel contesto statico e il dato piu importante. Questo valore viene inviato a ogni richiesta al LLM come parte del system prompt.

- **< 100K token**: contesto contenuto, costi bassi
- **100K-200K token**: contesto significativo, il caching diventa importante per contenere i costi
- **> 200K token**: contesto molto grande, valutare la riduzione dei documenti o il caricamento selettivo

### Distribuzione per documento

La colonna `%` aiuta a identificare quali documenti occupano piu spazio nel contesto. Se un documento occupa oltre il 20% del totale, potrebbe essere candidato per:
- Riassunto o semplificazione
- Caricamento condizionale (solo quando rilevante)
- Spostamento nel retrieval dinamico (RAG)

### Cache ratio

- **0%**: nessun caching attivo. Normale alla prima richiesta
- **50-80%**: caching parziale. Il contesto statico e parzialmente cachato
- **> 80%**: caching efficace. La maggior parte del contesto statico e servita dalla cache

### Proiezioni di costo

Le proiezioni assumono che ogni richiesta invii l'intero contesto statico. I costi reali includeranno anche i token di output (risposta del modello) e i token della conversazione, che non sono calcolati qui.

## Esempi completi

### Conteggio base con documenti locali

```bash
python scripts/count_tokens.py --local ../Knowledge-AIR-Coach/docs/
```

### Conteggio con modello specifico

```bash
python scripts/count_tokens.py --local ../Knowledge-AIR-Coach/docs/ --model gemini-2.0-flash
```

### Verifica completa con cache probe

```bash
python scripts/count_tokens.py --local ../Knowledge-AIR-Coach/docs/ --probe-cache
```

### Conteggio da S3 (produzione)

```bash
python scripts/count_tokens.py
```

### Conteggio da S3 con cache probe

```bash
python scripts/count_tokens.py --probe-cache
```

## Risoluzione problemi

### `Error: GOOGLE_API_KEY not set`

La variabile `GOOGLE_API_KEY` non e configurata. Verificare il file `.env` nella root del progetto o impostarla come variabile d'ambiente.

### `Error: directory '...' does not exist`

Il percorso passato a `--local` non esiste. Verificare il percorso relativo alla directory corrente (la root del progetto).

### `No documents found!`

Nessun file `.md` trovato nella directory specificata o nel bucket S3. Verificare che i file siano presenti e che le credenziali AWS siano corrette (per la modalita S3).

### `Cache probe failed: ...`

L'errore puo derivare da:
- Rate limit (429): attendere qualche secondo e riprovare
- Modello non supportato: verificare il nome del modello con `--model`
- Problemi di rete: verificare la connessione

### Rate limit durante il conteggio

L'API `count_tokens()` ha un limite di 3000 RPM (richieste per minuto). Con una knowledge base tipica (10-15 documenti) non si raggiunge mai questo limite. Se si verificano errori 429, ridurre il numero di documenti nella directory.
