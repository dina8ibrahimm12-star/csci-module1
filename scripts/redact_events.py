#!/usr/bin/env python3
"""
Redacts raw EventBridge events (CloudTrail / Config) so they can be shared or committed.

Usage:  python3 scripts/redact_events.py IN.jsonl OUT.jsonl

It replaces the account id, IP addresses, access key ids, principal ids, session names and
identity-store ids with fake values, then CHECKS that none of the original values is left in the
output. If one is left, nothing is written and the script exits with an error.
Event ids, resource ids (sg-..., i-...) and timestamps are kept so tests can de-duplicate and order.
"""
import json
import re
import sys

FAKE_ACCOUNT = "123456789012"
IPV4 = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")


def walk(o):
    if isinstance(o, dict):
        for k, v in o.items():
            yield k, v
            yield from walk(v)
    elif isinstance(o, list):
        for v in o:
            yield from walk(v)


def collect(events):
    pairs = {}  # original -> fake
    n = {"ip": 0, "key": 0, "pid": 0, "ses": 0, "ident": 0}
    for ev in events:
        for k, v in walk(ev):
            if not isinstance(v, str) or not v:
                continue
            if k in ("account", "recipientAccountId", "awsAccountId", "ownerId", "accountId") and re.fullmatch(r"\d{12}", v):
                pairs[v] = FAKE_ACCOUNT
            elif k == "sourceIPAddress" and IPV4.match(v):
                pairs[v] = "203.0.113.10"
            elif k == "accessKeyId":
                pairs[v] = "ASIA-REDACTED-%02d" % n["key"]; n["key"] += 1
            elif k == "principalId":
                role_id, _, session = v.partition(":")
                pairs[role_id] = "AROAEXAMPLEEXAMPLE%02d" % n["pid"]; n["pid"] += 1
                if session:
                    pairs[session] = "redacted-session-%d" % n["ses"]; n["ses"] += 1
            elif k in ("userId", "identityStoreArn", "identityCenterInstanceArn", "signInSessionArn"):
                pairs[v] = "redacted-identity-%d" % n["ident"]; n["ident"] += 1
            elif k == "userAgent":
                pairs[v] = "aws-cli/2 (redacted)"
    # session name also appears inside ARNs (".../AccountFullAccessRole/<session>")
    return pairs


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    src, dst = sys.argv[1], sys.argv[2]
    events = [json.loads(l) for l in open(src) if l.strip()]
    pairs = collect(events)
    text = "\n".join(json.dumps(e) for e in events)
    for orig in sorted(pairs, key=len, reverse=True):  # longest first
        text = text.replace(orig, pairs[orig])
    leftovers = [o for o in pairs if o in text]
    if leftovers:
        sys.exit(f"STOP: {len(leftovers)} sensitive value(s) still present; nothing written.")
    for line in text.splitlines():
        json.loads(line)  # still valid JSON
    open(dst, "w").write(text + "\n")
    print(f"Redacted {len(events)} events -> {dst}  ({len(pairs)} sensitive values replaced)")


if __name__ == "__main__":
    main()
