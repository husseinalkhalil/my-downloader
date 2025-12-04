from flask import Flask, render_template, request, send_file
import yt_dlp
import os
import time
import glob
import requests
import mimetypes

app = Flask(__name__)

# تنظيف الملفات القديمة تلقائياً عند تشغيل التطبيق
def clean_temp_files():
    try:
        for f in glob.glob("media_*"):
            os.remove(f)
    except:
        pass

clean_temp_files()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/download', methods=['POST'])
def download_media():
    url = request.form.get('url')
    
    if not url:
        return "الرجاء إدخال رابط", 400

    # اسم أساسي للملف بدون لاحقة
    file_id = str(int(time.time()))
    base_filename = f"media_{file_id}"
    
    # 1. المحاولة الأولى: التحقق مما إذا كان الرابط صورة مباشرة باستخدام Requests
    # هذه الطريقة تنجح مع الصور التي لا تنتهي بـ .jpg
    try:
        # استخدام هوية متصفح حقيقي لتجنب الحظر
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # فحص الرابط (Head Request) لنعرف نوعه قبل التحميل
        response = requests.get(url, headers=headers, stream=True, timeout=10)
        content_type = response.headers.get('Content-Type', '').lower()

        # إذا كان الرابط يؤدي لصورة مباشرة
        if 'image' in content_type and 'html' not in content_type:
            # تخمين الصيغة (jpg, png, etc)
            ext = mimetypes.guess_extension(content_type) or '.jpg'
            final_filename = f"{base_filename}{ext}"
            
            with open(final_filename, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            return send_file(final_filename, as_attachment=True, download_name=f"image{ext}")

    except Exception as e:
        print(f"Direct download failed, trying yt-dlp: {e}")

    # 2. المحاولة الثانية: استخدام yt-dlp (لليوتيوب، تويتر، انستا، وغيرها)
    try:
        ydl_opts = {
            'format': 'best', # أفضل جودة
            'outtmpl': f'{base_filename}.%(ext)s', # الحفظ بالاسم الأساسي + الامتداد الأصلي
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        # البحث عن الملف الذي تم إنشاؤه (لأننا لا نعرف هل هو mp4 أم jpg أم webp)
        found_files = glob.glob(f"{base_filename}.*")
        
        if not found_files:
            return "فشل التحميل: لم يتم العثور على ملف (قد يكون الحساب خاصاً أو الرابط غير مدعوم)", 500

        final_file = found_files[0]
        
        # تحديد اسم الملف عند التنزيل للمستخدم
        file_ext = os.path.splitext(final_file)[1]
        download_name = f"downloaded_media{file_ext}"

        return send_file(final_file, as_attachment=True, download_name=download_name)

    except Exception as e:
        error_msg = str(e)
        if "No video formats" in error_msg:
             return "الرابط لا يحتوي على فيديو أو صورة قابلة للتحميل", 400
        return f"حدث خطأ: {error_msg}", 500
    
    finally:
        # محاولة تنظيف الملفات بعد الإرسال بفترة قصيرة (اختياري)
        pass

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
