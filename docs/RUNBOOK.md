# دليل التشغيل: من إنشاء الحساب لحد استخراج ملف المعلومات (Ubuntu / WSL)

> **قواعد ثابتة:**
> - مفيش أمر هنا بيتنفذ تلقائيًا. الأوامر اللي **بتنشئ أو بتغيّر** حاجة في AWS هي: `terraform apply` و`simulate_changes` (وأي حاجة بتعمليها في الـ Console). أي أمر `plan` أو `describe` أو `get` هو قراءة فقط.
> - **لا `apply` ولا `destroy` قبل ما الفريق يراجع الخطة والتكلفة ويوافق** (بند 6 و7 و`CLEANUP.md`).
> - **لا مفاتيح AWS في أي ملف ولا في GitHub ولا في الشات، ولا مشاركة كلمة سر أو كود MFA.** الطريقة هنا (`aws login`) مش بتحتاج Access Keys دايمة.
> - لو بتستخدمي Windows PowerShell بدل Ubuntu: في آخر الملف جدول ترجمة الأوامر.

## اللي لازم تعرفيه عن حسابك (التجربة الجديدة من AWS)
حسب توثيق AWS الرسمي لـ "Sign up for AWS (new)":
- **مفيش Root user ولا مستخدمين IAM للـ Console.** الحساب ملك الـ AWS Builder ID بتاعك، وبتتعمل لك صلاحيات Admin على المشروع تلقائيًا. الـ MFA والدعوات من **AWS Settings** (`settings.aws.com`).
- **الـ Region بتتحدد تلقائيًا من بلد عنوانك ومبتتغيرش.** حسابك: **Europe (Stockholm) `eu-north-1`**. كل ملفات المشروع مضبوطة عليها.
- **Free plan**: رصيد 100$ لحد 6 شهور، وAWS **بتقفل الحساب** لما الرصيد يخلص أو المدة تخلص (وقتها بتضيع الموارد والسجلات). صدّري الأدلة بدري (`CLEANUP.md`).
- خدماتنا مدعومة (S3, CloudTrail, Config, EventBridge, SQS, Athena, Glue, VPC, EC2, IAM). **لكن:** الـ Multi-Region مش مدعوم (CloudTrail عندنا بقى Region واحدة)، و**GuardDuty وSecurity Hub مش مدعومين افتراضيًا**: ده يخص Role 2، والفريق يقرر مع المدرب (التوثيق بيذكر "Activate advanced AWS features" لكن شروطه وتكلفته لازم تتراجع قبل أي ضغط).
- **حد معروف:** أحداث IAM (سيناريو S2) بتتسجل في `us-east-1`، وقاعدة EventBridge في `eu-north-1` ممكن مترصدهاش. هنختبرها في بند 8.

