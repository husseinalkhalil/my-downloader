from flask import Flask, render_template, request, send_file, after_this_request
import yt_dlp
import os
import time
import glob
import requests
import mimetypes
import shutil
import zipfile

app = Flask(__name__)

def clean_server():
    """تنظيف الملفات المؤقتة والقديمة"""
    try:
        # حذف المجلدات التي تبدأ بـ download_
        for d in glob.glob("download_*"):
            shutil.rmtree(d, ignore_errors=True)
        # حذف ملفات ZIP القديمة
        for z in glob.glob("*.zip"):
            os.remove(z)
        # حذف ملفات الوسائط المفردة
        for f in glob.glob("media_*"):
            os.remove(f)
    except:
        pass

# تنظيف عند بدء التشغيل
clean_server()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/download', methods=['POST'])
def download_media():
    url = request.form.get('url')
    if not url:
        return "الرجاء إدخال رابط", 400

    # 1. تجهيز مجلد عمل خاص لهذا الطلب
    request_id = str(int(time.time()))
    work_dir = f"download_{request_id}"
    
    # التأكد من إنشاء المجلد
    if not os.path.exists(work_dir):
        os.makedirs(work_dir)

    # 2. إعدادات yt-dlp المخصصة للروابط المتعددة
    ydl_opts = {
        'format': 'best', # أفضل جودة متاحة
        
        # --- السطر الأهم: تسمية الملفات بترقيم تسلسلي ---
        # %(playlist_index)s يضع رقم الملف (1, 2, 3...)
        'outtmpl': f'{work_dir}/media_%(playlist_index)s.%(ext)s',
        
        'quiet': True,
        'no_warnings': True,
        'ignoreerrors': True,
        
        # تفعيل القوائم (ضروري للبوستات المتعددة)
        'noplaylist': False,
        'extract_flat': False,
        
        # عدم كتابة ملفات json أو وصف، نريد الميديا فقط
        'writethumbnail': False,
        'writeinfojson': False,
        'writesubtitles': False,

        # إعدادات إنستغرام (خداع الهوية)
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Instagram 123.0.0.21.115',
        }
    }

    # تعديل الهوية لباقي المواقع (غير إنستغرام)
    if "instagram.com" not in url:
        ydl_opts['http_headers'] = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
        }

    try:
        # --- بدء التحميل ---
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        # --- فحص النتائج ---
        # البحث عن كل الملفات داخل المجلد (مهما كانت صيغتها)
        files = []
        for ext in ['*.mp4', '*.jpg', '*.jpeg', '*.png', '*.webp', '*.mkv', '*.mov']:
            files.extend(glob.glob(os.path.join(work_dir, ext)))

        # إذا لم نجد شيئاً، نحاول التحميل المباشر كصورة وحيدة (خطة بديلة)
        if not files:
            direct_file = try_direct_download(url, work_dir)
            if direct_file:
                files = [direct_file]

        # --- القرار النهائي ---
        
        # حالة 0: فشل تام
        if not files:
            shutil.rmtree(work_dir, ignore_errors=True)
            return "فشل التحميل: لم يتم العثور على ملفات، أو أن الحساب خاص.", 500

        # حالة 1: ملف واحد فقط
        elif len(files) == 1:
            file_path = files[0]
            # نخرج الملف من المجلد المؤقت لنرسله
            file_ext = os.path.splitext(file_path)[1]
            public_filename = f"media_{request_id}{file_ext}"
            shutil.move(file_path, public_filename)
            shutil.rmtree(work_dir, ignore_errors=True) # حذف المجلد

            @after_this_request
            def cleanup_single(response):
                try: os.remove(public_filename)
                except: pass
                return response

            # نسميه اسماً عاماً ليتعرف عليه المتصفح
            return send_file(public_filename, as_attachment=True, download_name=f"downloaded_media{file_ext}")

        # حالة 2: مجموعة ملفات (أكثر من 1) -> ZIP
        else:
            zip_filename = f"collection_{request_id}.zip"
            with zipfile.ZipFile(zip_filename, 'w') as zipf:
                for file in files:
                    # نضيف الملف للضغظ باسم بسيط (media_1.jpg, media_2.mp4)
                    zipf.write(file, os.path.basename(file))
            
            shutil.rmtree(work_dir, ignore_errors=True) # حذف المجلد الأصلي

            @after_this_request
            def cleanup_zip(response):
                try: os.remove(zip_filename)
                except: pass
                return response

            return send_file(zip_filename, as_attachment=True, download_name="media_collection.zip")

    except Exception as e:
        # تنظيف في حال الخطأ
        shutil.rmtree(work_dir, ignore_errors=True)
        return f"حدث خطأ أثناء المعالجة: {str(e)}", 500


def try_direct_download(url, folder):
    """محاولة أخيرة: تحميل الرابط كملف مباشر"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(url, headers=headers, stream=True, verify=False, timeout=10)
        content_type = response.headers.get('Content-Type', '').lower()
        
        # التأكد أنه ليس صفحة ويب
        if 'html' not in content_type:
            ext = mimetypes.guess_extension(content_type.split(';')[0]) or '.jpg'
            filename = os.path.join(folder, f"direct_media{ext}")
            with open(filename, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return filename
    except:
        pass
    return None

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
