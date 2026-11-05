#!/usr/bin/env python3
"""
Prints change events arriving in the SQS queue (EventBridge -> SQS feed).
Prove the feed works:   python src/tools/verify_pipeline.py --queue-url <url>  (or set CSCI_QUEUE_URL)

By default messages are NOT deleted (peek mode) so the Collector can still read them.
"""
import argparse
import json
import os

import boto3


def summarize(body):
    d = body.get("detail", {})
    if body.get("source") == "aws.config":
        ci = d.get("configurationItem", {})
        return (f"[CONFIG ] {ci.get('resourceType')} {ci.get('resourceId')} "
                f"({d.get('messageType')})")
    who = d.get("userIdentity", {}).get("arn", "?")
    return f"[TRAIL  ] {d.get('eventName')} by {who} at {d.get('eventTime')}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--queue-url", default=os.getenv("CSCI_QUEUE_URL"))
    ap.add_argument("--region", default=os.getenv("AWS_DEFAULT_REGION", "eu-north-1"))
    ap.add_argument("--profile", help="AWS profile (default: AWS_PROFILE env var)")
    ap.add_argument("--delete", action="store_true", help="delete messages after printing")
    ap.add_argument("--max-polls", type=int, default=6)
    a = ap.parse_args()
    if not a.queue_url:
        ap.error("--queue-url or CSCI_QUEUE_URL required")

    sqs = boto3.Session(profile_name=a.profile, region_name=a.region).client("sqs")
    seen = 0
    for _ in range(a.max_polls):
        r = sqs.receive_message(QueueUrl=a.queue_url, MaxNumberOfMessages=10,
                                WaitTimeSeconds=10, VisibilityTimeout=5)
        for m in r.get("Messages", []):
            seen += 1
            print(summarize(json.loads(m["Body"])))
            if a.delete:
                sqs.delete_message(QueueUrl=a.queue_url, ReceiptHandle=m["ReceiptHandle"])
    print(f"Done. {seen} message(s) seen.")


if __name__ == "__main__":
    main()