## 0) قبل أي حاجة في AWS (من غير حساب)
تثبيت الأدوات وفحص الملفات (من فولدر المشروع):
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python3 scripts/static_check.py
python3 tests/test_discover_offline.py
```
لازم تشوفي `ALL CHECKS PASSED` و`ALL OFFLINE TESTS PASSED`. بعدين Terraform (محتاج إنترنت لتحميل مكتبة AWS، ممكن ياخد دقايق ومبيطبعش تقدم):
```bash
mkdir -p ~/.terraform.d/plugin-cache
export TF_PLUGIN_CACHE_DIR="$HOME/.terraform.d/plugin-cache"
terraform fmt -recursive infra
(cd infra/evidence && terraform init -backend=false && terraform validate)
(cd infra/lab && terraform init -backend=false && terraform validate)
```
لازم `Success! The configuration is valid.` مرتين. ملف `.terraform.lock.hcl` اللي بيظهر **ارفعيه على GitHub**.

## 1) إنشاء الحساب (الفريق هو اللي بينشئه)
**قرارات الفريق:** مين صاحب الحساب (حساب واحد يديره شخص، والباقي يتدعوا)؟ الخطة Free ولا Paid؟ والـ Region ستوكهولم مقبولة للمشروع (اتأكدوا مع المدرب)؟ وGuardDuty وSecurity Hub هتتفعل إزاي؟

**الخطوات** (الشاشات بتتغير، اتبعي الموقع الرسمي):
1. `aws.amazon.com` > Sign up > اختاري **Sign up for AWS (new)** (لو ظهرت لك الخيارين).
2. سجّلي بجوجل أو أي طريقة تدخل بيها، واكتبي بيانات التواصل. AWS بتنشئ المشروع الأول وتحدد الـ Region.
3. اتأكدي من **Free plan** والرصيد من Billing > Credits.
4. شوفي الـ Region من `settings.aws.com` > Project > Overview > Additional info.

## 2) تأمين الحساب (مرة واحدة)
1. فعّلي **MFA** من AWS Settings (قسم الأمان / MFA).
2. ادعي زمايلك من AWS Settings > Team (بالإيميل): كل واحد بحسابه، **ومحدش يشارك بيانات دخوله**.
3. متحطيش بيانات الدخول في أي ملف، وماتعمليش IAM user بمفاتيح دايمة (متاحة للـ programmatic فقط، لكن ده بنتجنبه).

## 3) ربط الجهاز بالحساب (من غير Access Keys)
```bash
aws login --profile csci
```
- لو سألك عن الـ Region اكتبي `eu-north-1`.
- في المتصفح اختاري حساب المشروع وسجّلي بنفس طريقة دخولك. الجلسة بتتجدد تلقائيًا لحد 12 ساعة، وبعدها أعيدي الأمر.
- **لو الأمر مفتحش حسابك أو ظهر خطأ:** ابعتي الرسالة للفريق/لي، وماتجربيش طرق تانية فيها مفاتيح.

Terraform مش بيقرا بيانات `aws login` مباشرة في بعض إصداراته (مشكلة معروفة في مستودع provider AWS)، فنخلي AWS CLI هو اللي يسلّمهاله. افتحي `~/.aws/config`:
```bash
nano ~/.aws/config
```
وأضيفي في آخره (ده مجرد أمر، مفيهوش أي سر):
```
[profile csci-tf]
region = eu-north-1
credential_process = aws configure export-credentials --profile csci --format process
```
احفظي (`Ctrl+O` ثم Enter ثم `Ctrl+X`). وبعدين في **كل terminal جديد**:
```bash
source .venv/bin/activate
export AWS_PROFILE=csci-tf
export AWS_DEFAULT_REGION=eu-north-1
aws sts get-caller-identity
```
المفروض يظهر رقم حساب مشروعك (قارنيه بالموجود في Settings، **وغطيه لو هتصوّري**) ودور/هوية مش Root.

## 4) حماية التكلفة (قبل أول مورد)
1. Free plan عنده حماية ذاتية: الحساب بيتقفل لما الرصيد يخلص، فالمشكلة مش الفلوس بل **ضياع السجلات**. راجعي Billing > Credits (الرصيد وتاريخ انتهائه) وإيميلات التنبيه (50% و25% و10%).
2. اختياري: Budget من Billing > Budgets، أو `create_budget = true` و`alert_email` في `infra/lab/terraform.tfvars`.
3. أكبر البنود المحتملة: **AWS Config** (حسب عدد التغييرات) و**EC2** (لو اتفعّل) و**Flow Logs**. `terraform plan` مش بيعرض التكلفة، فراجعي صفحات الأسعار الرسمية.

## 5) فحص الحساب قبل البناء (قراءة فقط)
```bash
aws cloudtrail describe-trails
aws configservice describe-configuration-recorders
aws configservice describe-delivery-channels
```
- حساب جديد: المفروض فاضيين.
- لو في trail تحبوا تستخدموه: `create_cloudtrail = false` في `infra/evidence/terraform.tfvars`.
- لو في Config recorder **أو** delivery channel (واحد من كل نوع لكل Region): `create_config_recorder = false` في `infra/lab/terraform.tfvars`.

## 6) مرحلة الـ Evidence (السجلات الدائمة)
```bash
cd infra/evidence
terraform init
terraform plan -out tfplan
```
**راجعي الخطة مع الفريق قبل أي `apply`.** المتوقع: إضافة فقط، وصفر `to destroy`: S3 bucket للسجلات (Block Public Access + versioning + تشفير + retention)، CloudTrail Region واحدة، Glue database، Athena workgroup، وملفين SQL محليين. ممنوع تشوفي EC2 أو `0.0.0.0/0` في ingress.

بعد **موافقة الفريق على الخطة والتكلفة**:
```bash
terraform apply tfplan
terraform output
cd ../..
```
سجّلي `logs_bucket`. **خدي نسخة خاصة** من `infra/evidence/terraform.tfstate` خارج المشروع (مش على GitHub). لو `apply` فشل برسالة explicit deny/AccessDenied، انسخيها كاملة وابعتيها (ممكن سياسة من AWS للحسابات الجديدة).

## 7) مرحلة المعمل (قابلة للحذف)
```bash
cd infra/lab
cp terraform.tfvars.example terraform.tfvars
nano terraform.tfvars        # logs_bucket_name = قيمة logs_bucket من بند 6
terraform init
terraform plan -out tfplan
```
**مراجعة الخطة والتكلفة (إجباري قبل أي `apply`):**
- `create_web_server = false` يعني مفيش `aws_instance`. تأكدي.
- المتوقع: VPC وSubnet وSG (بدون ingress)، role باسم AppRole، bucketين S3 (Block Public Access مفعّل)، Config recorder + delivery channel، Flow Logs، قاعدتين EventBridge، SQS + DLQ، discovery role.
- EC2 قرار فريق: غيّري `create_web_server = true` وأعيدي `plan`. (الـ Free plan ممكن يمنع بعض أنواع الأجهزة.)

بعد **موافقة الفريق**:
```bash
terraform apply tfplan
terraform output
cd ../..
```

## 8) التحقق
**أ) Config شغال** (قراءة فقط):
```bash
aws configservice describe-configuration-recorder-status
aws configservice describe-delivery-channel-status
```
المطلوب: `recording: true` و`lastStatus: SUCCESS`، وتسليم ناجح للـ delivery channel (قد يتأخر دقايق). لو ظهر `InsufficientDeliveryPolicyException` ارجعي لبند 6.

**ب) حدث التغيير وصل.** terminal 1:
```bash
export CSCI_QUEUE_URL=$(terraform -chdir=infra/lab output -raw queue_url)
python3 src/tools/verify_pipeline.py
```
terminal 2 (⚠️ تغيير حقيقي في المعمل، بعد موافقة الفريق، ومعاه `AWS_PROFILE` و`AWS_DEFAULT_REGION` زي بند 3):
```bash
bash scripts/simulate_changes.sh s1 apply
```
بعد 1 إلى 5 دقايق تظهر `[TRAIL] AuthorizeSecurityGroupIngress ...` و`[CONFIG] ...`. بعدها **رجّعي**:
```bash
bash scripts/simulate_changes.sh s1 revert
```
جرّبي `s2` و`s3` (apply ثم revert لكل واحد).
- **s2 (IAM):** **اتقاس في حسابنا:** حدث `PutRolePolicy` ما بيوصلش للطابور ولا لـ CloudTrail بتاع `eu-north-1` ولا لـ Config، لأن IAM بتتسجل في `us-east-1`. اكتشاف S2 بيتم بمقارنة الـ Snapshots أو بالأمر: `aws cloudtrail lookup-events --region us-east-1 --lookup-attributes AttributeKey=EventName,AttributeValue=PutRolePolicy`. التفاصيل في `docs/data-model.md` (بند 8).
- **s3 (S3 عام):** ممكن AWS تمنع السياسة العامة (مثلًا إعداد على مستوى الحساب). وده آمن، والمحاولة بتتسجل. **ماتغيّريش إعدادات الحساب.**

**ج) أسماء الأحداث الحقيقية:** في Console افتحي CloudTrail > Event history (في Region المشروع)، فلتر Event source = `s3.amazonaws.com`، وشوفي `Event name` الحقيقي لـ `delete-public-access-block`. لو مش في قائمة `watched_api_events` في `infra/lab/events.tf`، ضيفيه وأعيدي plan/apply بموافقة الفريق.

## 9) استخراج ملف المعلومات (Snapshot)
```bash
python3 src/discovery/discover.py --region eu-north-1 \
  --role-arn "$(terraform -chdir=infra/lab output -raw discovery_role_arn)"
