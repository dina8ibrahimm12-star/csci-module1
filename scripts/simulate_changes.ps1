<#
 Windows PowerShell version of simulate_changes.sh.
 Applies / reverts the three scripted risky changes against the LAB account.
 These are REAL changes. Run only after team approval.

 Usage (from the repo root):
   .\scripts\simulate_changes.ps1 -Scenario s1 -Action apply
   .\scripts\simulate_changes.ps1 -Scenario s1 -Action revert
 Add -Yes to skip the confirmation question.
 If scripts are blocked:  powershell -ExecutionPolicy Bypass -File .\scripts\simulate_changes.ps1 ...
 Needs: AWS CLI v2, Terraform, infra\lab already applied, $env:AWS_PROFILE set.
#>
param(
  [Parameter(Mandatory = $true)][ValidateSet('s1', 's2', 's3')][string]$Scenario,
  [Parameter(Mandatory = $true)][ValidateSet('apply', 'revert')][string]$Action,
  [switch]$Yes
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$labDir = Join-Path $root 'infra/lab'

function Get-TfOutput([string]$Name) {
  $v = terraform "-chdir=$labDir" output -raw $Name
  if ($LASTEXITCODE -ne 0) { throw "terraform output '$Name' failed. Is infra/lab applied?" }
  return $v
}
function Invoke-Aws {
  & aws @args
  if ($LASTEXITCODE -ne 0) { throw "aws $($args -join ' ') failed (exit $LASTEXITCODE)" }
}
function New-JsonFile([string]$Json) {
  $f = Join-Path ([IO.Path]::GetTempPath()) ("csci-" + [guid]::NewGuid().ToString() + ".json")
  Set-Content -Path $f -Value $Json -Encoding ascii
  return $f
}

$sg     = Get-TfOutput 'web_sg_id'
$role   = Get-TfOutput 'app_role_name'
$bucket = Get-TfOutput 'customer_data_bucket'
$env:AWS_DEFAULT_REGION = Get-TfOutput 'region'

# Safety: refuse to run against any account other than the one Terraform built.
$expected = Get-TfOutput 'account_id'
$actual = (& aws sts get-caller-identity --query Account --output text)
if ($LASTEXITCODE -ne 0) { throw "Not logged in to AWS. Log in first (see docs/RUNBOOK.md)." }
if ($expected -ne $actual) { throw "STOP: current AWS account ($actual) is not the lab account ($expected)." }

if (-not $Yes) {
  $ans = Read-Host "About to run '$Scenario $Action' in account $actual. Type yes to continue"
  if ($ans -ne 'yes') { Write-Host 'Cancelled.'; exit 1 }
}

$tmp = $null
try {
  switch ("${Scenario}:${Action}") {
    's1:apply'  { Invoke-Aws ec2 authorize-security-group-ingress --group-id $sg --protocol tcp --port 22 --cidr 0.0.0.0/0 }
    's1:revert' { Invoke-Aws ec2 revoke-security-group-ingress --group-id $sg --protocol tcp --port 22 --cidr 0.0.0.0/0 }

    's2:apply' {
      $tmp = New-JsonFile '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":"s3:*","Resource":"*"}]}'
      Invoke-Aws iam put-role-policy --role-name $role --policy-name TooBroad --policy-document "file://$tmp"
    }
    's2:revert' { Invoke-Aws iam delete-role-policy --role-name $role --policy-name TooBroad }

    's3:apply' {
      Invoke-Aws s3api delete-public-access-block --bucket $bucket
      $tmp = New-JsonFile @"
{"Version":"2012-10-17","Statement":[{"Sid":"PublicRead","Effect":"Allow","Principal":"*","Action":"s3:GetObject","Resource":"arn:aws:s3:::$($bucket)/*"}]}
"@
      try { Invoke-Aws s3api put-bucket-policy --bucket $bucket --policy "file://$tmp" }
      catch { Write-Warning "Policy was rejected (probably an account-level Block Public Access). That is fine and safe; the attempt is still logged. Do NOT change account-level settings." }
    }
    's3:revert' {
      try { Invoke-Aws s3api delete-bucket-policy --bucket $bucket } catch { Write-Warning 'No bucket policy to delete.' }
      Invoke-Aws s3api put-public-access-block --bucket $bucket --public-access-block-configuration "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"
    }
  }
  Write-Host "Done: $Scenario $Action"
}
finally {
  if ($tmp -and (Test-Path $tmp)) { Remove-Item $tmp -Force }
}
