# /// script
# requires-python = ">=3.10"
# dependencies = ["httpx>=0.27"]
# ///
import time, json, httpx, os, hashlib, subprocess, sys


# --- Configuration ---
INBOX_URL = os.getenv("INBOX_URL", "http://localhost:8080/inbox")
#SHA = "ba571958a173624d977c949601bab53800cf695a"
SHA = "main"
RAW_URL = f"https://raw.githubusercontent.com/gegedenice/LLM-notify/{SHA}/RAG-notify-demo"
# Use current working directory for state, not script location (since script runs from temp when remote)
STATE_DIR = os.path.join(os.getcwd(), "state")
SEEN_FILE = os.path.join(STATE_DIR, "seen.txt")
os.makedirs(STATE_DIR, exist_ok=True)

def seen_ids():
    return set(open(SEEN_FILE).read().split()) if os.path.exists(SEEN_FILE) else set()
def mark_seen(msgid):
    with open(SEEN_FILE,"a") as f: f.write(msgid+"\n")

def sha(s: str) -> str: return hashlib.sha1(s.encode()).hexdigest()  # id simple

def post_announce(obj_name, path, who):
    payload = {
      "@context": ["https://www.w3.org/ns/activitystreams","https://www.w3.org/ns/prov#"],
      "type": "Announce",
      "actor": "https://smartbibl.ia/actors/runner",
      "object": {"type":"Document","id":f"urn:smartbibl:state:{obj_name}","name":obj_name,"url":f"file://{path}"},
      "prov:wasGeneratedBy": {"type":"Activity","prov:wasAssociatedWith": who}
    }
    httpx.post(INBOX_URL, headers={"Content-Type":"application/ld+json"}, json=payload, timeout=30)

def run(cmd):
    print("→", " ".join(cmd)); 
    p = subprocess.run(cmd, check=True, capture_output=True, text=True)
    print(p.stdout); 
    if p.stderr: print(p.stderr, file=sys.stderr)

def main():
    done = seen_ids()
    while True:
        msgs = httpx.get(INBOX_URL, timeout=30).json()
        for m in msgs:
            msgid = sha(json.dumps(m, sort_keys=True))
            if msgid in done: continue
            if m.get("type") != "Create": continue
            inst = m.get("instrument",{}); 
            if inst.get("action") != "index": continue
            obj = m.get("object",{})
            url = obj.get("url") or obj.get("id")
            # 1) split
            run(["uv","run","<RAW_URL>/splitter.py","--in",url,"--out","state/chunks.jsonl"])
            post_announce("chunks", "state/chunks.jsonl", f"splitter.py@{SHA}")
            # 2) embed
            run(["uv","run","<RAW_URL>/embedder.py","--in","state/chunks.jsonl","--out","state/embeddings.jsonl"])
            post_announce("embeddings", "state/embeddings.jsonl", f"embedder.py@{SHA}")
            # 3) index
            run(["uv","run","<RAW_URL>/indexer.py","--in","state/embeddings.jsonl","--out","state/index.jsonl"])
            post_announce("index", "state/index.jsonl", f"indexer.py@{SHA}")
            mark_seen(msgid); done.add(msgid)
        time.sleep(2)

if __name__ == "__main__":
    main()