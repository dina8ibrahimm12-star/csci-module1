#!/usr/bin/env python3
"""
Offline sanity checks. Needs NO AWS account and NO network.
It is NOT a replacement for `terraform fmt` / `terraform validate` (run those too).

Run from the repo root:  py scripts/static_check.py
"""
import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
problems, notes = [], []

# Folders that are not part of the project (libraries, caches, git internals, terraform downloads)
SKIP_DIRS = {".venv", "venv", ".git", ".terraform", "node_modules", "__pycache__", "evidence-export", "snapshots"}


def rglob(pattern):
    return [p for p in ROOT.rglob(pattern) if not (set(p.relative_to(ROOT).parts) & SKIP_DIRS)]



def fail(msg):
    problems.append(msg)


def ok(msg):
    notes.append(msg)


def strip_comments(text):
    out = []
    for line in text.splitlines():
        line = re.sub(r"(^|\s)#.*$", "", line)
        out.append(line)
    return "\n".join(out)


# ---------- Terraform (per stack) ----------
for stack in sorted((ROOT / "infra").iterdir()):
    if not stack.is_dir():
        continue
    tfs = sorted(stack.glob("*.tf"))
    if not tfs:
        continue
    text = {f.name: strip_comments(f.read_text()) for f in tfs}
    allt = "\n".join(text.values())

    # braces balanced
    for name, t in text.items():
        t2 = re.sub(r'"(?:[^"\\]|\\.)*"', '""', t)
        if t2.count("{") != t2.count("}") or t2.count("[") != t2.count("]") or t2.count("(") != t2.count(")"):
            fail(f"{stack.name}/{name}: unbalanced brackets")

    declared_vars = set(re.findall(r'variable\s+"([^"]+)"', allt))
    used_vars = set(re.findall(r"\bvar\.([a-zA-Z0-9_]+)", allt))
    for v in sorted(used_vars - declared_vars):
        fail(f"{stack.name}: var.{v} used but not declared")
    for v in sorted(declared_vars - used_vars):
        notes.append(f"{stack.name}: variable '{v}' declared but unused (ok if intentional)")

    resources = set(re.findall(r'resource\s+"([^"]+)"\s+"([^"]+)"', allt))
    datas = set(re.findall(r'data\s+"([^"]+)"\s+"([^"]+)"', allt))
    # references
    for m in re.finditer(r"(?<![\w.\"])(data\.)?((?:aws|local)_[a-z0-9_]+)\.([a-zA-Z0-9_]+)", allt):
        is_data, rtype, rname = m.group(1), m.group(2), m.group(3)
        if is_data:
            if (rtype, rname) not in datas:
                fail(f"{stack.name}: reference to undefined data.{rtype}.{rname}")
        elif (rtype, rname) not in resources:
            fail(f"{stack.name}: reference to undefined {rtype}.{rname}")
    locals_declared = set()
    for blk in re.finditer(r"locals\s*\{(.*?)\n\}", allt, re.S):
        locals_declared |= set(re.findall(r"^\s*([a-z_]+)\s*=", blk.group(1), re.M))
    for l in set(re.findall(r"\blocal\.([a-zA-Z0-9_]+)", allt)) - locals_declared:
        fail(f"{stack.name}: local.{l} used but not declared in a locals block")

    # safety: no inbound rules in Terraform at all
    if re.search(r"\bingress\s*\{", allt):
        fail(f"{stack.name}: contains an inline 'ingress' block (SG must start closed)")
    if re.search(r"aws_security_group_rule|aws_vpc_security_group_ingress_rule", allt):
        fail(f"{stack.name}: contains a separate SG ingress rule resource")
    # safety: no public ACLs / policies
    if re.search(r'acl\s*=\s*"public', allt):
        fail(f"{stack.name}: public S3 ACL found")
    for pab in re.finditer(r'resource\s+"aws_s3_bucket_public_access_block"[^{]*\{(.*?)\n\}', allt, re.S):
        for key in ("block_public_acls", "block_public_policy", "ignore_public_acls", "restrict_public_buckets"):
            if not re.search(rf"{key}\s*=\s*true", pab.group(1)):
                fail(f"{stack.name}: public access block missing {key} = true")
    # credentials in provider block
    if re.search(r"access_key|secret_key|\btoken\s*=", allt):
        fail(f"{stack.name}: credentials-like attribute in .tf")
    ok(f"{stack.name}: {len(tfs)} .tf files, {len(resources)} resources, {len(declared_vars)} variables checked")

# lab specifics
lab = (ROOT / "infra/lab/compute.tf").read_text()
if "count" not in lab.split('resource "aws_instance"')[1].split("}")[0]:
    fail("lab: aws_instance has no count (EC2 must be optional)")
if not re.search(r'variable\s+"create_web_server"\s*\{[^}]*default\s*=\s*false', (ROOT / "infra/lab/variables.tf").read_text(), re.S):
    fail("lab: create_web_server must default to false")
ev = (ROOT / "infra/evidence/main.tf").read_text()
if "prevent_destroy = true" not in ev or re.search(r"force_destroy\s*=\s*true", ev):
    fail("evidence: log bucket must have prevent_destroy = true and force_destroy = false")
