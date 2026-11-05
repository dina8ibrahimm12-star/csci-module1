# تسليم الجزء الأول (Role 1) للفريق

> الجزء ده معمول ومتجرّب على حساب AWS حقيقي (Free plan، Region **eu-north-1** ثابتة). **مفيش بيانات دخول ولا أرقام حساب في المشروع.** الأشياء الحساسة (Snapshots، رابط الطابور) بتتبعت بقناة الفريق **الخاصة**، مش GitHub.

## الحالة الحالية
- **السجلات (دايمة، متتحذفش):** bucket `csci-logs-<account>` + CloudTrail + Athena (`csci_logs`, workgroup `csci-wg`).
- **المعمل (قابل للحذف):** VPC وSG (مقفول) وEC2 `web-server` (t3.micro) ودور `AppRole` وbucketين S3 (`customer-data` حساس و`app-assets`) + Config + Flow Logs + EventBridge ثم SQS.
- **السيناريوهات الثلاثة اتجرّبت واترجّعت:** S1 فتح SSH للعالم، S2 سياسة IAM واسعة، S3 bucket عام.
- **ملفات الـ Snapshot** (بتتبعت لكم خاصةً): `baseline.json` (قبل)، `after-s1.json`، `after-s2.json`، `after-s3.json`. أمثلة وهمية في `samples/`، والشكل في `docs/snapshot-schema.md`.
- **الأحداث الحقيقية** الخام اتسجلت في `evidence-export/` (مش على GitHub). شكلها في `docs/data-model.md`.

## كل دور محتاج إيه
- **Role 3 (Security Graph):** الـ Snapshots + `docs/snapshot-schema.md` + `samples/`. بيانات "قبل/بعد" جاهزة لحساب الـ delta: `baseline` (مفيش مسار) ثم `after-s1` (مسار جديد Internet → EC2 → AppRole → S3).
- **Role 4/5 (Collector وDashboard):** الطابور `csci-change-events`. رابطه بيتبعت خاصةً. الرسائل أحداث EventBridge خام. اقروا `docs/data-model.md` (بند 3): dedupe على `event_id`، تجاهل الأحداث الفاشلة (`errorCode`)، امسحوا الرسالة بعد التخزين.
- **Role 2 (Detection):** GuardDuty وSecurity Hub **مش مدعومين افتراضيًا** في الحساب ده (نوع الحساب الجديد). AWS Config مدعوم فتقدروا تضيفوا Config rules. تفعيل GuardDuty قرار فريق مع المدرب (راجعوا شروطه وتكلفته الأول).
- **Role 6 (Remediation وTesting):** أوامر السيناريوهات في `scripts/simulate_changes.sh` (وPowerShell). كلها بتغيّر موارد حقيقية في المعمل، فبعد موافقة الفريق. الـ revert موجود لكل واحد.

## حاجات لازم تعرفوها (اتقاست، مش تخمين)
1. **أحداث IAM (سيناريو S2) ما بتوصلش للطابور.** IAM بتتسجل في `us-east-1`، والحساب ده Region ثابتة `eu-north-1`. الاكتشاف عن طريق مقارنة الـ Snapshots، أو سحب الأحداث من CloudTrail في `us-east-1`: `aws cloudtrail lookup-events --region us-east-1 --lookup-attributes AttributeKey=EventName,AttributeValue=PutRolePolicy`.
2. **CloudTrail بيسجل المحاولات الفاشلة** وبتوصل للطابور. فلازم الـ Collector يفحص `errorCode`.
3. **كل رسالة في الطابور بتتحسب محاولة استلام.** بعد 5 محاولات بتروح لطابور الأخطاء (`...-dlq`). متفضلوش تقروا من الطابور بأدوات اختبار: استخدموا الـ Collector.
4. **S3 العام اتقبل** (مفيش Block Public Access على مستوى الحساب). قرار الفريق لو عايزين يمنعوه بعد انتهاء التجارب.
5. **الـ Region ثابتة والـ Free plan بيقفل الحساب** لما الرصيد يخلص أو بعد حوالي 6 شهور. صدّروا الأدلة قبل كده.

## الدخول للحساب
كل واحد بحسابه (مفيش مشاركة بيانات دخول). ادعوهم من **AWS Settings** (حسب توثيق AWS للتجربة الجديدة)، وراجعوا الصلاحيات اللي بتتدّيها الدعوة قبل ما تعتمدوا عليها. من الـ CLI: `aws login --remote --profile csci` (جلسة مؤقتة، من غير مفاتيح دايمة). تفاصيل `docs/RUNBOOK.md`.

## التكلفة والتشغيل
- **الـ EC2 هو الوحيد اللي بيكلف باستمرار.** لو مش بيتستخدم: `aws ec2 stop-instances --instance-ids <id>` (والتشغيل: `start-instances`). الـ Config كمان بيتحاسب حسب التغييرات.
- **مفيش `terraform apply` ولا `destroy` من غير موافقة الفريق.** الحذف بيكون للمعمل بس (`infra/lab`) بعد تصدير الأدلة. **متحذفوش `infra/evidence`**: فيه السجلات (محمية بـ `prevent_destroy`).
- ملف الحالة `terraform.tfstate` عند صاحبة الجزء الأول (مش على GitHub). نسخة احتياطية خاصة.
