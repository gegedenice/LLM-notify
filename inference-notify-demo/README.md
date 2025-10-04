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