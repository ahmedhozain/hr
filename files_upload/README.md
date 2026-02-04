# Flask HR Documents Uploader

تطبيق ويب لإدارة ورفع المستندات للموارد البشرية باستخدام Flask وPostgreSQL.

## المتطلبات
- Python 3.10 أو أحدث
- PostgreSQL
- جميع الحزم في requirements.txt

## طريقة التشغيل محليًا
1. أنشئ بيئة افتراضية:
   ```
   python -m venv venv
   venv\Scripts\activate
   ```
2. ثبّت الاعتمادات:
   ```
   pip install -r requirements.txt
   ```
3. أنشئ ملف .env بناءً على uploads/env.example
4. شغّل التطبيق:
   ```
   flask run
   ```

## ملاحظات
- تأكد من ضبط متغيرات البيئة مثل DATABASE_URL وSECRET_KEY.
- لا ترفع ملفات البيئة أو قواعد البيانات أو مجلد uploads إلى GitHub.
- عند النشر على Render، أضف متغيرات البيئة من لوحة التحكم.