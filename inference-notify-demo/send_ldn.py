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
    parser = argparse.ArgumentParser(description="Send an inference job to an LDN inbox.")
    # Connection
    parser.add_argument("--inbox", required=True, help="URL of the LDN inbox.")

    # LLM parameters (mirroring inference.py)
    parser.add_argument("--provider", required=True, help="LLM provider (e.g., 'groq', 'openai').")
    parser.add_argument("--model", required=True, help="Model name to use for inference.")
    parser.add_argument("--user-prompt", required=True, help="The prompt to send to the model.")
    parser.add_argument("--system-prompt", help="Optional system prompt.")

    # Extra options
    parser.add_argument("--options-json", help='Arbitrary options as a JSON string, e.g., \'{"temperature":0.5}\'.')
    parser.add_argument("--actor", default="https://example.org/users/cli-user", help="Actor URI for the notification.")

    args = parser.parse_args()

    # Build the 'object' part of the LDN message
    job_object = {
        "provider": args.provider,
        "model": args.model,
        "user_prompt": args.user_prompt,
    }
    if args.system_prompt:
        job_object["system_prompt"] = args.system_prompt
    if args.options_json:
        try:
            job_object["options"] = json.loads(args.options_json)
        except json.JSONDecodeError:
            print(f"Error: Invalid JSON in --options-json: {args.options_json}", file=sys.stderr)
            return 1

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

    print(f"Sending payload to {args.inbox}:")
    print(json.dumps(payload, indent=2))

    try:
        r = httpx.post(args.inbox, headers={"Content-Type": "application/ld+json"}, json=payload, timeout=30)
        r.raise_for_status()
        print("\nSent successfully. Response:", r.json())
    except httpx.RequestError as e:
        print(f"\nError sending notification: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}", file=sys.stderr)
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())