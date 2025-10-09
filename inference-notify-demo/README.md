# Inference-Notify Demo

This demo showcases a distributed, notification-driven architecture for running LLM inference tasks. It uses a W3C Linked Data Notifications (LDN) inbox to receive jobs and an orchestrator to trigger an OpenAI-compatible inference client.

This approach decouples the requestor from the inference service, allowing for a scalable, auditable, and asynchronous AI workflow. All scripts are designed to be run remotely via `uv`, requiring no local installation. For auditability, every parameter of an inference job is stored in the notification message.

## Project Structure

```
inference-notify-demo/
 ├─ README.md
 ├─ inbox_server.py         # Simple LDN inbox server, also serves results
 ├─ poll_and_run.py         # Orchestrator: polls inbox and runs inference
 ├─ inference.py            # Universal inference client (OpenAI, Groq, etc.)
 ├─ send_ldn.py             # Client to send a detailed inference job notification
 └─ state/                  # Outputs from the demo (inbox messages, results)
```

## How to Run

You will need three separate terminals to run the full demo.

### 1. Launch the Inbox Server (Terminal A)

This server listens for incoming notifications and serves the resulting output files.

```bash
uv run https://raw.githubusercontent.com/gegedenice/LLM-notify/main/inference-notify-demo/inbox_server.py
```

It will start listening on `http://localhost:8080`. The inbox is at `/inbox`.

### 2. Send an Inference Job Notification (Terminal B)

Use the `send_ldn.py` script to construct and send a detailed job notification to the inbox. It supports all the arguments of the `inference.py` script, allowing for fine-grained control over the job.

**Basic Example:**
```bash
uv run https://raw.githubusercontent.com/gegedenice/LLM-notify/main/inference-notify-demo/send_ldn.py \
  --inbox http://localhost:8080/inbox \
  --provider "groq" \
  --model "llama3-8b-8192" \
  --user-prompt "Explain the W3C Linked Data Notifications standard in 3 sentences."
```

**Advanced Example with more parameters:**
```bash
uv run https://raw.githubusercontent.com/gegedenice/LLM-notify/main/inference-notify-demo/send_ldn.py \
  --inbox http://localhost:8080/inbox \
  --provider "groq" \
  --model "llama3-8b-8192" \
  --user-prompt "explain reranking in RAG." \
  --system-prompt "You are an expert in IA systems." \
  --temperature 0.1 \
  --max-tokens 500
```

### 3. Launch the Orchestrator (Terminal C)

The orchestrator polls the inbox, finds the new job, and executes the remote `inference.py` script, dynamically building the command from all parameters in the notification.

**Before running, ensure you have set the required API key for your chosen provider (e.g., `GROQ_API_KEY`).**

```bash
# Example for Groq
export GROQ_API_KEY="YOUR_API_KEY_HERE"

# Launch the orchestrator
INBOX_URL=http://localhost:8080/inbox \
uv run https://raw.githubusercontent.com/gegedenice/LLM-notify/main/inference-notify-demo/poll_and_run.py
```

The result will be saved as a `.txt` file in the `state/` directory, and a final "Announce" notification will be sent to the inbox. You can view the result at a URL like `http://localhost:8080/state/inference-result-....txt`.

### Production Note: Versioning

For production or stable environments, it is recommended to replace `main` in the script URLs with a specific commit SHA. This ensures that you are running a fixed, tested version of the code.

Example:
```
https://raw.githubusercontent.com/gegedenice/LLM-notify/a1b2c3d4/inference-notify-demo/inbox_server.py
```

## Relation to the paper

This demo is a working illustration of the ideas in
[Distributed AI over Normalized Notifications (LDN)](https://vixra.org/pdf/2510.0040v1.pdf):

- **Create** messages carry a complete, explicit job description (all inference
  parameters are embedded in the notification’s `object`).
- **Announce** messages are emitted when the job finishes, pointing to the
  resulting artifact in `state/` and providing provenance (via PROV).

## Prerequisites

- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/) installed
- Provider API key in environment (one of):
  - **OpenAI**: `OPENAI_API_KEY` or `LLM_API_KEY`
  - **Groq**: `GROQ_API_KEY` or `LLM_API_KEY`
  - **HuggingFace**: `HF_API_KEY`/`HUGGINGFACE_API_KEY` or `LLM_API_KEY`

## End‑to‑end flow

1) A `Create` LDN notification with `instrument.action = infer` is posted to the
   inbox. The `object` holds all CLI parameters that will be passed through to
   `inference.py` (keys with underscores become `--kebab-case` flags).
2) The orchestrator polls `/inbox`, builds a command from the `object` fields,
   and remote-runs the universal client `inference.py`.
3) The raw text result is stored under `state/inference-result-*.txt` and an
   `Announce` message is posted back to the inbox with provenance.

## Direct CLI usage of `inference.py`

You can call the client directly (bypassing notifications):

```bash
uv run inference-notify-demo/inference.py \
  --provider groq --model llama3-8b-8192 \
  -u "Explain the W3C Linked Data Notifications standard in 3 sentences." \
  --temperature 0.1 --max-tokens 300
```

List models (provider-dependent):

```bash
uv run inference-notify-demo/inference.py --provider groq --list-models
```

JSON output and reasoning effort:

```bash
uv run inference-notify-demo/inference.py \
  --provider openai --model o3-mini \
  -u "Summarize OAIS in 2 lines" \
  --reasoning-effort medium --json-output
```

Environment variables are detected automatically if `--api-key` is not set.

## `send_ldn.py` argument mapping

`send_ldn.py` mirrors the flags of `inference.py` and places them into the
notification `object`. For example:

```bash
uv run inference-notify-demo/send_ldn.py \
  --inbox http://localhost:8080/inbox \
  --provider groq --model llama3-8b-8192 \
  -u "explain reranking in RAG" \
  --system-prompt "You are an expert in IR" \
  --temperature 0.1 --max-tokens 500 --json-output
```

The orchestrator converts underscores to dashes when building flags, so
`user_prompt` becomes `--user-prompt`, `reasoning_effort` becomes
`--reasoning-effort`, etc.

## Message schema

Minimal `Create` message used by this demo:

```json
{
  "@context": "https://www.w3.org/ns/activitystreams",
  "type": "Create",
  "actor": "https://example.org/users/cli-user",
  "object": {
    "provider": "groq",
    "model": "llama3-8b-8192",
    "user_prompt": "Explain the W3C LDN standard in 3 sentences.",
    "temperature": 0.1,
    "max_tokens": 300
  },
  "instrument": {"type": "Service", "action": "infer"}
}
```

`Announce` messages posted by the orchestrator point to
`http://localhost:8080/state/inference-result-*.txt` and include
`prov:wasGeneratedBy` for auditability.

## State directory

```
state/
  inbox/                         # stored LDN messages
  seen.txt                       # processed message ids
  inference-result-<uuid>.txt    # last run output
```

## Troubleshooting

- If you see `ERROR: No API key provided`, set the appropriate env var (see
  Prerequisites) or pass `--api-key`.
- If remote execution fails, pin the script URLs to a specific commit SHA.
- Unicode issues are handled, but if you see mangled output, ensure your shell
  locale is UTF‑8.

## Reproducibility and version pinning

For production, replace `main` in any remote script URLs with a commit SHA.
This prevents accidental upgrades and ensures runs are repeatable.

## Extending

- Add providers by implementing a new loader in `inference.py`.
- Pass extra OpenAI-compatible options with `--options-json '{...}'`.
- Adjust logging with `--verbose` and structured results with `--json-output`.

## License

This folder inherits the repository’s license (see the root `LICENSE`).