# /// script
# requires-python = ">=3.10"
# dependencies = ["httpx>=0.27"]
# ///
import time
import json
import httpx
import os
import hashlib
import subprocess
import sys
import uuid

# --- Configuration ---
INBOX_URL = os.getenv("INBOX_URL", "http://localhost:8080/inbox")
STATE_DIR = "state"
SEEN_FILE = os.path.join(STATE_DIR, "seen.txt")
os.makedirs(STATE_DIR, exist_ok=True)

# --- State Management ---
def get_seen_ids():
    """Reads the set of seen message IDs from the state file."""
    if not os.path.exists(SEEN_FILE):
        return set()
    with open(SEEN_FILE, "r") as f:
        return set(line.strip() for line in f)

def mark_as_seen(message_id):
    """Marks a message ID as seen by appending it to the state file."""
    with open(SEEN_FILE, "a") as f:
        f.write(message_id + "\n")

def get_message_id(message: dict) -> str:
    """Computes a stable SHA1 hash for a given message dictionary."""
    return hashlib.sha1(json.dumps(message, sort_keys=True).encode()).hexdigest()

# --- Notification Helpers ---
def post_announce(object_name, file_path, generating_activity):
    """Posts an 'Announce' notification to the inbox about a generated resource."""
    payload = {
        "@context": ["https://www.w3.org/ns/activitystreams", "https://www.w3.org/ns/prov#"],
        "type": "Announce",
        "actor": "https://smartbibl.ia/actors/inference-runner",
        "object": {
            "type": "Document",
            "id": f"urn:smartbibl:state:{object_name}",
            "name": object_name,
            "url": f"file://{os.path.abspath(file_path)}"
        },
        "prov:wasGeneratedBy": generating_activity
    }
    try:
        httpx.post(INBOX_URL, headers={"Content-Type": "application/ld+json"}, json=payload, timeout=30)
    except httpx.RequestError as e:
        print(f"Error sending Announce notification: {e}", file=sys.stderr)

# --- Core Logic ---
def run_command(command):
    """Executes a command, logs its output, and returns the captured stdout."""
    print(f"→ Running command: {' '.join(command)}", file=sys.stderr)
    process = subprocess.run(command, check=True, capture_output=True, text=True)
    if process.stdout:
        print(process.stdout)
    if process.stderr:
        print(process.stderr, file=sys.stderr)
    return process.stdout

def build_inference_command(params: dict) -> list[str]:
    """Builds the command to execute the inference script from notification parameters."""
    cmd = ["uv", "run", "inference.py"]
    # Required parameters
    cmd.extend(["--provider", params["provider"]])
    cmd.extend(["--model", params["model"]])
    cmd.extend(["--user-prompt", params["user_prompt"]])

    # Optional parameters
    if "system_prompt" in params:
        cmd.extend(["--system-prompt", params["system_prompt"]])

    # Pass other options via JSON
    if "options" in params and isinstance(params["options"], dict):
        cmd.extend(["--options-json", json.dumps(params["options"])])

    return cmd

def main():
    """Main polling loop to process inference notifications."""
    print(f"Orchestrator started. Polling inbox at {INBOX_URL}...", file=sys.stderr)
    seen_ids = get_seen_ids()

    while True:
        try:
            response = httpx.get(INBOX_URL, timeout=30)
            response.raise_for_status()
            messages = response.json()
        except (httpx.RequestError, json.JSONDecodeError) as e:
            print(f"Error fetching or parsing inbox: {e}", file=sys.stderr)
            time.sleep(5)
            continue

        for message in messages:
            msg_id = get_message_id(message)
            if msg_id in seen_ids:
                continue

            # Check if it's a valid inference job
            if message.get("type") == "Create" and message.get("instrument", {}).get("action") == "infer":
                print(f"Received new inference job: {msg_id}", file=sys.stderr)

                job_params = message.get("object", {})

                try:
                    # Build and run the inference command
                    command = build_inference_command(job_params)
                    result_text = run_command(command)

                    # Save the result to a file
                    result_id = str(uuid.uuid4())
                    result_filename = f"inference-result-{result_id}.txt"
                    result_filepath = os.path.join(STATE_DIR, result_filename)
                    with open(result_filepath, "w") as f:
                        f.write(result_text)

                    print(f"Inference complete. Result saved to {result_filepath}", file=sys.stderr)

                    # Announce the result
                    post_announce(
                        object_name=result_filename,
                        file_path=result_filepath,
                        generating_activity=message.get("id", f"urn:uuid:{msg_id}")
                    )

                except (KeyError, TypeError) as e:
                    print(f"ERROR: Invalid job parameters for message {msg_id}. Missing key: {e}", file=sys.stderr)
                except subprocess.CalledProcessError as e:
                    print(f"ERROR: Inference script failed for message {msg_id}:\n{e.stderr}", file=sys.stderr)
                except Exception as e:
                    print(f"An unexpected error occurred while processing message {msg_id}: {e}", file=sys.stderr)
                finally:
                    # Mark message as processed regardless of outcome to avoid retries
                    mark_as_seen(msg_id)
                    seen_ids.add(msg_id)

        time.sleep(2)

if __name__ == "__main__":
    main()