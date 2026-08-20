حزمة التحديث الثاني لمشروع بيّنة

طريقة الاستخدام:
1) افتح ملف TXT من هذه الحزمة.
2) ابحث عن الملف الأصلي حسب المسار الموضح أدناه داخل Visual Studio Code.
3) احذف محتوى الملف الأصلي كاملًا.
4) الصق محتوى ملف TXT كاملًا ثم احفظ بـ Ctrl+S.
5) كرر العملية لجميع الملفات.

مطابقة أسماء ملفات TXT مع مسارات المشروع:

backend__app__agent.py.txt
=> backend/app/agent.py

backend__app__analytics.py.txt
=> backend/app/analytics.py

backend__app__main.py.txt
=> backend/app/main.py

backend__app__schemas.py.txt
=> backend/app/schemas.py

backend__app__service.py.txt
=> backend/app/service.py

backend__tests__test_api.py.txt
=> backend/tests/test_api.py

frontend__app__globals.css.txt
=> frontend/app/globals.css

frontend__components__bayyinah-app.tsx.txt
=> frontend/components/bayyinah-app.tsx

frontend__components__chart-card.tsx.txt
=> frontend/components/chart-card.tsx

frontend__lib__api.ts.txt
=> frontend/lib/api.ts

frontend__lib__schemas.ts.txt
=> frontend/lib/schemas.ts

frontend__tests__schemas.test.ts.txt
=> frontend/tests/schemas.test.ts

بعد الاستبدال محليًا:
- أوقف الفرونت والباك إن كانا يعملان.
- شغّل الباكند من جديد.
- شغّل الفرونت من جديد.
- نفّذ تحليلًا جديدًا؛ النتائج القديمة لا تحتوي البنية الجديدة.

مهم: لا تضع مفتاح GROQ_API_KEY داخل أي ملف مرفوع إلى GitHub.
