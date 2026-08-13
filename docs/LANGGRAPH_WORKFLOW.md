# سير LangGraph

```mermaid
flowchart TD
  S([Start]) --> V[validate_file]
  V -->|غير صالح| H[handle_failure]
  V --> I[inspect_workbook] --> T[detect_tables]
  T -->|فارغ| H
  T --> N[infer_semantics] --> A[detect_ambiguities]
  A -->|غامض| Q[request_user_clarification / interrupt]
  Q -->|Command resume| P[profile_dataset]
  A -->|واضح| P
  P --> C[create_analysis_plan] --> E[execute_analysis]
  E --> R[validate_results]
  R -->|صحيح| D[generate_dashboard_spec]
  R -->|إعادة والمحاولات متبقية| E
  R -->|بلغ الحد| F[fallback_analysis]
  D --> G[generate_insights] --> SV[save_analysis] --> END([End])
  F --> END
  H --> END
```

الحالة TypedDict وتضم هوية الملف، الورقة، ملفات الأعمدة، الغموض، الربط، الجودة، الخطة، النتائج، DashboardSpec، المرحلة، التقدم، الأخطاء، عدد المحاولات، وسجل القرار. يستخدم InMemorySaver مع `thread_id=analysis_id`. عند الغموض تحفظ الحالة؛ تصبح قيمة `Command(resume=...)` جواب `interrupt()` عند إعادة دخول العقدة.

حلقة recovery تعيد `validate_results` إلى `execute_analysis`. الحد من 1 إلى 5، وبعده يعمل fallback محلي محافظ.

