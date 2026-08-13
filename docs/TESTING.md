# الاختبارات

يشغل `scripts/test-all.ps1` اختبارات Backend مع coverage، ثم lint وTypeScript وVitest وNext build.

نتيجة التحقق الحالية: 15 اختبار Pytest ناجحًا بتغطية 88%، و3 اختبارات Vitest ناجحة، مع نجاح ESLint وTypeScript وبناء Next.js الإنتاجي.

تغطي Pytest: قراءة Excel، اكتشاف الأوراق، المعاينة، الاستدلال الدلالي، كشف الغموض، جودة البيانات، حسابات DuckDB، DashboardSpec، منع الرقم غير الموثق، مسار الملف النظيف، interrupt/resume، الحد الأقصى وfallback، وفحص API الكامل من ملف التجربة إلى اللوحة.

تغطي اختبارات Ollama بعقود محلية حتمية: فرض JSON Schema، حذف `sample_values` من الـPrompt، رفض الأعمدة المختلقة، وإيقاف LangGraph بأمان عند فشل المزود. الاختبار الحي للنموذج نفسه يتم على جهاز العرض بعد `ollama pull llama3.2`، لأن النموذج لا يُنزّل داخل CI.
