# API

الأساس: `http://127.0.0.1:8001/api/v1`، والتوثيق التفاعلي عند `/docs`.

| الطريقة | المسار | الغرض |
|---|---|---|
| GET | `/health` | حالة الخدمة، `mock/ollama`، اسم النموذج، جاهزية LLM، قاعدة البيانات والوظائف |
| POST | `/files` | رفع XLSX آمنًا |
| POST | `/samples/{sales\|messy}` | تسجيل نسخة عمل من ملف تجريبي |
| GET | `/files/{id}` | بيانات المصنف والأوراق |
| GET | `/files/{id}/preview?sheet=` | معاينة وملفات الأعمدة |
| POST | `/analyses` | تشغيل الرسم حتى النهاية أو interrupt |
| POST | `/analyses/{id}/resume` | الاستئناف بربط الأعمدة |
| GET | `/analyses/{id}` | حالة التحليل من الذاكرة القصيرة أو السجل الدائم بعد إعادة التشغيل |
| GET | `/analyses` | التحليلات المحفوظة محليًا |

طلب البدء: `{file_id, sheet_name, max_iterations, column_mapping}`. جواب HITL: `{mappings: {"رمز_س": "dimension"}}`.
