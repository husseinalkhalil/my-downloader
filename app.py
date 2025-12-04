from flask import Flask, render_template, request, send_file
import yt_dlp
import os
import time
import glob
import requests
import mimetypes

app = Flask(__name__)

def clean_temp_files():
    """حذف الملفات القديمة لتنظيف السيرفر"""
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

    # اسم ملف فريد
    file_id = str(int(time.time()))
    base_filename = f"media_{file_id}"
    
    # إعدادات هوية المتصفح (ضروري جداً لتحميل الصور)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
        'Referer': 'https://www.google.com/'
    }

    # --- المرحلة 1: هل الرابط ملف مباشر (صورة/فيديو)؟ ---
    try:
        # نرسل طلب استكشاف (HEAD) أو (GET) مع Stream
        # verify=False لتجاهل مشاكل شهادات الأمان في بعض المواقع
        response = requests.get(url, headers=headers, stream=True, timeout=10, verify=False)
        
        content_type = response.headers.get('Content-Type', '').lower()
        
        # إذا لم يكن الرابط صفحة HTML (أي أنه ملف مباشر سواء صورة أو فيديو)
        if 'html' not in content_type:
            # تخمين الامتداد الصحيح (jpg, png, mp4...)
            ext = mimetypes.guess_extension(content_type.split(';')[0]) or '.jpg'
            final_filename = f"{base_filename}{ext}"
            
            # تحميل الملف
            with open(final_filename, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # إرسال الملف
            return send_file(final_filename, as_attachment=True, download_name=f"downloaded_file{ext}")

    except Exception as e:
        print(f"Direct download check skipped: {e}")

    # --- المرحلة 2: إذا كان الرابط صفحة ويب (يوتيوب، تويتر...) نستخدم yt-dlp ---
    try:
        ydl_opts = {
            'format': 'best', 
            'outtmpl': f'{base_filename}.%(ext)s',
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        # البحث عن الملف الناتج
        found_files = glob.glob(f"{base_filename}.*")
        
        if not found_files:
            return "فشل التحميل: لم يتم العثور على وسائط في الرابط.", 500

        final_file = found_files[0]
        file_ext = os.path.splitext(final_file)[1]
        
        return send_file(final_file, as_attachment=True, download_name=f"social_media{file_ext}")

    except Exception as e:
        return f"حدث خطأ أثناء المعالجة: {str(e)}", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
