# التنظيف بدون فقدان سجلات التقرير

## الفكرة
- `infra/lab` = المعمل. **يتحذف** بعد التجارب.
- `infra/evidence` = السجلات (bucket + CloudTrail + Athena). **مش بيتحذف مع المعمل.**
  الـ bucket فيه `prevent_destroy` و`force_destroy = false`، يعني `terraform destroy` على الـ evidence هيفشل عمدًا.

## ما الذي يُحذف مع المعمل وما الذي يبقى
| يُحذف (infra/lab) | يبقى (infra/evidence) |
|---|---|
| VPC, SG, EC2 (لو اتفعّل), AppRole, buckets البيانات الوهمية | bucket السجلات `csci-logs-<account>` |
| Config recorder (تاريخ التسجيل يفضل في الـ bucket) | سجلات CloudTrail / Config / Flow Logs اللي اتسلّمت بالفعل |
| EventBridge + طابور SQS (أي رسائل لسه ما اتقراتش بتضيع) | CloudTrail trail، Athena workgroup وقاعدة Glue |
| إعداد Flow Logs (السجلات اللي اتكتبت تبقى) | نتائج استعلامات Athena (`athena-results/`) |

## قبل حذف المعمل (إجباري)
1. **ارجعي كل التغييرات**: `simulate_changes -Action revert` لكل من s1 وs2 وs3 اللي اتنفذوا.
2. **احفظي نسخة محلية** مما يلزم للتقرير (ومتترفعش على GitHub، فولدر `evidence-export/` متجاهل):
   ```bash
   mkdir -p evidence-export
   B=$(terraform -chdir=infra/evidence output -raw logs_bucket)
   aws s3 sync "s3://$B" evidence-export/logs     # قراءة فقط من الـ bucket
   cp snapshots/*.json evidence-export/ 2>/dev/null || true
   ```
   وصدّري نتائج استعلامات Athena (Download results CSV) ولقطات الشاشة اللي في التقرير.
3. **خدي موافقة الفريق** على الحذف.

## حذف المعمل فقط
```bash
cd infra/lab
terraform plan -destroy -out destroy.tfplan     # راجعي القائمة: لازم تكون موارد المعمل فقط
terraform apply destroy.tfplan                  # ⚠️ بعد موافقة الفريق فقط
```
(لا تشغّلي أي أمر destroy داخل `infra/evidence`.)
لو الحساب على خطة Free: AWS بتقفل الحساب لما الرصيد يخلص أو بعد المدة المحددة (6 شهور، وراجعي تاريخ الانتهاء في Billing > Credits)، وساعتها بتضيع الموارد **والسجلات**. فصدّري الأدلة بدري ومتستناش آخر لحظة.

## حذف السجلات نهائيًا (بعد قبول التقرير النهائي وتصدير الأدلة، وبموافقة الفريق والمدرب)
1. في `infra/evidence/main.tf` احذفي بلوك `lifecycle { prevent_destroy = true }` وغيّري `force_destroy = true`.
2. `terraform apply` (لتطبيق التغيير)، ثم `terraform plan -destroy` وراجعي، ثم `terraform apply` للحذف.
أو اتركي الـ bucket ينتهي تلقائيًا بعد `log_retention_days` (الافتراضي 365 يوم).

## تنبيه على ملفات الحالة (tfstate)
`terraform.tfstate` في كل فولدر هو اللي بيعرّف Terraform إيه اللي اتبنى. لو ضاع، Terraform مش هيقدر يحذف الموارد.
احتفظي بنسخة خاصة بره المشروع، ولا ترفعيها على GitHub (متجاهلة في `.gitignore`).
