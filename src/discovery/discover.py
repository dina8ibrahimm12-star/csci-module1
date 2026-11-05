#!/usr/bin/env python3
"""
Read-only AWS discovery. Produces a snapshot JSON that the Security Graph
module (role 3) consumes. Schema: docs/snapshot-schema.md

Usage:
  python src/discovery/discover.py --region eu-north-1
  python src/discovery/discover.py --role-arn arn:aws:iam::<acct>:role/csci-discovery-readonly
"""
import argparse
import json
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

SCHEMA_VERSION = "1.0"
OPEN_V4, OPEN_V6 = "0.0.0.0/0", "::/0"


def call(fn, ignore=(), default=None, **kw):
    """Call an AWS API, returning `default` for expected 'not configured' errors."""
    try:
        return fn(**kw)
    except ClientError as e:
        if e.response["Error"]["Code"] in ignore:
            return default
        raise


def tags_to_dict(tags):
    return {t["Key"]: t["Value"] for t in (tags or [])}


def make_session(region, role_arn, profile):
    base = boto3.Session(profile_name=profile, region_name=region)
    if not role_arn:
        return base
    c = base.client("sts").assume_role(
        RoleArn=role_arn, RoleSessionName="csci-discovery"
    )["Credentials"]
    return boto3.Session(
        aws_access_key_id=c["AccessKeyId"],
        aws_secret_access_key=c["SecretAccessKey"],
        aws_session_token=c["SessionToken"],
        region_name=region,
    )


def sg_rule(direction, p):
    cidrs = [r["CidrIp"] for r in p.get("IpRanges", [])]
    cidrs6 = [r["CidrIpv6"] for r in p.get("Ipv6Ranges", [])]
    return {
        "direction": direction,
        "protocol": p.get("IpProtocol"),  # "-1" = all
        "from_port": p.get("FromPort"),
        "to_port": p.get("ToPort"),
        "cidrs": cidrs,
        "ipv6_cidrs": cidrs6,
        "source_security_groups": [g["GroupId"] for g in p.get("UserIdGroupPairs", [])],
        "open_to_internet": OPEN_V4 in cidrs or OPEN_V6 in cidrs6,
    }


def discover_network(ec2):
    vpcs = [
        {"vpc_id": v["VpcId"], "cidr": v["CidrBlock"], "tags": tags_to_dict(v.get("Tags"))}
        for v in ec2.describe_vpcs()["Vpcs"]
    ]
    subnets = [
        {
            "subnet_id": s["SubnetId"],
            "vpc_id": s["VpcId"],
            "cidr": s["CidrBlock"],
            "map_public_ip_on_launch": s["MapPublicIpOnLaunch"],
            "tags": tags_to_dict(s.get("Tags")),
        }
        for s in ec2.describe_subnets()["Subnets"]
    ]
    # route tables -> which subnets have a route to an internet gateway
    route_tables = ec2.describe_route_tables()["RouteTables"]
    igw_subnets, main_igw_vpcs, explicit = set(), set(), set()
    for rt in route_tables:
        has_igw = any(
            (r.get("GatewayId") or "").startswith("igw-")
            and r.get("DestinationCidrBlock") == OPEN_V4
            for r in rt["Routes"]
        )
        for a in rt["Associations"]:
            if a.get("SubnetId"):
                explicit.add(a["SubnetId"])
                if has_igw:
                    igw_subnets.add(a["SubnetId"])
            if a.get("Main") and has_igw:
                main_igw_vpcs.add(rt["VpcId"])
    for s in subnets:
        s["has_internet_route"] = s["subnet_id"] in igw_subnets or (
            s["subnet_id"] not in explicit and s["vpc_id"] in main_igw_vpcs
        )
    return vpcs, subnets


def discover_security_groups(ec2):
    out = []
    for page in ec2.get_paginator("describe_security_groups").paginate():
        for g in page["SecurityGroups"]:
            rules = [sg_rule("ingress", p) for p in g["IpPermissions"]]
            rules += [sg_rule("egress", p) for p in g["IpPermissionsEgress"]]
            out.append({
                "group_id": g["GroupId"],
                "name": g["GroupName"],
                "vpc_id": g.get("VpcId"),
                "tags": tags_to_dict(g.get("Tags")),
                "rules": rules,
            })
    return out


def discover_instances(ec2, iam):
    out = []
    for page in ec2.get_paginator("describe_instances").paginate():
        for r in page["Reservations"]:
            for i in r["Instances"]:
                if i["State"]["Name"] in ("terminated", "shutting-down"):
                    continue
                role = None
                arn = i.get("IamInstanceProfile", {}).get("Arn")
                if arn:
                    prof = call(iam.get_instance_profile, ignore=("NoSuchEntity",),
                                InstanceProfileName=arn.split("/")[-1])
                    if prof and prof["InstanceProfile"]["Roles"]:
                        role = prof["InstanceProfile"]["Roles"][0]["RoleName"]
                tags = tags_to_dict(i.get("Tags"))
                out.append({
                    "instance_id": i["InstanceId"],
                    "name": tags.get("Name"),
                    "state": i["State"]["Name"],
                    "instance_type": i["InstanceType"],
                    "public_ip": i.get("PublicIpAddress"),
                    "private_ip": i.get("PrivateIpAddress"),
                    "subnet_id": i.get("SubnetId"),
                    "vpc_id": i.get("VpcId"),
                    "security_group_ids": [g["GroupId"] for g in i.get("SecurityGroups", [])],
                    "iam_role": role,
                    "tags": tags,
                    "launch_time": i["LaunchTime"].isoformat(),
                })
    return out


