# Snapshot JSON contract (v1.0)
Produced by `src/discovery/discover.py`. One file per run + `latest.json` (git-ignored: it holds
account details; share it through the team's private channel, not public GitHub).
Examples with FAKE ids: `samples/sample-snapshot-baseline.json`, `samples/sample-snapshot-after-s1.json`.
If a role or bucket cannot be read fully, its entry has an `error` field (AWS error code) instead of details.

```
{ schema_version, snapshot_id, taken_at (UTC ISO), account_id, region,
  resources: {
    vpcs:            [{vpc_id, cidr, tags}],
    subnets:         [{subnet_id, vpc_id, cidr, map_public_ip_on_launch, has_internet_route, tags}],
    security_groups: [{group_id, name, vpc_id, tags,
                       rules: [{direction: ingress|egress, protocol ("-1"=all), from_port, to_port,
                                cidrs[], ipv6_cidrs[], source_security_groups[], open_to_internet}]}],
    ec2_instances:   [{instance_id, name, state, instance_type, public_ip, private_ip, subnet_id,
                       vpc_id, security_group_ids[], iam_role, tags, launch_time}],
    iam_roles:       [{role_name, role_arn, trust_policy,
                       attached_policies: [{policy_name, policy_arn, aws_managed, document}],
                       inline_policies:   [{policy_name, document}]}],
    s3_buckets:      [{bucket_name, tags, public_access_block, policy, policy_is_public,
                       acl_is_public, is_public}]
  } }
```
Graph hints for Role 3:
- An EC2 is **internet-facing** if: state=running AND public_ip present AND its subnet has
  `has_internet_route` AND one of its SGs has an ingress rule with `open_to_internet=true`.
- EC2 -> Role via `iam_role`; Role -> S3 via policy statements (resolve `s3:*`, `*`, bucket ARNs).
- Sensitive data = bucket tag `Sensitivity=high` (scoring input: data sensitivity from tags).
Lab baseline (EC2 exists only if `create_web_server = true`): EC2 `web-server` (SG has NO ingress), `AppRole` (read customer-data),
buckets `customer-data` (high), `app-assets` (low), logs (medium).
