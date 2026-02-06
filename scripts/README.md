# Monitoring Fase 0 - Manuale d'uso

Sistema di monitoraggio per AIR Coach che misura token reali, stato del caching, costi e rate limit. Comprende script standalone, moduli runtime integrati nel server e un endpoint API.

## Indice

- [Panoramica](#panoramica)
- [Prerequisiti](#prerequisiti)
- [Variabili d'ambiente](#variabili-dambiente)
- [Script: count_tokens.py](#script-count_tokenspy)
- [Script: calculate_costs.py](#script-calculate_costspy)
- [Script: monitoring_report.py](#script-monitoring_reportpy)
- [Endpoint API: GET /api/monitoring](#endpoint-api-get-apimonitoring)
- [Moduli runtime](#moduli-runtime)
- [Collezioni MongoDB](#collezioni-mongodb)
- [Interpretazione dei risultati](#interpretazione-dei-risultati)
- [Risoluzione problemi](#risoluzione-problemi)

---

## Panoramica

Il sistema e composto da tre livelli:

| Livello | Componente | Scopo |
|---------|-----------|-------|
| **Script standalone** | `scripts/count_tokens.py` | Conteggio token della knowledge base (eseguibile offline) |
| **Script standalone** | `scripts/calculate_costs.py` | Calcolo costi reali dai dati raccolti in MongoDB |
| **Script standalone** | `scripts/monitoring_report.py` | Report completo con raccomandazioni |
| **Moduli runtime** | `src/monitoring/token_logger.py` | Logging automatico token per ogni richiesta |
| **Moduli runtime** | `src/monitoring/rate_limit_monitor.py` | Cattura errori 429 (rate limit) |
| **Moduli runtime** | `src/monitoring/cache_monitor.py` | Analisi metriche di cache dalle risposte LLM |
| **Moduli runtime** | `src/monitoring/dashboard.py` | Aggregazione metriche e raccomandazioni |
| **Endpoint API** | `GET /api/monitoring` | Report via HTTP (protetto da API key) |

### Flusso dati

1. Per ogni richiesta utente, `src/rag.py` misura la durata e cattura `usage_metadata` dal chunk finale tramite `StreamingHandler`
2. Nel blocco `finally`, chiama `log_token_usage()` per persistere i dati in MongoDB (`token_metrics`)
3. Se viene rilevato un errore 429, chiama `log_rate_limit_event()` per persistere l'evento in MongoDB (`rate_limit_events`)
4. Gli script e l'endpoint API interrogano queste collezioni per generare report

## Prerequisiti

1. **Python 3.7+** con il virtual environment del progetto attivato
2. **`GOOGLE_API_KEY`** configurata nel file `.env` (o come variabile d'ambiente)
3. **MongoDB Atlas** raggiungibile (per i moduli runtime e gli script di analisi)
4. Per la modalita S3 di `count_tokens.py`: le variabili AWS (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `BUCKET_NAME`) devono essere configurate

Non sono necessarie dipendenze aggiuntive rispetto a quelle gia installate nel progetto.

## Variabili d'ambiente

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `ENABLE_TOKEN_LOGGING` | `"true"` | Abilita/disabilita il logging dei token su MongoDB. Impostare a `"false"` per disabilitare |
| `MONITORING_API_KEY` | `""` | API key richiesta per accedere all'endpoint `GET /api/monitoring`. Passata nell'header `X-Monitoring-Key` |

Entrambe sono definite in `src/env.py` e leggono dal file `.env`.

---

## Script: count_tokens.py

Conteggio reale dei token nella knowledge base usando il SDK di Google Generative AI. Produce stime di costo basate sul pricing di Gemini Flash.

### Uso

```bash
# Dalla root del progetto (serverless-AIR-coach/)

# Conteggio da directory locale
python scripts/count_tokens.py --local ../Knowledge-AIR-Coach/docs/

# Conteggio da S3 (richiede credenziali AWS)
python scripts/count_tokens.py

# Con verifica cache implicito
python scripts/count_tokens.py --local ../Knowledge-AIR-Coach/docs/ --probe-cache

# Con modello specifico
python scripts/count_tokens.py --local ../Knowledge-AIR-Coach/docs/ --model gemini-2.0-flash
```

### Opzioni

| Opzione | Tipo | Default | Descrizione |
|---------|------|---------|-------------|
| `--local <path>` | string | _(S3)_ | Percorso alla directory locale contenente i file `.md` |
| `--probe-cache` | flag | `false` | Esegue un probe per verificare se il caching implicito e attivo |
| `--model <name>` | string | da `FORCED_MODEL` o `gemini-3-flash-preview` | Modello da usare per il conteggio token |

### Modalita di caricamento documenti

**Modalita locale (`--local`)**: carica tutti i file `.md` da una directory locale. Lo script cerca i file `*.md`, li ordina alfabeticamente, ed esce con errore se la directory non esiste o non contiene file `.md`. Se la directory contiene una sottodirectory `docs/`, usa quella.

**Modalita S3 (default)**: carica i file `.md` dal bucket S3 configurato nel `.env`. Riflette esattamente i documenti usati in produzione. Richiede `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `BUCKET_NAME`.

### Cache Probe

L'opzione `--probe-cache` invia una richiesta minimale al modello con l'intero contesto concatenato e verifica il campo `cached_content_token_count` nella risposta.

Il probe:
1. Concatena tutti i documenti
2. Invia al modello con il prompt "Rispondi solo: OK" e `max_output_tokens: 5`
3. Legge `usage_metadata` dalla risposta
4. Riporta: input tokens, cached tokens, output tokens e cache ratio

**Nota**: il caching implicito di Google si attiva tipicamente dopo che lo stesso contesto e stato inviato piu volte. Una singola esecuzione potrebbe non mostrare cache hits.

### Output

**Tabella documenti:**

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

**Stime di costo** (per 50, 100 e 500 richieste/giorno):

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

Prezzi: input $0.10/1M token, input cached $0.025/1M token (75% di risparmio).

**Cache Probe** (se attivato):

```
--- Cache Probe ---
  Input tokens:       185,000
  Cached tokens:      150,000
  Output tokens:            2
  Cache ratio:          81.1%
  -> Implicit caching is ACTIVE
```

---

## Script: calculate_costs.py

Interroga la collezione `token_metrics` in MongoDB e calcola costi reali, risparmi dal caching e proiezioni mensili basate sui dati di traffico effettivo.

### Uso

```bash
# Costi delle ultime 24 ore (default)
python scripts/calculate_costs.py

# Costi degli ultimi 7 giorni
python scripts/calculate_costs.py --hours 168

# Costi filtrati per utente
python scripts/calculate_costs.py --user google-oauth2|12345

# Combinazione
python scripts/calculate_costs.py --hours 72 --user google-oauth2|12345
```

### Opzioni

| Opzione | Tipo | Default | Descrizione |
|---------|------|---------|-------------|
| `--hours <n>` | int | `24` | Ore da analizzare (look-back) |
| `--user <id>` | string | _(tutti)_ | Filtra per user ID |

### Output

```
============================================================
  AIR Coach Cost Report — Last 24 hours
============================================================

--- Token Usage ---
  Total requests:              150
  Total input tokens:    27,750,000
  Total output tokens:      300,000
  Total cached tokens:   22,200,000
  Avg input/request:        185,000
  Avg output/request:         2,000

--- Latency ---
  Avg duration:             3,200 ms
  Min duration:             1,800 ms
  Max duration:             8,500 ms

--- Cache Analysis ---
  Cache hit requests:           142 (94.7%)
  Cache token ratio:           80.0%
  Caching active:               YES

--- Costs (Gemini Flash) ---
  Period cost:          $   0.2350
  Cost without cache:   $   0.3975
  Cache savings:        $   0.1625

--- Monthly Projection ---
  Projected (actual):   $   7.05
  Projected (no cache): $  11.93
  Projected savings:    $   4.88

--- Users ---
  Unique users:                  12
    google-oauth2|12345: 45 requests
    google-oauth2|67890: 30 requests
    ...
```

Il pricing usato: input $0.10/1M, output $0.40/1M, input cached $0.025/1M.

---

## Script: monitoring_report.py

Genera un report completo che aggrega tutte le metriche (token, cache, costi, rate limit) con raccomandazioni automatiche.

### Uso

```bash
# Report delle ultime 24 ore (default)
python scripts/monitoring_report.py

# Report degli ultimi 7 giorni
python scripts/monitoring_report.py --hours 168

# Output in formato JSON (per integrazione con altri tool)
python scripts/monitoring_report.py --json
```

### Opzioni

| Opzione | Tipo | Default | Descrizione |
|---------|------|---------|-------------|
| `--hours <n>` | int | `24` | Ore da analizzare |
| `--json` | flag | `false` | Output in formato JSON invece del formato leggibile |

### Output

```
============================================================
  AIR Coach Monitoring Report
  Period: last 24 hours
  Generated: 2025-01-15T10:30:00+00:00
============================================================

--- Token Usage ---
  Total requests:              150
  Total input tokens:    27,750,000
  Total output tokens:      300,000
  Avg input/request:        185,000
  Avg output/request:         2,000
  Avg duration:           3,200.0 ms

--- Cache Analysis ---
  Caching active:               YES
  Cache hit requests:           142
  Cache hit rate:              94.7%
  Avg cache ratio:             80.0%
  Total cached tokens:   22,200,000

--- Cost Analysis ---
  Period cost:          $   0.2350
  Cost without cache:   $   0.3975
  Cache savings:        $   0.1625
  Monthly projection:   $   7.05

--- Rate Limits ---
  Total events:                  0

--- Recommendations ---
  1. No issues detected. System is operating normally.
```

### Raccomandazioni automatiche

Il report genera raccomandazioni basate sui dati:

| Condizione | Raccomandazione |
|------------|-----------------|
| Caching non attivo | Suggerisce di abilitare il caching esplicito |
| Cache ratio < 30% | Suggerisce caching per il system prompt statico |
| Costo mensile proiettato > $500 | Suggerisce migrazione a Vertex AI |
| Rate limit events rilevati | Suggerisce throttling delle richieste |
| Media input > 200K token | Suggerisce riduzione del contesto o caricamento selettivo |

---

## Endpoint API: GET /api/monitoring

Endpoint HTTP che restituisce lo stesso report di `monitoring_report.py` in formato JSON. Protetto da API key.

### Richiesta

```
GET /api/monitoring?hours=24
Header: X-Monitoring-Key: <MONITORING_API_KEY>
```

### Parametri

| Parametro | Tipo | Default | Vincoli | Descrizione |
|-----------|------|---------|---------|-------------|
| `hours` | int | `24` | 1-720 | Ore da analizzare |

### Autenticazione

L'endpoint richiede l'header `X-Monitoring-Key` con il valore della variabile `MONITORING_API_KEY`. Senza API key configurata (valore vuoto), l'endpoint e disabilitato e restituisce 403.

### Risposta

```json
{
  "period_hours": 24,
  "generated_at": "2025-01-15T10:30:00+00:00",
  "token_usage": {
    "total_requests": 150,
    "total_input_tokens": 27750000,
    "total_output_tokens": 300000,
    "total_tokens": 28050000,
    "avg_input_tokens": 185000,
    "avg_output_tokens": 2000,
    "avg_duration_ms": 3200.0
  },
  "cache_analysis": {
    "total_cached_tokens": 22200000,
    "cache_hit_requests": 142,
    "cache_hit_rate_percent": 94.7,
    "avg_cache_ratio_percent": 80.0,
    "caching_active": true
  },
  "cost_analysis": {
    "period_cost_usd": 0.235,
    "cost_without_cache_usd": 0.3975,
    "cache_savings_usd": 0.1625,
    "projected_monthly_usd": 7.05
  },
  "rate_limits": {
    "total_events": 0,
    "by_type": {},
    "affected_users": []
  },
  "recommendations": [
    "No issues detected. System is operating normally."
  ]
}
```

### Esempio con curl

```bash
curl -H "X-Monitoring-Key: la-tua-api-key" "https://your-domain/api/monitoring?hours=48"
```

---

## Moduli runtime

I moduli in `src/monitoring/` si integrano automaticamente nel flusso delle richieste. Non richiedono intervento manuale.

### token_logger.py

Cattura `usage_metadata` da ogni risposta LLM e la persiste nella collezione `token_metrics` di MongoDB.

**Integrazione**: `src/rag.py` chiama `log_token_usage()` nel blocco `finally` di ogni richiesta, passando i dati catturati da `StreamingHandler.get_usage_metadata()`.

**Campi catturati**:
- `input_tokens` / `prompt_token_count`
- `output_tokens` / `candidates_token_count`
- `total_tokens` / `total_token_count`
- `input_token_details.cache_read` (LangChain format, primary)
- `cached_tokens` / `cached_content_token_count`
- `request_duration_ms` (misurato con `RequestTimer`)

**Disabilitazione**: impostare `ENABLE_TOKEN_LOGGING=false` nel `.env`.

### rate_limit_monitor.py

Cattura errori HTTP 429 (rate limit) e li persiste nella collezione `rate_limit_events` di MongoDB.

**Integrazione**: `src/agent/streaming_handler.py` rileva gli errori 429 nel blocco `except` tramite `is_rate_limited()`. Se rilevato, `src/rag.py` chiama `log_rate_limit_event()` nel blocco `finally`.

**Tipo di limite rilevato automaticamente** dal messaggio di errore:
- `RPM` — requests per minute
- `TPM` — tokens per minute
- `RPD` — requests per day
- `QUOTA` — quota generica

### cache_monitor.py

Analizza le metriche di caching dalle risposte LLM (sia formato Google SDK che LangChain). Usato per logging strutturato nei log del server.

**Funzioni**:
- `log_cache_metrics(response)` — estrae e logga cache ratio da una singola risposta
- `log_request_context(user_id, model, region)` — logga il contesto della richiesta
- `analyze_cache_effectiveness(metrics_history)` — analisi aggregata su uno storico di metriche

### dashboard.py

Aggrega dati da `token_logger` e `rate_limit_monitor` in un report strutturato con raccomandazioni automatiche. Usato sia dall'endpoint API che dallo script `monitoring_report.py`.

---

## Collezioni MongoDB

### `token_metrics`

Un documento per ogni richiesta al LLM:

```json
{
  "user_id": "google-oauth2|12345",
  "model": "gemini-3-flash-preview",
  "input_tokens": 185000,
  "output_tokens": 2500,
  "total_tokens": 187500,
  "cached_tokens": 148000,
  "request_duration_ms": 3200,
  "timestamp": "2025-01-15T10:30:00Z",
  "metadata": {}
}
```

### `rate_limit_events`

Un documento per ogni errore 429 ricevuto:

```json
{
  "user_id": "google-oauth2|12345",
  "limit_type": "RPM",
  "model": "gemini-3-flash-preview",
  "error_message": "Resource exhausted: requests per minute limit...",
  "timestamp": "2025-01-15T10:30:00Z"
}
```

---

## Interpretazione dei risultati

### Token count totale

Il numero totale di token nel contesto statico e il dato piu importante. Questo valore viene inviato a ogni richiesta al LLM come parte del system prompt.

- **< 100K token**: contesto contenuto, costi bassi
- **100K-200K token**: contesto significativo, il caching diventa importante per contenere i costi
- **> 200K token**: contesto molto grande, valutare la riduzione dei documenti o il caricamento selettivo

### Distribuzione per documento

La colonna `%` di `count_tokens.py` aiuta a identificare quali documenti occupano piu spazio nel contesto. Se un documento occupa oltre il 20% del totale, potrebbe essere candidato per:
- Riassunto o semplificazione
- Caricamento condizionale (solo quando rilevante)
- Spostamento nel retrieval dinamico (RAG)

### Cache ratio

- **0%**: nessun caching attivo. Normale alla prima richiesta
- **50-80%**: caching parziale. Il contesto statico e parzialmente cachato
- **> 80%**: caching efficace. La maggior parte del contesto statico e servita dalla cache

### Proiezioni di costo

Le proiezioni di `count_tokens.py` assumono solo il contesto statico. I costi reali calcolati da `calculate_costs.py` e `monitoring_report.py` includono anche i token di output e la conversazione.

---

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

### `No token metrics found for the specified period`

Nessun dato nella collezione `token_metrics` per il periodo richiesto. Verificare che:
- `ENABLE_TOKEN_LOGGING` sia `true`
- Il server sia in esecuzione e riceva richieste
- La connessione a MongoDB sia attiva

### 403 sull'endpoint `/api/monitoring`

La API key non corrisponde. Verificare che:
- `MONITORING_API_KEY` sia configurata nel `.env` del server
- L'header `X-Monitoring-Key` nella richiesta contenga lo stesso valore
