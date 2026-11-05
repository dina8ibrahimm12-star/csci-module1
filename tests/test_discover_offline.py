#!/usr/bin/env python3
"""
Offline test of src/discovery/discover.py using FAKE AWS clients.
Never contacts AWS. Run from the repo root:  py tests/test_discover_offline.py
"""
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

try:
    import botocore.exceptions as _bx  # real library if installed
    ClientError = _bx.ClientError
except ImportError:  # minimal stand-in so the test runs even without boto3
    class ClientError(Exception):
        def __init__(self, response, op):
            super().__init__(str(response))
            self.response = response
    botocore = types.ModuleType("botocore")
    exc = types.ModuleType("botocore.exceptions")
    exc.ClientError = ClientError
    boto3 = types.ModuleType("boto3")
    botocore.exceptions = exc
    sys.modules.update({"botocore": botocore, "botocore.exceptions": exc, "boto3": boto3})

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src" / "discovery"))
import discover as d  # noqa: E402


def err(code):
    return ClientError({"Error": {"Code": code}}, "op")


class Pager:
    def __init__(self, pages): self.pages = pages
    def paginate(self, **kw): return iter(self.pages)


class FakeEC2:
    def __init__(self, ssh_open):
        self.ssh_open = ssh_open
    def describe_vpcs(self): return {"Vpcs": [{"VpcId": "vpc-1", "CidrBlock": "10.0.0.0/16"}]}
    def describe_subnets(self):
        return {"Subnets": [
            {"SubnetId": "subnet-pub", "VpcId": "vpc-1", "CidrBlock": "10.0.1.0/24", "MapPublicIpOnLaunch": True},
            {"SubnetId": "subnet-priv", "VpcId": "vpc-1", "CidrBlock": "10.0.2.0/24", "MapPublicIpOnLaunch": False}]}
    def describe_route_tables(self):
        return {"RouteTables": [
            {"VpcId": "vpc-1", "Routes": [{"GatewayId": "local", "DestinationCidrBlock": "10.0.0.0/16"},
                                          {"GatewayId": "igw-1", "DestinationCidrBlock": "0.0.0.0/0"}],
             "Associations": [{"SubnetId": "subnet-pub"}]},
            {"VpcId": "vpc-1", "Routes": [{"GatewayId": "local", "DestinationCidrBlock": "10.0.0.0/16"}],
             "Associations": [{"Main": True}]}]}
    def get_paginator(self, name):
        if name == "describe_security_groups":
            ingress = [{"IpProtocol": "tcp", "FromPort": 22, "ToPort": 22,
                        "IpRanges": [{"CidrIp": "0.0.0.0/0"}]}] if self.ssh_open else []
            return Pager([{"SecurityGroups": [{"GroupId": "sg-1", "GroupName": "web", "VpcId": "vpc-1",
                "IpPermissions": ingress,
                "IpPermissionsEgress": [{"IpProtocol": "-1", "IpRanges": [{"CidrIp": "0.0.0.0/0"}]}]}]}])
        if name == "describe_instances":
            return Pager([{"Reservations": [{"Instances": [
                {"InstanceId": "i-1", "State": {"Name": "running"}, "InstanceType": "t3.micro",
                 "PublicIpAddress": "203.0.113.5", "PrivateIpAddress": "10.0.1.5", "SubnetId": "subnet-pub",
                 "VpcId": "vpc-1", "SecurityGroups": [{"GroupId": "sg-1"}],
                 "IamInstanceProfile": {"Arn": "arn:aws:iam::1:instance-profile/p"},
                 "Tags": [{"Key": "Name", "Value": "web-server"}],
                 "LaunchTime": datetime(2026, 10, 1, tzinfo=timezone.utc)},
                {"InstanceId": "i-dead", "State": {"Name": "terminated"}}]}]}])


