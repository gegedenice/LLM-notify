# RAG-Notify Demo

**RAG over LDN** : distributed-RAG with Json-LD normalized-notifications Hub

- Distributed and deported : plus besoin d’un “RAG monolithique”, mais une constellation de micro-services qui communiquent via notifications standardisées.

- Event-driven federated Index: les index sont toujours à jour, réactifs.
  - Chaque ressource/document expose un inbox.
  - Quand une nouvelle version est créée ou modifiée, elle envoie une Create ou Update notification.
  - Le consumer (ex. un micro-service embedder.py) reçoit la notif → re-vectorise uniquement ce qui a changé.

- De boîte noire → traçabilité native : chaque opération est notifiée et archivée.

- De format fermé → web sémantique : les notifs sont du JSON-LD, donc interopérables avec les graphes existants.

## Project structure

```
RAG-notify-demo/
 ├─ README.md
 ├─ inbox_server.py         # petite Inbox LDN (HTTP) pour le POC
 ├─ send_ldn.py             # envoi d'une notif vers l'inbox
 ├─ poll_and_run.py         # runner: lit notifs → orchestre scripts
 ├─ splitter.py             # découpe document → chunks.jsonl
 ├─ embedder.py             # chunks → embeddings.jsonl
 ├─ indexer.py              # embeddings → index.jsonl
 ├─ query.py                # question → résultats depuis index.jsonl
 ├─ examples/
 │   ├─ sample.txt
 │   └─ job.create.json     # payload LDN de départ
 └─ state/                  # sortie du POC (chunks, embeddings, index)
```

## Run

1. Launch Inbox (terminal A)
```
uv run https://raw.githubusercontent.com/gegedenice/uv-scripts/refs/heads/ba571958a173624d977c949601bab53800cf695a/RAG-demo/inbox_server.py
```

2. Send the Create notif

*In production: replace 'main' by the commit SHA

```
uv run https://raw.githubusercontent.com/gegedenice/uv-scripts/main/RAG-demo/send_ldn.py \
  --inbox http://localhost:8080/inbox \
  --payload https://raw.githubusercontent.com/gegedenice/uv-scripts/main/RAG-demo/examples/job.create.json
```

3. Launch the runner (orchestrator) (terminal B)

```
INBOX_URL=http://localhost:8080/inbox \
uv run https://raw.githubusercontent.com/gegedenice/uv-scripts/main/RAG-demo/poll_and_run.py
```

4. Query the Index

```
uv run https://raw.githubusercontent.com/gegedenice/uv-scripts/main/RAG-demo/query.py --index state/index.jsonl \
  --q "De quoi parle le document ?" --k 5
```

## English overview

This folder is a minimal, working illustration of the ideas in the paper
[Toward a Transparent, Auditable, and Distributed Architecture for LLM Tasks Using W3C Linked Data Notifications and Remote uv Scripts](https://vixra.org/pdf/2510.0040v1.pdf).
It demonstrates a distributed, notification-driven RAG pipeline where each
processing step is a micro-service triggered by W3C Linked Data Notifications
(LDN).

- **Event-driven index**: a `Create` notification with `instrument.action = "index"`
  tells the system a document changed and must be reprocessed.
- **Streaming provenance**: each step posts an `Announce` message referencing
  the generated artifact in `state/` and the activity that produced it.
- **Interoperability**: notifications are JSON-LD (ActivityStreams + PROV), easy
  to route, store, and audit across services.

## Relation to the paper

- **Create vs Announce**: The paper’s normalized event model is applied here:
  `Create` carries the job request; each processing stage returns an `Announce`
  that points to the freshly created artifact and includes provenance
  (`prov:wasGeneratedBy`).
- **Decoupling**: The inbox is a simple web endpoint; producers and consumers
  only share schemas, not code or runtimes.

## Prerequisites

- Python 3.10+
- [`uv`](https://docs.astral.sh/uv/) installed (used to run scripts and their
  declared dependencies without a local venv)
- Internet access on first run (to download Python deps and models)

## End‑to‑end flow

1) A `Create` LDN message is posted to the inbox with `instrument.action = index`
   and an `object.url` (or `object.id`) pointing to the source document.
2) The orchestrator polls the inbox and, for each unseen job, runs:
   - `splitter.py` → writes `state/chunks.jsonl`
   - `embedder.py` → writes `state/embeddings.jsonl`
   - `indexer.py` → writes `state/index.jsonl`
   After each step, it posts an `Announce` with a link to the produced file.
3) You can then query the index with `query.py`.

The `state/` directory is created in the current working directory the scripts
run from. The inbox stores incoming messages under `state/inbox/`. A
`state/seen.txt` file prevents reprocessing the same message.

## Quickstart (local)

You can use the local scripts in this folder with `uv run`.

### 1) Start the inbox (Terminal A)

