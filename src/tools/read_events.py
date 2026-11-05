#!/usr/bin/env python3
"""
Reads ALL messages currently in the change-events queue ONCE, de-duplicated, and prints a
summary. Optionally saves the raw events to a local file (for the data-model spec / report).

- Messages are NOT deleted (the Collector can still read them).
- Each message is received about once, so this does not push messages toward the dead-letter queue
  (the queue moves a message to the DLQ after 5 receives).

Usage:  python3 src/tools/read_events.py --save evidence-export/events.jsonl
"""
import argparse
import json
import os
from pathlib import Path

import boto3


def summarize(body):
    d = body.get("detail", {})
    if body.get("source") == "aws.config":
        ci = d.get("configurationItem", {})
        return f"[CONFIG ] {ci.get('resourceType')} {ci.get('resourceId')} ({d.get('messageType')})"
    who = d.get("userIdentity", {}).get("arn", "?")
    return f"[TRAIL  ] {d.get('eventName')} by {who}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--queue-url", default=os.getenv("CSCI_QUEUE_URL"))
    ap.add_argument("--region", default=os.getenv("AWS_DEFAULT_REGION", "eu-north-1"))
    ap.add_argument("--profile", help="AWS profile (default: AWS_PROFILE env var)")
    ap.add_argument("--hold", type=int, default=90, help="seconds messages stay hidden while we read")
    ap.add_argument("--save", help="write raw events (one JSON per line) to this file")
    a = ap.parse_args()
    if not a.queue_url:
        ap.error("--queue-url or CSCI_QUEUE_URL required")

    sqs = boto3.Session(profile_name=a.profile, region_name=a.region).client("sqs")
    seen, quiet_polls = {}, 0
    while quiet_polls < 2:
        r = sqs.receive_message(
            QueueUrl=a.queue_url, MaxNumberOfMessages=10, WaitTimeSeconds=5,
            VisibilityTimeout=a.hold, AttributeNames=["ApproximateReceiveCount"],
        )
        new = [m for m in r.get("Messages", []) if m["MessageId"] not in seen]
        quiet_polls = 0 if new else quiet_polls + 1
        for m in new:
            seen[m["MessageId"]] = m

    events = sorted((json.loads(m["Body"]) for m in seen.values()), key=lambda b: b.get("time", ""))
    counts = {m["MessageId"]: int(m["Attributes"]["ApproximateReceiveCount"]) for m in seen.values()}
    for ev in events:
        print(f"{ev.get('time', '?')}  {summarize(ev)}")
    print(f"\n{len(events)} unique message(s). Not deleted; they become visible again in {a.hold}s.")
    if counts and max(counts.values()) >= 4:
        print(f"WARNING: a message was received {max(counts.values())} times; 5 receives move it to the DLQ.")

    if a.save:
        p = Path(a.save)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("\n".join(json.dumps(e) for e in events) + "\n")
        print(f"Saved raw events to {p}")


if __name__ == "__main__":
    main()
