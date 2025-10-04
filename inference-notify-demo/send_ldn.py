# /// script
# requires-python = ">=3.10"
# dependencies = ["httpx>=0.27"]
# ///
import argparse
import json
import httpx
import sys
import uuid

def main():
    parser = argparse.ArgumentParser(
        description="Send a detailed inference job to an LDN inbox, mirroring all of inference.py's arguments."
    )
    # --- Arguments for send_ldn.py
    parser.add_argument("--inbox", required=True, help="URL of the LDN inbox.")
    parser.add_argument("--actor", default="https://example.org/users/cli-user", help="Actor URI for the notification.")

    # --- Arguments mirrored from inference.py
    # Core
    parser.add_argument("--provider", required=True, help="openai | groq | ollama | hf|huggingface")
    parser.add_argument("--model", required=True, help="Model name to use for inference.")
    parser.add_argument("--base-url", help="Override base URL for the provider.")

    # Provider-specific
    parser.add_argument("--hf-subpath", help="HuggingFace router subpath (default: openai/v1)")

    # Operations
    parser.add_argument("--list-models", action="store_true", help="List available models (note: this is a client-side flag).")
    parser.add_argument("--json-output", action="store_true", help="Request raw JSON output from inference.")
    parser.add_argument("--verbose", action="store_true", help="Request verbose logs from inference.")

    # Prompts
    parser.add_argument("-u", "--user-prompt", required=True, help="User prompt text.")
    parser.add_argument("-s", "--system-prompt", help="System prompt text.")

    # Common completion options
    parser.add_argument("--temperature", type=float, help="Sampling temperature.")
    parser.add_argument("--top-p", type=float, help="Top-p sampling.")
    parser.add_argument("--max-tokens", type=int, help="Max tokens in response.")
    parser.add_argument("--stream", type=lambda v: str(v).lower() in {"1", "true", "yes"}, help="Enable streaming (bool).")

    # Reasoning effort
    parser.add_argument("--reasoning-effort", choices=["low", "medium", "high"], help="Request extra reasoning effort.")

    args = parser.parse_args()

    # Build the 'object' part of the LDN message from all provided args
    job_object = {}
    for arg, value in vars(args).items():
        # Exclude args specific to the sending script and only include args that were actually provided
        if arg not in ['inbox', 'actor'] and value is not None:
            # Convert boolean flags to a more explicit representation if they are True
            if isinstance(value, bool) and value:
                job_object[arg] = True
            elif not isinstance(value, bool):
                job_object[arg] = value

    # Build the full LDN notification payload
    payload = {
        "@context": "https://www.w3.org/ns/activitystreams",
        "id": f"urn:uuid:{uuid.uuid4()}",
        "type": "Create",
        "actor": args.actor,
        "object": job_object,
        "instrument": {
            "type": "Service",
            "action": "infer"
        }
    }

    print("--- Sending Notification ---")
    print(json.dumps(payload, indent=2))
    print("--------------------------")

    try:
        r = httpx.post(args.inbox, headers={"Content-Type": "application/ld+json"}, json=payload, timeout=30)
        r.raise_for_status()
        print("\n=> Sent successfully. Inbox response:", r.json())
    except httpx.RequestError as e:
        print(f"\n[ERROR] Failed to send notification: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"\n[ERROR] An unexpected error occurred: {e}", file=sys.stderr)
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())