# مطابقة المتطلبات

| المتطلب | التنفيذ |
|---|---|
| LangGraph / وكيل واحد / حالة | `backend/app/graph.py`, `state.py` |
| Checkpoint وHITL | InMemorySaver + interrupt + Command resume |
| Recovery وFallback وحد 1–5 | conditional edge من validate إلى execute/fallback |
| Ollama محلي وMock | `agent.py`؛ `llama3.2` افتراضي، وMock للاختبارات فقط |
| Pydantic وZod | `schemas.py` و`frontend/lib/schemas.ts` |
| FastAPI وNext/TypeScript | `backend/app/main.py`, `frontend/app` |
| ECharts وTanStack | `chart-card.tsx`, `data-table.tsx` |
| openpyxl/pandas وDuckDB | فحص/قراءة وتحليل حتمي |
| PostgreSQL/SQLite | Docker Compose + SQLite fallback |
| Celery/Redis/Inline | Docker Compose + `jobs.py` fallback |
| أمان الرفع | الامتداد، MIME، الحجم، الاسم، المسار، التوقيع، الأوراق والأبعاد |
| واجهة عربية RTL | `lang=ar`, `dir=rtl`, نصوص عربية و`ar-SA` |
| ملفات تجريبية | `samples/مبيعات_عربية_مرتبة.xlsx`, `بيانات_غير_مرتبة.xlsx` |
| صفحات الرحلة | حالات/مسارات الرئيسية والرفع والسجل والأوراق والمعاينة والربط والتوضيح والجودة والتقدم واللوحة والتفاصيل والخطأ |
| حفظ التحليل | SQLite + JSON محلي |
| جاهزية النموذج | `/api/v1/health` + شارة الواجهة + خطة الوكيل في شاشة التفاصيل |
| خط ثمانية | الملفات الرسمية WOFF2 مضمنة محليًا: Sans للواجهة وSerif Display للعناوين، مع نسخة الترخيص |

## قيود معروفة

- checkpoint في الذاكرة لا يستمر بعد إعادة تشغيل الخادم.
- المرشحات في النسخة الأكاديمية تعرض الخيارات وتحتفظ بالحالة؛ إعادة حساب السلاسل المرئية حسب الفلتر تحسين مستقبلي.
- يلزم تثبيت Ollama وتنزيل `llama3.2` مرة واحدة قبل العرض الحي.
