# الذاكرة والحالة

الذاكرة قصيرة الأجل هي LangGraph `InMemorySaver`. يحفظ checkpoint الحالة عند interrupt ويستعيدها باستخدام معرف التحليل نفسه. لا تمثل ذاكرة مستخدم طويلة الأمد، وتُفقد checkpoints عند إعادة تشغيل الخادم؛ يبقى Dashboard النهائي في SQLite وJSON.

حقول الحالة الأساسية: `file_id`, `file_path`, `sheet_name`, `columns`, `ambiguous_columns`, `column_mapping`, `quality`, `analysis_plan`, `dashboard`, `iteration`, `max_iterations`, `stage`, `progress`, `trace`.

لا تُخزن DataFrame داخل checkpoint؛ تعاد قراءتها من المسار الداخلي الآمن، مما يقلل حجم الذاكرة ويحسن قابلية التسلسل.

