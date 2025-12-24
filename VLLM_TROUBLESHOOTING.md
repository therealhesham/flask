# حل مشكلة vLLM Connection Error

## المشكلة

إذا كنت ترى رسائل مثل:
```
Error during VLLM generation: Connection error.
Detected vllm error, retrying generation (attempt 1)...
```

هذا يعني أن chandra-ocr يحاول الاتصال بخدمة vLLM ولكن يواجه مشاكل في الاتصال.

## الحلول المطبقة

### 1. ✅ معالجة تلقائية للأخطاء
- chandra-ocr يقوم بإعادة المحاولة تلقائياً (عادة 6 محاولات)
- الكود الآن يطبع معلومات تشخيصية عند اكتشاف أخطاء vLLM

### 2. ✅ Endpoints جديدة للتشخيص
- `GET /vllm-status` - للتحقق من إعدادات vLLM
- `GET /diagnostics` - معلومات شاملة عن النظام

### 3. ✅ رسائل خطأ محسّنة
- رسائل أوضح عند حدوث أخطاء vLLM
- إرشادات لحل المشكلة

## الأسباب المحتملة

1. **vLLM service غير متاح**
   - الخدمة غير قيد التشغيل
   - الخدمة متوقفة أو معطلة

2. **مشاكل الشبكة**
   - عدم إمكانية الوصول لـ vLLM service
   - Firewall يمنع الاتصال
   - Network latency عالية

3. **إعدادات خاطئة**
   - URL أو Port خاطئ
   - Environment variables غير صحيحة

4. **vLLM service مثقل**
   - الخدمة بطيئة في الرد
   - الخدمة مشغولة بطلبات أخرى

## الحلول

### 1. التحقق من حالة vLLM

```bash
# تحقق من إعدادات vLLM
curl http://YOUR_SERVER:5000/vllm-status

# تحقق من معلومات التشخيص
curl http://YOUR_SERVER:5000/diagnostics
```

### 2. التحقق من Environment Variables

vLLM قد يحتاج إلى environment variables:
- `VLLM_HOST` - عنوان vLLM service
- `VLLM_PORT` - منفذ vLLM service
- `VLLM_BASE_URL` - URL كامل لـ vLLM
- `VLLM_API_BASE` - API base URL
- `OPENAI_API_BASE` - OpenAI API base (إذا كان vLLM متوافق مع OpenAI API)

### 3. التحقق من أن vLLM يعمل

```bash
# إذا كان vLLM يعمل محلياً
curl http://localhost:8000/health

# أو حسب إعداداتك
curl http://VLLM_HOST:VLLM_PORT/health
```

### 4. إعادة تشغيل vLLM Service

إذا كان vLLM service متاحاً، جرب إعادة تشغيله:
```bash
# حسب طريقة تشغيلك لـ vLLM
docker restart vllm-container
# أو
systemctl restart vllm
```

## ملاحظات مهمة

1. **إعادة المحاولة التلقائية**: chandra-ocr يقوم بإعادة المحاولة تلقائياً. إذا رأيت 6 محاولات فاشلة ثم نجحت، هذا طبيعي.

2. **الوقت المستغرق**: قد يستغرق الأمر وقتاً أطول بسبب إعادة المحاولات، لكنه يجب أن ينجح في النهاية.

3. **النجاح بعد المحاولات**: كما في سجلك:
   ```
   Error during VLLM generation: Connection error.
   ... (6 attempts) ...
   Successfully used method: generate(batch=[ImagePrompt] PIL)
   OCR completed in 52.36 seconds
   ```
   هذا يعني أن النظام يعمل بشكل صحيح - فقط يحتاج إلى إعادة المحاولة.

## تحسينات مستقبلية

إذا استمرت المشكلة، يمكن:
1. زيادة عدد محاولات إعادة المحاولة في chandra
2. إضافة connection pooling لـ vLLM
3. استخدام vLLM محلي بدلاً من remote service
4. إضافة health check لـ vLLM قبل بدء المعالجة

## Endpoints المتاحة

- `GET /vllm-status` - حالة وإعدادات vLLM
- `GET /diagnostics` - معلومات تشخيصية شاملة
- `GET /health` - Health check
- `POST /ocr` - معالجة OCR (يستخدم vLLM تلقائياً)