if re.search(r"aws_s3_bucket\"\s+\"logs\"", (ROOT / "infra/lab/storage.tf").read_text()):
    fail("lab: must not manage the log bucket")

# templatefile variables
for tpl in (ROOT / "infra/evidence/templates").glob("*.tftpl"):
    used = set(re.findall(r"(?<!\$)\$\{([a-z_]+)\}", tpl.read_text()))
    athena = (ROOT / "infra/evidence/athena.tf").read_text()
    block = re.search(rf"{re.escape(tpl.name)}\", \{{(.*?)\}}\)", athena, re.S)
    provided = set(re.findall(r"^\s*([a-z_]+)\s*=", block.group(1), re.M)) if block else set()
    for u in used - provided:
        fail(f"{tpl.name}: template variable ${{{u}}} not provided by athena.tf")

# ---------- event names ----------
ev_tf = (ROOT / "infra/lab/events.tf").read_text()
names = set(re.findall(r'"([A-Z][A-Za-z]+)"', ev_tf.split("watched_api_events")[1].split("]")[0]))
required = {"AuthorizeSecurityGroupIngress", "PutRolePolicy", "AttachRolePolicy", "PutBucketPolicy",
            "PutBucketPublicAccessBlock", "DeletePublicAccessBlock", "DeleteBucketPublicAccessBlock",
            "PutAccountPublicAccessBlock", "DeleteAccountPublicAccessBlock", "ModifySecurityGroupRules"}
for r in sorted(required - names):
    fail(f"events.tf missing event name {r}")
ok(f"events.tf watches {len(names)} API event names")

# ---------- Python / JSON / scripts ----------
for py in list((ROOT / "src").rglob("*.py")) + list((ROOT / "scripts").glob("*.py")) + list((ROOT / "tests").glob("*.py")):
    try:
        ast.parse(py.read_text(), filename=str(py))
    except SyntaxError as e:
        fail(f"python syntax error in {py.name}: {e}")
ok("python files compile")

for js in (ROOT / "samples").glob("*.json"):
    d = json.loads(js.read_text())
    for k in ("schema_version", "snapshot_id", "taken_at", "account_id", "region", "resources"):
        if k not in d:
            fail(f"{js.name}: missing '{k}'")
    for k in ("vpcs", "subnets", "security_groups", "ec2_instances", "iam_roles", "s3_buckets"):
        if k not in d.get("resources", {}):
            fail(f"{js.name}: resources.{k} missing")
ok("sample snapshots are valid JSON with the contract keys")

for sh in (ROOT / "scripts").glob("*.sh"):
    if b"\r\n" in sh.read_bytes():
        fail(f"{sh.name}: has CRLF line endings (breaks on Linux/Git Bash)")
ps = (ROOT / "scripts/simulate_changes.ps1").read_text()
if ps.count("{") != ps.count("}") or ps.count("(") != ps.count(")"):
    fail("simulate_changes.ps1: unbalanced brackets (basic check only; not run in PowerShell)")

# ---------- docs / README consistency & no auto-apply ----------
for f in list(rglob("*.md")) + list(rglob("*.sh")) + list(rglob("*.ps1")) + list(rglob("*.py")):
    if f.name == "static_check.py":
        continue
    t = f.read_text(errors="ignore")
    if "-auto-approve" in t and f.name != "README.md":
        fail(f"{f.relative_to(ROOT)}: uses -auto-approve")
    if re.search(r"terraform[^\n]*\b(apply|destroy)\b", t) and f.suffix in (".sh", ".ps1", ".py"):
        fail(f"{f.relative_to(ROOT)}: script runs terraform apply/destroy")
runbook = (ROOT / "docs/RUNBOOK.md").read_text()
readme = (ROOT / "README.md").read_text()
for needle in ("aws login", "describe-delivery-channels", "describe-delivery-channel-status",
               "MFA", "terraform plan", "الفريق"):
    if needle not in runbook:
        fail(f"RUNBOOK.md must mention '{needle}'")
for needle in ("RUNBOOK", "plan", "review", "never put aws keys", "-auto-approve"):
    if needle.lower() not in readme.lower():
        fail(f"README.md must mention '{needle}'")
steps_runbook = set(re.findall(r"^## (\d+)\)", runbook, re.M))
steps_readme = set(re.findall(r"^(\d+)\. ", readme.split("## Order of work")[1].split("## Layout")[0], re.M))
if steps_runbook != steps_readme:
    fail(f"README step numbers {sorted(steps_readme, key=int)} differ from RUNBOOK {sorted(steps_runbook, key=int)}")
for pat in ("DEPI/ministry", "حساب الوزارة"):
    for f in rglob("*"):
        if f.is_file() and f.suffix in (".md", ".tf", ".example") and pat in f.read_text(errors="ignore"):
            fail(f"{f.relative_to(ROOT)}: outdated wording '{pat}'")
