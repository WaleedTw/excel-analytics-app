# مطابقة المتطلبات

| المتطلب | التنفيذ |
|---|---|
| LangGraph / ثلاثة إيجنتات / حالة | `backend/app/graph.py`, `state.py`, `backend/app/agents/` |
| Checkpoint وHITL | InMemorySaver + interrupt + Command resume |
| Recovery وFallback وحد 1–5 | conditional edge من validate إلى execute/fallback |
| Ollama محلي وMock | `agent.py`؛ `llama3.2` افتراضي، وMock للاختبارات فقط |
| Pydantic وZod | `schemas.py` و`frontend/lib/schemas.ts` |
| FastAPI وNext/TypeScript | `backend/app/main.py`, `frontend/app` |
| ECharts وTanStack | `chart-card.tsx`, `data-table.tsx` |
| Data Loader وopenpyxl/pandas/DuckDB | XLSX وCSV موحدان وتحليل حتمي |
| PostgreSQL/SQLite | Docker Compose + SQLite fallback |
| تحليل خلفي وحالة فعلية | `AnalysisService` + polling عبر `/analyses/{id}` |
| أمان الرفع | الامتداد، MIME، الحجم، الاسم، المسار، توقيع XLSX، ترميز وفاصل CSV، والأبعاد |
| واجهة عربية RTL | `lang=ar`, `dir=rtl`, نصوص عربية و`ar-SA` |
| ملفات تجريبية | `samples/مبيعات_عربية_مرتبة.xlsx`, `بيانات_غير_مرتبة.xlsx` |
| صفحات الرحلة | الرئيسية والرفع والأوراق والمعاينة والربط والتوضيح والتقدم واللوحة والتفاصيل والخطأ |
| الخصوصية والحذف | حذف ملف XLSX/CSV وسجله تلقائيًا بعد انتهاء المهمة، بلا سجل ملفات سابقة |
| جاهزية النموذج | `/api/v1/health` + شارة الواجهة + خطة الوكيل في شاشة التفاصيل |
| خط ثمانية | الملفات الرسمية WOFF2 مضمنة محليًا: Sans للواجهة وSerif Display للعناوين، مع نسخة الترخيص |

## قيود معروفة

- checkpoint في الذاكرة لا يستمر بعد إعادة تشغيل الخادم.
- سياق الأسئلة والحسابات المخصصة مؤقت داخل عملية الخادم ولا يصلح لتشغيل متعدد النسخ دون مخزن مشترك.
- المرشحات في النسخة الأكاديمية تعرض الخيارات وتحتفظ بالحالة؛ إعادة حساب السلاسل المرئية حسب الفلتر تحسين مستقبلي.
- يلزم تثبيت Ollama وتنزيل `llama3.2` مرة واحدة قبل العرض الحي.