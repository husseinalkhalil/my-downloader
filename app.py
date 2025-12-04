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
    
    # --- 1. التحقق من الصور المباشرة (Direct Images) ---
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/115.0.0.0 Safari/537.36'}
        # نستخدم HEAD request سريع للتحقق من النوع
        response = requests.head(url, headers=headers, allow_redirects=True, timeout=5, verify=False)
        content_type = response.headers.get('Content-Type', '').lower()

        if 'image' in content_type and 'html' not in content_type:
            response = requests.get(url, headers=headers, stream=True, verify=False)
            ext = mimetypes.guess_extension(content_type.split(';')[0]) or '.jpg'
            final_filename = f"{base_filename}{ext}"
            
            with open(final_filename, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return send_file(final_filename, as_attachment=True, download_name=f"image{ext}")
    except:
        pass 

    # --- 2. إعدادات التحميل (yt-dlp) ---
    
    # الإعدادات العامة المشتركة
    ydl_opts = {
        'format': 'best',
        'outtmpl': f'{base_filename}.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'ignoreerrors': True, # تجاهل الأخطاء البسيطة
    }

    # تخصيص الإعدادات حسب الموقع
    if "instagram.com" in url:
        # إعدادات خاصة لإنستغرام (خدعة الآيفون)
        ydl_opts.update({
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Instagram 123.0.0.21.115',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Sec-Fetch-Mode': 'navigate',
            }
        })
    elif "youtube.com" in url or "youtu.be" in url:
        # إعدادات خاصة لليوتيوب (بدون headers مزيفة لتجنب الحظر)
        # نترك yt-dlp يتصرف بطبيعته
        pass
    else:
        # لباقي المواقع (تويتر، تيك توك) نستخدم هوية متصفح كمبيوتر عادية
        ydl_opts.update({
             'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
        })

    # --- 3. التنفيذ ---
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        found_files = glob.glob(f"{base_filename}.*")
        
        if not found_files:
            return "فشل التحميل: تأكد أن الفيديو متاح وعام (قد يكون خاصاً أو محذوفاً).", 500

        final_file = found_files[0]
        file_ext = os.path.splitext(final_file)[1]
        
        return send_file(final_file, as_attachment=True, download_name=f"media{file_ext}")

    except Exception as e:
        error_msg = str(e)
        print(f"Error: {error_msg}") # طباعة الخطأ في السجلات للمبرمج
        if "Sign in" in error_msg:
             return "يوتيوب يرفض التحميل من السيرفر (يطلب تسجيل دخول). حاول فيديو آخر.", 400
        return f"حدث خطأ أثناء التحميل: {error_msg}", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
