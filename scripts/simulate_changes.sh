#!/usr/bin/env bash
# Applies / reverts the three scripted risky changes against the LAB account.
# These are REAL changes to AWS resources. Run only after team approval.
#
# Usage:  scripts/simulate_changes.sh s1|s2|s3 apply|revert [--yes]
# Windows: use scripts/simulate_changes.ps1 instead (or run this in Git Bash / WSL).
# Needs: AWS CLI v2, Terraform, `infra/lab` already applied, and in this terminal:
#   export AWS_PROFILE=csci-tf ; export AWS_DEFAULT_REGION=eu-north-1   (see docs/RUNBOOK.md step 3)
set -euo pipefail
cd "$(dirname "$0")/.."
tf() { terraform -chdir=infra/lab output -raw "$1"; }

scenario="${1:-}"; action="${2:-}"; flag="${3:-}"
case "$scenario" in s1|s2|s3) ;; *) echo "Usage: $0 s1|s2|s3 apply|revert [--yes]"; exit 1 ;; esac
case "$action" in apply|revert) ;; *) echo "Usage: $0 s1|s2|s3 apply|revert [--yes]"; exit 1 ;; esac

SG=$(tf web_sg_id); ROLE=$(tf app_role_name); BUCKET=$(tf customer_data_bucket)
export AWS_DEFAULT_REGION=$(tf region)

# Safety: refuse to run against any account other than the one Terraform built.
expected=$(tf account_id)
actual=$(aws sts get-caller-identity --query Account --output text)
if [ "$expected" != "$actual" ]; then
  echo "STOP: current AWS account ($actual) is not the lab account ($expected)."; exit 1
fi

if [ "$flag" != "--yes" ]; then
  read -r -p "About to run '$scenario $action' in account $actual. Type yes to continue: " ans
  [ "$ans" = "yes" ] || { echo "Cancelled."; exit 1; }
fi

case "$scenario:$action" in
  s1:apply)  # SSH open to the world
    aws ec2 authorize-security-group-ingress --group-id "$SG" --protocol tcp --port 22 --cidr 0.0.0.0/0 ;;
  s1:revert)
    aws ec2 revoke-security-group-ingress --group-id "$SG" --protocol tcp --port 22 --cidr 0.0.0.0/0 ;;

  s2:apply)  # over-permissive IAM: s3:* on everything
    aws iam put-role-policy --role-name "$ROLE" --policy-name TooBroad \
      --policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":"s3:*","Resource":"*"}]}' ;;
  s2:revert)
    aws iam delete-role-policy --role-name "$ROLE" --policy-name TooBroad ;;

  s3:apply)  # public bucket: remove bucket Public Access Block + public-read policy
    aws s3api delete-public-access-block --bucket "$BUCKET"
    aws s3api put-bucket-policy --bucket "$BUCKET" --policy "{\"Version\":\"2012-10-17\",\"Statement\":[{\"Sid\":\"PublicRead\",\"Effect\":\"Allow\",\"Principal\":\"*\",\"Action\":\"s3:GetObject\",\"Resource\":\"arn:aws:s3:::${BUCKET}/*\"}]}" \
      || echo "NOTE: policy was rejected (probably an account-level Block Public Access). That is fine and safe; the attempt is still logged. Do NOT change account-level settings." ;;
  s3:revert)  # tolerant: works even if apply only partly succeeded
    aws s3api delete-bucket-policy --bucket "$BUCKET" || true
    aws s3api put-public-access-block --bucket "$BUCKET" --public-access-block-configuration \
      BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true ;;
esac
echo "Done: $scenario $action"
