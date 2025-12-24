# حل مشكلة Timeout في OCR API

## المشكلة
إذا كنت تواجه خطأ "Timeout was reached"، قد يكون السبب من عدة أماكن:

## الحلول المطبقة

### 1. في الكود (ocr_api.py)
- ✅ زيادة overall timeout إلى **30 دقيقة** (1800 ثانية)
- ✅ إزالة ThreadPoolExecutor المتداخل الذي قد يسبب مشاكل
- ✅ تحسين معالجة الأخطاء

### 2. في Gunicorn (Dockerfile)
- ✅ زيادة timeout إلى **40 دقيقة** (2400 ثانية)
- ✅ إعدادات graceful-timeout و keep-alive محسّنة

### 3. في Test Script (test_ocr.ps1)
- ✅ زيادة curl timeout إلى **40 دقيقة** (2400 ثانية)

## ⚠️ مشكلة محتملة: sslip.io

إذا كنت تستخدم **sslip.io** كـ reverse proxy (كما في test_ocr.ps1)، قد يكون لديه timeout محدود.

### حلول:

1. **الوصول المباشر للخدمة** (بدون sslip.io):
   ```powershell
   # استخدم IP مباشر أو domain name مباشر
   $uri = "http://YOUR_SERVER_IP:5000/ocr"
   ```

2. **استخدام reverse proxy آخر** مثل:
   - nginx (مع timeout settings عالية)
   - Caddy
   - Traefik

3. **التحقق من timeout settings**:
   ```powershell
   # تحقق من timeout settings
   curl.exe http://YOUR_SERVER/timeout-info
   ```

## نصائح إضافية

1. **تقليل حجم الصورة**: الصور الكبيرة تستغرق وقتاً أطول
2. **استخدام async processing**: للمستقبل، يمكن استخدام background jobs
3. **مراقبة الأداء**: تحقق من logs لمعرفة أين يحدث timeout بالضبط

## Endpoints المتاحة

- `GET /health` - Health check
- `GET /timeout-info` - معلومات عن timeout settings
- `GET /diagnostics` - معلومات عن chandra package
- `POST /ocr` - معالجة OCR

## إذا استمرت المشكلة

1. تحقق من logs في Docker:
   ```bash
   docker logs <container_name>
   ```

2. تحقق من timeout في reverse proxy (إذا كان موجوداً)

3. جرب الوصول المباشر للخدمة بدون reverse proxy

4. تحقق من موارد النظام (CPU, Memory, Disk)

