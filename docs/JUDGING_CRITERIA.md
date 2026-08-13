# مطابقة معايير التحكيم

| معيار التحكيم | ما يقدمه «بيّنة» | الدليل أثناء العرض |
|---|---|---|
| Problem Statement | يحول ملفات Excel العربية غير الجاهزة إلى تقرير جودة ولوحة موثقة، ويحل غموض الأعمدة بدل التخمين | الصفحة الرئيسية + الملف المرتب وغير المرتب |
| Prompt Engineering Strategy | System Prompt عربي بقواعد دور وحدود، JSON Schema، بيانات وصفية فقط، ومعاملة نص الملف كمدخل غير موثوق | `backend/app/agent.py` و`docs/SYSTEM_PROMPT.md` |
| Tools & Agent Architecture | وكيل LangGraph ذو حالة؛ Ollama للتخطيط، openpyxl/pandas للفحص، DuckDB/Python للحساب، Pydantic للتحقق | `docs/LANGGRAPH_WORKFLOW.md` وtrace التحليل |
| Memory | checkpoint مرتبط بـ`thread_id` يحفظ حالة المقاطعة، وSQLite/JSON يحفظان اللوحات المكتملة لإعادة فتحها | تجربة HITL ثم صفحة السجل |
| Safety, Validation & HITL | فحص XLSX والمسار والحجم، منع الماكرو/الصيغ، interrupt للتوضيح، تحقق النتائج ومراجع الأرقام، حد محاولات وfallback | الملف غير المرتب + `docs/GUARDRAILS.md` + الاختبارات |
| UI integration | Next.js/React عربية RTL بخط ثمانية، رحلة مبسطة، Dashboard حديثة، رسوم ECharts واضحة، حركة KPI، وشارة جاهزية Ollama | العرض الحي على سطح المكتب والهاتف |
| Presentation & working demo | عينتان جاهزتان، فحص صحة يظهر المزود والنموذج، خطة وكيل ظاهرة، سيناريو عرض واختبارات آلية | `docs/DEMO_SCRIPT.md` و`/api/v1/health` |

## رسالة المشروع المختصرة

«بيّنة» وكيل بيانات عربي محلي يحوّل Excel إلى قرار قابل للتتبع: يفهم البنية بواسطة نموذج مجاني محلي، يسأل الإنسان عند الغموض، ويترك كل رقم لحساب برمجي موثق.
