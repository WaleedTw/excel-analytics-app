# بيّنة — تحليلات Excel واضحة

«بيّنة» منصة ويب عربية تحوّل ملفات Excel إلى تقرير جودة ولوحة معلومات تفاعلية. يستخدم الباكند FastAPI وLangGraph وDuckDB، وتستخدم الواجهة Next.js. النموذج السحابي Groq يخطط للتحليل من البيانات الوصفية فقط، بينما تنفّذ Python وDuckDB جميع الحسابات الرقمية.

## التشغيل على Windows

المتطلبات: Python 3.11+ وNode.js 20+ ومفتاح Groq مجاني.

1. انسخ `.env.example` إلى ملف جديد اسمه `.env` في جذر المشروع.
2. أنشئ مفتاحًا من [Groq Console](https://console.groq.com/keys)، ثم ضعه في `.env`:

```env
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_your_key_here
```

3. افتح نافذتي CMD داخل المجلد الذي يحتوي `scripts`، ثم شغّل:

```cmd
powershell -ExecutionPolicy Bypass -File scripts\run-backend.ps1
```

```cmd
powershell -ExecutionPolicy Bypass -File scripts\run-frontend.ps1
```

- الواجهة: http://127.0.0.1:3000
- توثيق الباكند: http://127.0.0.1:8001/docs
- فحص الصحة: http://127.0.0.1:8001/api/v1/health

يجب أن يظهر في فحص الصحة `mode=groq` و`llm_ready=true`.

## النشر المجاني

الخطة الموصى بها لهذا المشروع:

- الباكند: PythonAnywhere.
- الفرونتند: Vercel.
- الذكاء الاصطناعي: Groq.

اتبع الخطوات بالترتيب في [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md). بعد النشر لا يحتاج جهازك إلى البقاء شغّالًا.

## تجربة سريعة

1. افتح الواجهة واضغط «تحليل جديد».
2. ارفع `samples\مبيعات_عربية_مرتبة.xlsx`.
3. اختر ورقة «المبيعات» وابدأ التحليل.
4. جرّب `samples\بيانات_غير_مرتبة.xlsx` لاختبار معالجة الأعمدة الملتبسة.

## الأمان والحسابات

- يقبل النظام XLSX فقط، بحد 10 م.ب، وبأسماء آمنة ومسارات داخلية عشوائية.
- تُرفع نسخة الملف إلى خادم PythonAnywhere لإجراء الحسابات.
- لا تُرسل صفوف الملف أو عينات الخلايا إلى Groq؛ تُرسل أسماء الأعمدة وأنواعها وإحصاءات جودة مجمعة فقط.
- تُراجع استجابة النموذج عبر Pydantic، وتُرفض أي إشارة إلى عمود غير موجود.
- كل مجموع ومتوسط وتجميع وقيمة شاذة ينتج من Python أو DuckDB، وليس من النموذج اللغوي.
- لا تضع مفتاح Groq في الفرونتند أو داخل GitHub؛ ضعه كمتغير سري في PythonAnywhere فقط.

## Ollama اختياري

يبقى التشغيل المحلي مدعومًا. غيّر `LLM_PROVIDER=ollama` في `.env`، ثبّت Ollama، ثم نفّذ:

```powershell
.\scripts\setup-ollama.ps1
```

## الاختبارات

على Windows:

```powershell
.\scripts\test-all.ps1
```

## البنية

```text
backend/        FastAPI + LangGraph + Pydantic + DuckDB + SQLite
frontend/       Next.js + TypeScript + Tailwind + ECharts + Zod
samples/        ملفات Excel تجريبية
data/           الرفع والتحليلات وقاعدة SQLite
docs/           التوثيق ودليل النشر
scripts/        أوامر التشغيل والفحص
```