```bash
uv run RAG-notify-demo/inbox_server.py
```

It listens on `http://localhost:8080`. The inbox is at `/inbox`, and the
`state/` directory is served at `/state`.

### 2) Send a Create notification (Terminal B)

Option A — use the helper sender with a hosted JSON payload:

```bash
uv run RAG-notify-demo/send_ldn.py \
  --inbox http://localhost:8080/inbox \
  --payload https://raw.githubusercontent.com/gegedenice/uv-scripts/main/RAG-demo/examples/job.create.json
```

Option B — send directly with curl (inline JSON):

```bash
curl -sS -X POST \
  -H "Content-Type: application/ld+json" \
  --data '{
    "@context": ["https://www.w3.org/ns/activitystreams"],
    "type": "Create",
    "actor": "https://smartbibl.ia/actors/publisher",
    "object": {
      "type": "Document",
      "url": "https://raw.githubusercontent.com/gegedenice/uv-scripts/main/RAG-demo/examples/Inist_RA2024.md",
      "mediaType": "text/plain",
      "name": "Sample Text"
    },
    "instrument": {"type": "Service", "name": "RAG Pipeline", "action": "index"}
  }' \
  http://localhost:8080/inbox
```

### 3) Orchestrate the pipeline (Terminal C)

Option A — use a remote runner (recommended to pin to a commit for reproducibility):

```bash
# Replace `main` with a commit SHA in production
INBOX_URL=http://localhost:8080/inbox \
uv run https://raw.githubusercontent.com/gegedenice/uv-scripts/main/RAG-demo/poll_and_run.py
```

Option B — run the steps manually (no orchestrator):

```bash
uv run RAG-notify-demo/splitter.py --in \
  https://raw.githubusercontent.com/gegedenice/uv-scripts/main/RAG-demo/examples/Inist_RA2024.md \
  --out state/chunks.jsonl --chunk-size 900

uv run RAG-notify-demo/embedder.py --in state/chunks.jsonl \
  --out state/embeddings.jsonl --model sentence-transformers/all-MiniLM-L6-v2

uv run RAG-notify-demo/indexer.py --in state/embeddings.jsonl --out state/index.jsonl
```

### 4) Query the index

```bash
uv run RAG-notify-demo/query.py --index state/index.jsonl \
  --q "What is the document about?" --k 5
```

## CLI reference (local scripts)

- `splitter.py`
  - `--in` (URL or `file://`), `--out` (file), `--chunk-size` (chars, default 900)
- `embedder.py`
  - `--in`, `--out`, `--model` (default `sentence-transformers/all-MiniLM-L6-v2`)
- `indexer.py`
  - `--in`, `--out`
- `query.py`
  - `--index`, `--q`, `--k` (default 5), `--model`
- `send_ldn.py`
  - `--inbox`, `--payload` (HTTP(S) URL to JSON)

## Message formats

Minimal `Create` request (triggers indexing):

```json
{
  "@context": ["https://www.w3.org/ns/activitystreams"],
  "type": "Create",
  "actor": "https://smartbibl.ia/actors/publisher",
  "object": {
    "type": "Document",
    "url": "https://example.org/doc.txt",
    "mediaType": "text/plain",
    "name": "Doc Title"
  },
  "instrument": {"type": "Service", "name": "RAG Pipeline", "action": "index"}
}
```

`Announce` message (emitted after each stage):

```json
{
  "@context": [
    "https://www.w3.org/ns/activitystreams",
    "https://www.w3.org/ns/prov#"
  ],
  "type": "Announce",
  "actor": "https://smartbibl.ia/actors/runner",
  "object": {
    "type": "Document",
    "id": "urn:smartbibl:state:chunks",
    "name": "chunks",
    "url": "http://localhost:8080/state/chunks.jsonl"
  },
  "prov:wasGeneratedBy": {
    "type": "Activity",
    "prov:wasAssociatedWith": "splitter.py@<COMMIT>"
  }
}
```

## State directory layout

```
state/
  inbox/                  # stored LDN messages (JSON)
  seen.txt                # ids of processed messages
  chunks.jsonl            # splitter output
  embeddings.jsonl        # embedder output
  index.jsonl             # indexer output
```

## Troubleshooting

- If `sentence-transformers` downloads are slow, the first run may take time.
- If you see HTTP errors from remote URLs, check connectivity and CORS.
- If running the orchestrator remotely, prefer pinning to a specific commit SHA
  rather than `main`.
- Delete the `state/` directory to re-run from a clean slate.

## Extending

- Swap the embedding model via `--model` in `embedder.py`.
- Change chunking via `--chunk-size` in `splitter.py`.
- Replace `indexer.py` with a real vector index (FAISS, Milvus, etc.) while
  keeping the same notification contract.

## License

This folder inherits the repository’s license (see the root `LICENSE`).