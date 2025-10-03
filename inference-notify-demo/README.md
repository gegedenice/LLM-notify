# Inference-Notify Demo

This demo showcases a distributed, notification-driven architecture for running LLM inference tasks. It uses a W3C Linked Data Notifications (LDN) inbox to receive jobs and an orchestrator to trigger an OpenAI-compatible inference client.

This approach decouples the requestor from the inference service, allowing for asynchronous, auditable, and scalable AI workflows.

## Project Structure

```
inference-notify-demo/
 ├─ README.md
 ├─ inbox_server.py         # Simple LDN inbox server
 ├─ poll_and_run.py         # Orchestrator: polls inbox and runs inference
 ├─ inference.py            # Universal inference client (OpenAI, Groq, etc.)
 ├─ examples/
 │   └─ inference.job.json  # Sample notification payload to trigger a job
 └─ state/                  # Outputs from the demo (seen messages, results)
```

## How to Run

You will need three separate terminals to run the full demo.

### 1. Launch the Inbox Server (Terminal A)

This server listens for incoming notifications.

```bash
uv run inbox_server.py
```

It will start listening on `http://localhost:8080/inbox`.

### 2. Send an Inference Job Notification (Terminal B)

This command sends the job defined in `examples/inference.job.json` to the inbox. You can customize the `inference.job.json` file to change the provider, model, prompt, or other parameters.

```bash
uv run send_ldn.py \
  --inbox http://localhost:8080/inbox \
  --payload examples/inference.job.json
```

### 3. Launch the Orchestrator (Terminal C)

The orchestrator polls the inbox, finds the new job, and executes the `inference.py` script with the parameters from the notification.

**Before running, ensure you have set the required API key for your chosen provider (e.g., `GROQ_API_KEY`).**

```bash
# Example for Groq
export GROQ_API_KEY="YOUR_API_KEY_HERE"

# Launch the orchestrator
INBOX_URL=http://localhost:8080/inbox \
uv run poll_and_run.py
```

The orchestrator will detect the notification and run the inference. The result will be printed to the console and saved as a `.txt` file in the `state/` directory. A final "Announce" notification will be sent to the inbox, confirming the completion of the task.