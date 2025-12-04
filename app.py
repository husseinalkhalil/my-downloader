from flask import Flask, render_template, request, send_file
import yt_dlp
import os
import time
import glob
import requests
import mimetypes

app = Flask(__name__)

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

    file_id = str(int(time.time()))
    base_filename = f"media_{file_id}"
    
    # 1. محاولة التحميل المباشر (للصور المباشرة مثل JPG/PNG)
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
        }
        
        # تجنب تحميل صفحات الويب كملفات
        response = requests.head(url, headers=headers, allow_redirects=True, timeout=5)
        content_type = response.headers.get('Content-Type', '').lower()

        if 'image' in content_type and 'html' not in content_type:
            response = requests.get(url, headers=headers, stream=True)
            ext = mimetypes.guess_extension(content_type.split(';')[0]) or '.jpg'
            final_filename = f"{base_filename}{ext}"
            
            with open(final_filename, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            return send_file(final_filename, as_attachment=True, download_name=f"image{ext}")

    except Exception:
        pass # إذا فشل ننتقل للخطوة التالية

    # 2. محاولة التحميل باستخدام yt-dlp (إنستغرام، تويتر، يوتيوب)
    try:
        ydl_opts = {
            'format': 'best',
            'outtmpl': f'{base_filename}.%(ext)s',
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
            
            # --- هذا هو التعديل السحري لإنستغرام ---
            # نقوم بإيهام الموقع بأننا تطبيق إنستغرام على آيفون
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Instagram 123.0.0.21.115',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Sec-Fetch-Mode': 'navigate',
            }
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        found_files = glob.glob(f"{base_filename}.*")
        
        if not found_files:
            # رسالة توضيحية إذا فشل إنستغرام تحديداً
            if "instagram" in url:
                return "فشل التحميل من إنستغرام: الموقع يطلب تسجيل دخول (الحماية عالية جداً حالياً).", 500
            return "فشل التحميل: لم يتم العثور على وسائط.", 500

        final_file = found_files[0]
        file_ext = os.path.splitext(final_file)[1]
        
        return send_file(final_file, as_attachment=True, download_name=f"social_media{file_ext}")

    except Exception as e:
        error_msg = str(e)
        if "Login required" in error_msg:
             return "إنستغرام يرفض التحميل لأنه يطلب تسجيل دخول (حماية ضد السيرفرات).", 400
        return f"حدث خطأ: {error_msg}", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