```
لو الـ assume role فشل، شغّلي من غير `--role-arn`. الناتج في `snapshots/latest.json` (ومعاه نسخة بتاريخها). خدي snapshot قبل أي سيناريو وواحد بعده. الملف فيه بيانات حسابكم: **ميترفعش على GitHub** (متجاهل تلقائيًا)، وابعتيه لزميلك بقناة الفريق الخاصة. الشكل: `docs/snapshot-schema.md` (أمثلة وهمية في `samples/`).

## 10) Athena (اختياري، بعد ~15 دقيقة من أول نشاط)
Console > Athena > workgroup `csci-wg`: شغّلي بالترتيب محتوى `athena/generated/01_create_cloudtrail_table.sql` ثم `02_create_flowlogs_table.sql` ثم استعلامات `athena/03_queries.sql`.

## 11) التنظيف
اقري `docs/CLEANUP.md` **قبل** أي حذف. الحذف بعد تصدير الأدلة وموافقة الفريق فقط.

---
## ترجمة الأوامر لـ Windows PowerShell
| Ubuntu | PowerShell |
|---|---|
| `python3 ...` | `py ...` |
| `export AWS_PROFILE=csci-tf` | `$env:AWS_PROFILE = "csci-tf"` |
| `export X=$(cmd)` | `$env:X = cmd` |
| `bash scripts/simulate_changes.sh s1 apply` | `.\scripts\simulate_changes.ps1 -Scenario s1 -Action apply` |
| `cp a b` / `nano f` | `Copy-Item a b` / `notepad f` |