class FakeIAM:
    def get_instance_profile(self, InstanceProfileName):
        return {"InstanceProfile": {"Roles": [{"RoleName": "AppRole"}]}}
    def get_paginator(self, name):
        if name == "list_roles":
            return Pager([{"Roles": [
                {"RoleName": "AppRole", "Path": "/", "Arn": "arn:aws:iam::1:role/AppRole", "AssumeRolePolicyDocument": {}},
                {"RoleName": "svc", "Path": "/aws-service-role/x/", "Arn": "arn:x", "AssumeRolePolicyDocument": {}},
                {"RoleName": "Broken", "Path": "/", "Arn": "arn:aws:iam::1:role/Broken", "AssumeRolePolicyDocument": {}}]}])
        if name == "list_attached_role_policies":
            return Pager([{"AttachedPolicies": []}])
        if name == "list_role_policies":
            return Pager([{"PolicyNames": ["ReadCustomerData"]}])
    def get_role_policy(self, RoleName, PolicyName):
        if RoleName == "Broken":
            raise err("AccessDenied")
        return {"PolicyDocument": {"Statement": [{"Action": "s3:GetObject"}]}}


class FakeS3:
    def list_buckets(self): return {"Buckets": [{"Name": "pub"}, {"Name": "priv"}, {"Name": "denied"}]}
    def get_bucket_tagging(self, Bucket):
        if Bucket == "denied": raise err("AccessDenied")
        if Bucket == "pub": raise err("NoSuchTagSet")
        return {"TagSet": [{"Key": "Sensitivity", "Value": "high"}]}
    def get_public_access_block(self, Bucket):
        if Bucket == "pub": raise err("NoSuchPublicAccessBlockConfiguration")
        return {"PublicAccessBlockConfiguration": {"BlockPublicAcls": True}}
    def get_bucket_policy(self, Bucket):
        if Bucket == "pub": return {"Policy": '{"Statement": []}'}
        raise err("NoSuchBucketPolicy")
    def get_bucket_policy_status(self, Bucket):
        if Bucket == "pub": return {"PolicyStatus": {"IsPublic": True}}
        raise err("NoSuchBucketPolicy")
    def get_bucket_acl(self, Bucket): return {"Grants": []}


def check(cond, msg):
    if not cond:
        print("FAIL:", msg); sys.exit(1)
    print("  ok  ", msg)


vpcs, subnets = d.discover_network(FakeEC2(False))
sn = {s["subnet_id"]: s for s in subnets}
check(sn["subnet-pub"]["has_internet_route"] is True, "public subnet has internet route")
check(sn["subnet-priv"]["has_internet_route"] is False, "private subnet has no internet route")

closed = d.discover_security_groups(FakeEC2(False))[0]
check(not any(r["direction"] == "ingress" for r in closed["rules"]), "closed SG has no ingress rules")
opened = d.discover_security_groups(FakeEC2(True))[0]
ing = [r for r in opened["rules"] if r["direction"] == "ingress"]
check(len(ing) == 1 and ing[0]["open_to_internet"] and ing[0]["from_port"] == 22, "SSH 0.0.0.0/0 flagged open_to_internet")

inst = d.discover_instances(FakeEC2(False), FakeIAM())
check(len(inst) == 1 and inst[0]["iam_role"] == "AppRole" and inst[0]["name"] == "web-server", "instance mapped to role; terminated skipped")

roles = {r["role_name"]: r for r in d.discover_roles(FakeIAM())}
check("svc" not in roles, "service-linked role skipped")
check(roles["AppRole"]["inline_policies"][0]["policy_name"] == "ReadCustomerData", "inline policy captured")
check(roles["Broken"].get("error") == "AccessDenied", "unreadable role recorded with error, no crash")

b = {x["bucket_name"]: x for x in d.discover_buckets(FakeS3())}
check(b["pub"]["is_public"] is True and b["pub"]["public_access_block"] is None, "public bucket detected")
check(b["priv"]["is_public"] is False and b["priv"]["tags"] == {"Sensitivity": "high"}, "private bucket + tags")
check(b["denied"].get("error") == "AccessDenied", "unreadable bucket recorded with error, no crash")
print("ALL OFFLINE TESTS PASSED")
