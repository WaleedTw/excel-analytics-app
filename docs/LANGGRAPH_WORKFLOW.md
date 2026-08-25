# سير LangGraph متعدد الإيجنتات

```mermaid
flowchart TD
  S([Start]) --> V[validate_file]
  V -->|صالح| I[inspect_data_file]
  V -->|فشل| H[handle_failure]
  I --> T[detect_tables]
  T --> C1[Cleaning Agent: infer_semantics]
  C1 --> A[detect_ambiguities]
  A -->|غامض| Q[interrupt / clarification]
  Q --> C2[Cleaning Agent: profile_dataset]
  A -->|واضح| C2
  C2 --> P[Analysis Agent: create_plan]
  P --> E[Analysis Agent: execute]
  E --> R[Dashboard Agent: validate]
  R -->|صحيح| D[Dashboard Agent: finalize]
  R -->|إعادة| E
  R -->|بلغ الحد| F[fallback]
  D --> G[generate_insights]
  G --> SV[save_analysis]
  SV --> END([End])
  F --> END
  H --> END
```

## سجل التنفيذ

الحالة تحمل `agent_runs` بالإضافة إلى `trace`. كل سجل إيجنت يحتوي الاسم، المسؤولية، الحالة، الملخص، والمخرجات التي أنتجها. يعرض الفرونت إند أحدث سجل مكتمل لكل إيجنت، بينما يبقى السجل الكامل متاحًا في استجابة API لأغراض التدقيق.

## الاستعادة والتحقق

- يستخدم `thread_id = analysis_id` مع `InMemorySaver`.
- يحفظ `interrupt()` الغموض الدلالي ويستأنف بـ`Command(resume=...)`.
- يعاد تنفيذ إيجنت التحليل عند فشل DashboardSpec أو التحقق الرقمي حتى الحد المحدد.
- بعد بلوغ الحد، يستخدم fallback محليًا محافظًا لا يعتمد على النموذج اللغوي.