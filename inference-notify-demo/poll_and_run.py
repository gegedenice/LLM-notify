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
STATE_DIR = os.path.join(os.path.dirname(__file__), "state")
SEEN_FILE = os.path.join(STATE_DIR, "seen.txt")
os.makedirs(STATE_DIR, exist_ok=True)

# --- State Management ---
def get_seen_ids():
    """Reads the set of seen message IDs from the state file."""
    if not os.path.exists(SEEN_FILE):
        return set()
    with open(SEEN_FILE, "r", encoding='utf-8') as f:
        return set(line.strip() for line in f)

def mark_as_seen(message_id):
    """Marks a message ID as seen by appending it to the state file."""
    with open(SEEN_FILE, "a", encoding='utf-8') as f:
        f.write(message_id + "\n")

def get_message_id(message: dict) -> str:
    """Computes a stable SHA1 hash for a given message dictionary."""
    return hashlib.sha1(json.dumps(message, sort_keys=True).encode()).hexdigest()

# --- Notification Helpers ---
def post_announce(object_name, file_path, generating_activity):
    """Posts an 'Announce' notification to the inbox about a generated resource."""
    base_url = INBOX_URL.rsplit('/', 1)[0]
    object_url = f"{base_url}/{STATE_DIR}/{object_name}"
    payload = {
        "@context": ["https://www.w3.org/ns/activitystreams", "https://www.w3.org/ns/prov#"],
        "type": "Announce",
        "actor": "https://smartbibl.ia/actors/inference-runner",
        "object": {
            "type": "Document",
            "id": f"urn:smartbibl:state:{object_name}",
            "name": object_name,
            "url": object_url
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
    process = subprocess.run(command, check=True, capture_output=True, text=True, encoding='utf-8')
    if process.stdout:
        print(process.stdout)
    if process.stderr:
        print(process.stderr, file=sys.stderr)
    return process.stdout

def build_inference_command(params: dict) -> list[str]:
    """
    Builds the command to execute the remote inference script from detailed
    notification parameters.
    """
    # Base command using the remote script URL
    cmd = ["uv", "run", "https://raw.githubusercontent.com/gegedenice/LLM-notify/main/inference-notify-demo/inference.py"]

    # Dynamically map all keys from the notification to command-line flags
    for key, value in params.items():
        flag = f"--{key.replace('_', '-')}"

        # For boolean flags (like --list-models), just add the flag if True
        if isinstance(value, bool) and value:
            cmd.append(flag)
        # For all other types, add the flag and its value
        elif not isinstance(value, bool):
            cmd.append(flag)
            cmd.append(str(value))

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
                    with open(result_filepath, "w", encoding='utf-8') as f:
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