def discover_roles(iam):
    doc_cache = {}

    def managed_doc(arn):
        if arn not in doc_cache:
            p = iam.get_policy(PolicyArn=arn)["Policy"]
            doc_cache[arn] = iam.get_policy_version(
                PolicyArn=arn, VersionId=p["DefaultVersionId"]
            )["PolicyVersion"]["Document"]
        return doc_cache[arn]

    out = []
    for page in iam.get_paginator("list_roles").paginate():
        for r in page["Roles"]:
            if r["Path"].startswith("/aws-service-role/"):
                continue  # service-linked roles are noise
            name = r["RoleName"]
            try:
                out.append(_role_detail(iam, r, managed_doc))
            except ClientError as e:
                out.append({"role_name": name, "role_arn": r["Arn"],
                            "error": e.response["Error"]["Code"]})
    return out


def _role_detail(iam, r, managed_doc):
    name = r["RoleName"]
    attached = []
    for ap in iam.get_paginator("list_attached_role_policies").paginate(RoleName=name):
        for p in ap["AttachedPolicies"]:
            attached.append({
                "policy_name": p["PolicyName"],
                "policy_arn": p["PolicyArn"],
                "aws_managed": p["PolicyArn"].startswith("arn:aws:iam::aws:"),
                "document": managed_doc(p["PolicyArn"]),
            })
    inline = []
    for ip in iam.get_paginator("list_role_policies").paginate(RoleName=name):
        for pn in ip["PolicyNames"]:
            d = iam.get_role_policy(RoleName=name, PolicyName=pn)["PolicyDocument"]
            inline.append({"policy_name": pn, "document": d})
    return {
        "role_name": name,
        "role_arn": r["Arn"],
        "trust_policy": r["AssumeRolePolicyDocument"],
        "attached_policies": attached,
        "inline_policies": inline,
    }


def _bucket_detail(s3, n):
    tags = call(s3.get_bucket_tagging, ignore=("NoSuchTagSet",), Bucket=n)
    pab = call(s3.get_public_access_block,
               ignore=("NoSuchPublicAccessBlockConfiguration",), Bucket=n)
    pol = call(s3.get_bucket_policy, ignore=("NoSuchBucketPolicy",), Bucket=n)
    st = call(s3.get_bucket_policy_status, ignore=("NoSuchBucketPolicy",), Bucket=n)
    acl = call(s3.get_bucket_acl, Bucket=n)
    acl_public = any(
        g.get("Grantee", {}).get("URI", "").endswith(("/AllUsers", "/AuthenticatedUsers"))
        for g in (acl or {}).get("Grants", [])
    )
    policy_public = bool(st and st["PolicyStatus"]["IsPublic"])
    return {
        "bucket_name": n,
        "tags": tags_to_dict((tags or {}).get("TagSet")),
        "public_access_block": (pab or {}).get("PublicAccessBlockConfiguration"),
        "policy": json.loads(pol["Policy"]) if pol else None,
        "policy_is_public": policy_public,
        "acl_is_public": acl_public,
        "is_public": policy_public or acl_public,
    }


def discover_buckets(s3):
    out = []
    for b in s3.list_buckets()["Buckets"]:
        try:
            out.append(_bucket_detail(s3, b["Name"]))
        except ClientError as e:  # keep going; record why this bucket is incomplete
            out.append({"bucket_name": b["Name"], "error": e.response["Error"]["Code"]})
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--region", default=os.getenv("AWS_DEFAULT_REGION", "eu-north-1"))
    ap.add_argument("--role-arn", help="Read-only discovery role to assume (recommended)")
    ap.add_argument("--profile")
    ap.add_argument("--out-dir", default="snapshots")
    a = ap.parse_args()

    sess = make_session(a.region, a.role_arn, a.profile)
    ec2, iam, s3, sts = (sess.client(x) for x in ("ec2", "iam", "s3", "sts"))

    vpcs, subnets = discover_network(ec2)
    now = datetime.now(timezone.utc)
    snap = {
        "schema_version": SCHEMA_VERSION,
        "snapshot_id": str(uuid.uuid4()),
        "taken_at": now.isoformat(),
        "account_id": sts.get_caller_identity()["Account"],
        "region": a.region,
        "resources": {
            "vpcs": vpcs,
            "subnets": subnets,
            "security_groups": discover_security_groups(ec2),
            "ec2_instances": discover_instances(ec2, iam),
            "iam_roles": discover_roles(iam),
            "s3_buckets": discover_buckets(s3),
        },
    }

    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"snapshot-{now.strftime('%Y%m%dT%H%M%SZ')}.json"
    path.write_text(json.dumps(snap, indent=2, default=str))
    shutil.copyfile(path, out / "latest.json")

    print(f"Snapshot written: {path}")
    for k, v in snap["resources"].items():
        print(f"  {k:16} {len(v)}")


if __name__ == "__main__":
    main()