evtxt = (ROOT / "infra/evidence/main.tf").read_text()
for sid in ("ConfigAclCheck", "ConfigWrite"):
    blk = evtxt.split(f'sid       = "{sid}"')[1].split("statement {")[0]
    if "aws:SourceAccount" not in blk:
        fail(f"evidence: {sid} lacks aws:SourceAccount condition")
if "aws_iam_role_policy.config_s3" not in (ROOT / "infra/lab/logging.tf").read_text().split("configuration_recorder_status")[1]:
    fail("lab: Config recorder status must depend on the role's S3 policy")
ok("docs consistent: no auto-apply, README/RUNBOOK step numbers match, Config hardening present")

# ---------- Region / account-type decisions ----------
for st in ("lab", "evidence"):
    vt = (ROOT / f"infra/{st}/variables.tf").read_text()
    if not re.search(r'variable\s+"region"\s*\{[^}]*default\s*=\s*"eu-north-1"', vt, re.S):
        fail(f"{st}: region default must be eu-north-1 (the Region AWS assigned to the project)")
if not re.search(r'variable\s+"cloudtrail_multi_region"\s*\{[^}]*default\s*=\s*false', (ROOT / "infra/evidence/variables.tf").read_text(), re.S):
    fail("evidence: cloudtrail_multi_region must default to false (new AWS experience has no multi-Region)")
if "var.cloudtrail_multi_region" not in (ROOT / "infra/evidence/main.tf").read_text():
    fail("evidence: trail must use var.cloudtrail_multi_region")
if "eu-north-1" not in runbook or "Builder ID" not in runbook:
    fail("RUNBOOK must describe the new AWS experience (Builder ID, eu-north-1)")
if re.search(r"csci-lab-admins|MFA للـ Root|AdministratorAccess|SignInLocalDevelopmentAccess", runbook):
    fail("RUNBOOK still contains instructions for the traditional account (root/IAM group)")
ok("Region eu-north-1, single-Region trail, new-AWS-experience wording verified")

# ---------- Athena SQL: partition column quoting ----------
q = (ROOT / "athena/03_queries.sql").read_text()
if re.search(r"(WHERE|AND)\s+date\s*[>=<]", q):
    fail('athena/03_queries.sql: use "date" (double quotes) in SELECT; bare date fails in Athena')
if "PARTITIONED BY (region STRING, `date` STRING)" not in (ROOT / "infra/evidence/templates/cloudtrail_table.sql.tftpl").read_text():
    fail("cloudtrail_table template: partition column must be `date` with backticks in CREATE TABLE")
for need in ("docs/data-model.md", "docs/HANDOVER.md"):
    if not (ROOT / need).exists():
        fail(f"missing {need}")
ok("Athena quoting and hand-over docs present")

# ---------- secrets & git hygiene ----------
secret_pats = [r"AKIA[0-9A-Z]{16}", r"ASIA[0-9A-Z]{16}", r"aws_secret_access_key\s*=\s*[\"'][A-Za-z0-9/+=]{20,}", r"aws_session_token\s*=\s*[\"'][A-Za-z0-9/+=]{20,}",
               r"-----BEGIN (RSA |EC )?PRIVATE KEY-----"]
for f in rglob("*"):
    if f.is_file() and f.suffix not in (".zip", ".pyc"):
        try:
            t = f.read_text(errors="ignore")
        except Exception:
            continue
        if f.name == "static_check.py":
            continue
        for p in secret_pats:
            if re.search(p, t):
                fail(f"possible secret in {f.relative_to(ROOT)} (pattern {p})")
gi = (ROOT / ".gitignore").read_text()
for must in ("*.tfstate", "**/.terraform/", "*.tfvars", "!*.tfvars.example", "*.tfplan", ".aws/", ".env", "snapshots/*.json", "athena/generated/*.sql", "evidence-export/"):
    if must not in gi:
        fail(f".gitignore missing '{must}'")
if ".terraform.lock.hcl" in [l.strip() for l in gi.splitlines() if not l.startswith("#")]:
    fail(".terraform.lock.hcl must be committed, not ignored")
import subprocess  # noqa: E402

if (ROOT / ".git").exists():
    tracked = subprocess.run(["git", "-C", str(ROOT), "ls-files"], capture_output=True, text=True).stdout.splitlines()
    bad = re.compile(r"(\.tfstate|(^|/)terraform\.tfvars$|(^|/)\.terraform/|\.tfplan$|(^|/)tfplan|(^|/)snapshots/[^/]+\.json$|"
                     r"(^|/)athena/generated/.+\.sql$|(^|/)\.env|\.pem$|(^|/)\.aws/|(^|/)evidence-export/)")
    for t in tracked:
        if bad.search(t):
            fail(f"git is tracking a file that must not be committed: {t}")
    ok(f"git tracks {len(tracked)} files, none of them state/secret/generated files")
else:
    notes.append("no .git folder yet: tracked-file check skipped (it runs after `git init`)")

print("\n".join(f"  ok   {n}" for n in notes))
if problems:
    print("\nPROBLEMS:")
    print("\n".join(f"  FAIL {p}" for p in problems))
    sys.exit(1)
print("\nALL CHECKS PASSED")
