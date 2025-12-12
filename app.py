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

# تنظيف المجلدات القديمة عند بدء التشغيل
def clean_stale_data():
    try:
        # حذف ملفات ZIP القديمة
        for f in glob.glob("media_*.zip"):
            os.remove(f)
        # حذف المجلدات المؤقتة القديمة
        for d in glob.glob("download_*"):
            shutil.rmtree(d, ignore_errors=True)
    except:
        pass

clean_stale_data()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/download', methods=['POST'])
def download_media():
    url = request.form.get('url')
    if not url:
        return "الرجاء إدخال رابط", 400

    # إنشاء مجلد خاص لهذه العملية فقط (لتجنب تداخل الملفات)
    request_id = str(int(time.time()))
    download_folder = f"download_{request_id}"
    os.makedirs(download_folder, exist_ok=True)
    
    # اسم الملف الأساسي داخل المجلد
    base_filename = os.path.join(download_folder, "media")

    # --- إعدادات التحميل ---
    ydl_opts = {
        'format': 'best',
        'outtmpl': f'{base_filename}_%(autonumber)s.%(ext)s', # ترقيم الملفات تلقائياً
        'quiet': True,
        'no_warnings': True,
        'ignoreerrors': True,
        'noplaylist': False,     # تفعيل تحميل القوائم (مهم جداً للبوستات المتعددة)
        'yes_playlist': True,    # التأكيد على قبول القوائم
        'writethumbnail': False, # لا نريد صور مصغرة
        
        # إعدادات خاصة لإنستغرام
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Instagram 123.0.0.21.115',
        }
    }

    # إذا لم يكن الرابط من إنستغرام، نستخدم هوية متصفح عادية
    if "instagram.com" not in url:
        ydl_opts['http_headers'] = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
        }

    try:
        # 1. محاولة التحميل باستخدام yt-dlp
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        # 2. فحص الملفات التي تم تحميلها
        files = glob.glob(os.path.join(download_folder, "*"))
        
        # إذا فشل yt-dlp ولم يجد شيئاً، نجرب التحميل المباشر كصورة وحيدة
        if not files:
            direct_file = try_direct_download(url, download_folder)
            if direct_file:
                files = [direct_file]
            else:
                shutil.rmtree(download_folder, ignore_errors=True)
                return "فشل التحميل: لم يتم العثور على وسائط في الرابط.", 500

        # 3. اتخاذ القرار: ملف واحد أم مجموعة؟
        
        # أ) إذا كان ملفاً واحداً فقط
        if len(files) == 1:
            final_file = files[0]
            # نقل الملف خارج المجلد المؤقت ليتم إرساله
            public_name = f"media_{request_id}{os.path.splitext(final_file)[1]}"
            shutil.move(final_file, public_name)
            shutil.rmtree(download_folder, ignore_errors=True) # حذف المجلد المؤقت
            
            # جدولة حذف الملف بعد الإرسال
            @after_this_request
            def remove_file(response):
                try: os.remove(public_name)
                except: pass
                return response

            return send_file(public_name, as_attachment=True)

        # ب) إذا كان أكثر من ملف (ZIP)
        else:
            zip_filename = f"media_collection_{request_id}.zip"
            with zipfile.ZipFile(zip_filename, 'w') as zipf:
                for file in files:
                    zipf.write(file, os.path.basename(file))
            
            shutil.rmtree(download_folder, ignore_errors=True) # حذف المجلد المؤقت

            @after_this_request
            def remove_zip(response):
                try: os.remove(zip_filename)
                except: pass
                return response

            return send_file(zip_filename, as_attachment=True, download_name="media_collection.zip")

    except Exception as e:
        shutil.rmtree(download_folder, ignore_errors=True)
        return f"حدث خطأ: {str(e)}", 500

def try_direct_download(url, folder):
    """محاولة تحميل الرابط كصورة مباشرة إذا فشل yt-dlp"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(url, headers=headers, stream=True, verify=False, timeout=10)
        content_type = response.headers.get('Content-Type', '').lower()
        
        if 'image' in content_type and 'html' not in content_type:
            ext = mimetypes.guess_extension(content_type.split(';')[0]) or '.jpg'
            filename = os.path.join(folder, f"image{ext}")
            with open(filename, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return filename
    except:
        pass
    return None

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
