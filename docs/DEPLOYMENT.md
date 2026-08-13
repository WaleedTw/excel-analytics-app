# نشر بيّنة: PythonAnywhere + Vercel + Groq

بهذه الطريقة يعمل الموقع من السحابة ولا يحتاج جهازك إلى البقاء شغّالًا. نفّذ الخطوات بالترتيب، ولا ترفع ملف `.env` إلى GitHub.

## 1. إنشاء مفتاح Groq

1. افتح [Groq Console](https://console.groq.com/keys).
2. أنشئ مفتاح API وانسخه مؤقتًا في مكان آمن.
3. لا تضع المفتاح في كود الفرونتند أو GitHub.

## 2. رفع المشروع إلى PythonAnywhere

أنشئ حسابًا في [PythonAnywhere](https://www.pythonanywhere.com/)، ثم ارفع مجلد المشروع إلى:

```text
/home/YOURUSERNAME/excel-analytics-app
```

من تبويب **Consoles** افتح Bash ونفّذ:

```bash
mkvirtualenv bayyinah --python=python3.11
pip install -r ~/excel-analytics-app/backend/requirements.txt
```

إذا لم يتوفر الأمر `mkvirtualenv`، استخدم:

```bash
python3.11 -m venv ~/.virtualenvs/bayyinah
source ~/.virtualenvs/bayyinah/bin/activate
pip install -r ~/excel-analytics-app/backend/requirements.txt
```

## 3. إعداد أسرار الباكند

من تبويب **Files** أنشئ الملف:

```text
/home/YOURUSERNAME/excel-analytics-app/.env
```

وضع فيه القيم التالية بعد استبدال الأمثلة:

```env
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_your_real_key_here
GROQ_MODEL=llama-3.3-70b-versatile
GROQ_TIMEOUT_SECONDS=60

MAX_FILE_SIZE_MB=10
MAX_ROWS=100000
MAX_COLUMNS=200

FRONTEND_ORIGINS=https://YOUR-PROJECT.vercel.app
CORS_ORIGIN_REGEX=
```

يمكنك وضع رابط Vercel النهائي لاحقًا ثم إعادة تحميل الباكند.

## 4. إنشاء تطبيق FastAPI على PythonAnywhere

أنشئ API token من صفحة **Account** في PythonAnywhere. داخل Bash، فعّل البيئة ثم ثبّت أداة PythonAnywhere:

```bash
source ~/.virtualenvs/bayyinah/bin/activate
pip install --upgrade pythonanywhere
```

أنشئ موقع ASGI، مع استبدال `YOURUSERNAME` في الموضعين:

```bash
pa website create --domain YOURUSERNAME.pythonanywhere.com --command '/home/YOURUSERNAME/.virtualenvs/bayyinah/bin/uvicorn --app-dir /home/YOURUSERNAME/excel-analytics-app/backend --uds ${DOMAIN_SOCKET} app.main:app'
```

اختبر الرابط:

```text
https://YOURUSERNAME.pythonanywhere.com/api/v1/health
```

المتوقع: `status` يساوي `ok` و`mode` يساوي `groq` و`llm_ready` يساوي `true`.

بعد أي تعديل على الكود أو `.env` أعد تحميل الموقع:

```bash
pa website reload --domain YOURUSERNAME.pythonanywhere.com
```

> دعم ASGI/FastAPI في PythonAnywhere موصوف حاليًا كميزة تجريبية. كما أن `api.groq.com` موجود في قائمة المواقع المسموحة للحسابات المجانية وقت إعداد هذه النسخة.

## 5. نشر الفرونتند على Vercel

1. ارفع المشروع إلى مستودع GitHub خاص أو عام، مع التأكد أن `.env` غير مرفوع.
2. في [Vercel](https://vercel.com/) اختر **Add New Project** واربط المستودع.
3. اجعل **Root Directory** هو `frontend`.
4. أضف متغير البيئة:

```env
NEXT_PUBLIC_API_URL=https://YOURUSERNAME.pythonanywhere.com/api/v1
```

5. اضغط **Deploy** وانسخ الرابط النهائي، مثل:

```text
https://YOUR-PROJECT.vercel.app
```

6. ارجع إلى ملف `.env` في PythonAnywhere، واجعل `FRONTEND_ORIGINS` مطابقًا للرابط النهائي تمامًا، ثم نفّذ أمر إعادة التحميل.

إذا استخدمت نطاقًا خاصًا، أضفه أيضًا وافصل الروابط بفاصلة:

```env
FRONTEND_ORIGINS=https://YOUR-PROJECT.vercel.app,https://example.com
```

## 6. الفحص النهائي

1. افتح رابط Vercel في نافذة خاصة.
2. تأكد أن حالة Groq «متصل».
3. ارفع ملفًا تجريبيًا أقل من 10 م.ب.
4. أكمل التحليل وتأكد من ظهور اللوحة والرؤى التفصيلية.

## ملاحظات مهمة

- رابط Vercel عام؛ لا تنشره على نطاق واسع قبل إضافة تسجيل دخول إذا كانت الملفات حساسة.
- حساب Groq المجاني له حدود يومية ودقيقة. عشر تحليلات صغيرة عادة أقل بكثير من الحد، لكن الملفات ذات الأعمدة الكثيرة تستخدم رموزًا أكثر.
- الملف نفسه يُخزن ويُحلل على PythonAnywhere، لكن صفوفه لا تُرسل إلى Groq.
- لا تحذف مجلد `data` إذا كنت تريد الاحتفاظ بالتحليلات السابقة.
