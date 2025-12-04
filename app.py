from flask import Flask, render_template, request, send_file
import yt_dlp
import os
import time

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/download', methods=['POST'])
def download_video():
    url = request.form.get('url')
    
    if not url:
        return "الرجاء إدخال رابط", 400

    # اسم ملف عشوائي لتجنب تداخل التحميلات بين المستخدمين
    timestamp = int(time.time())
    filename = f'video_{timestamp}.mp4'
    
    # تحسين إعدادات التحميل لتجنب الأخطاء
    ydl_opts = {
        'format': 'best',
        'outtmpl': filename,
        'quiet': True,
        'no_warnings': True,
        # استخدام وكيل مستخدم (User Agent) لتجنب الحظر من بعض المواقع
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        # التأكد من أن الملف تم إنشاؤه فعلاً قبل إرساله
        if not os.path.exists(filename):
            return "فشل التحميل: لم يتم إنشاء الملف، قد يكون الموقع غير مدعوم.", 500

        # إرسال الملف
        return send_file(filename, as_attachment=True, download_name='video.mp4')

    except Exception as e:
        # هنا التغيير المهم: إرسال رمز خطأ 500 بدلاً من 200
        # هذا سيمنع المتصفح من تحميل النص كأنه فيديو
        error_message = str(e)
        if "No video formats found" in error_message:
            return "لم يتم العثور على فيديو في هذا الرابط", 400
        return f"حدث خطأ أثناء التحميل: {error_message}", 500
        
    finally:
        # محاولة تنظيف السيرفر وحذف الملف بعد إرساله (اختياري)
        # ملاحظة: في ويندوز قد يفشل الحذف المباشر، لكن في سيرفر لينكس (Render) سيعمل
        try:
            if os.path.exists(filename):
                # نترك الملف للحظات حتى ينتهي الإرسال (Render يمسح الملفات تلقائياً عند إعادة التشغيل)
                pass 
        except:
            pass

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
