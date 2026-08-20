# API

الأساس: `http://127.0.0.1:8001/api/v1`، والتوثيق التفاعلي عند `/docs`.

| الطريقة | المسار | الغرض |
|---|---|---|
| GET | `/health` | حالة الخدمة، `mock/ollama`، اسم النموذج، جاهزية LLM، قاعدة البيانات والوظائف |
| POST | `/files` | رفع XLSX آمنًا |
| POST | `/samples/{sales\|messy}` | تسجيل نسخة عمل من ملف تجريبي |
| GET | `/files/{id}` | بيانات المصنف والأوراق |
| GET | `/files/{id}/preview?sheet=` | معاينة وملفات الأعمدة |
| POST | `/analyses` | بدء مهمة تحليل خلفية وإرجاع معرّفها فورًا |
| POST | `/analyses/{id}/resume` | استئناف مهمة تنتظر توضيح ربط الأعمدة |
| GET | `/analyses/{id}` | الحالة والنسبة والمرحلة الحقيقية للمهمة الحالية |

طلب البدء: `{file_id, sheet_name, max_iterations, column_mapping}`. جواب HITL: `{mappings: {"رمز_س": "dimension"}}`.

حالات المهمة: `queued` ثم `running`، وقد تنتقل إلى `waiting_for_clarification`، وتنتهي بـ`completed` أو `completed_with_fallback` أو `failed`. لا توجد قائمة ملفات سابقة، وتُحذف نسخة XLSX وسجلها تلقائيًا عند انتهاء المهمة.