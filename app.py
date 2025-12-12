from flask import Flask, render_template, request, send_from_directory, jsonify
import yt_dlp
import os
import time
import shutil
import requests
from bs4 import BeautifulSoup
import mimetypes

app = Flask(__name__)

BASE_DOWNLOAD_DIR = "downloads"

# تنظيف السيرفر
def clean_server():
    if not os.path.exists(BASE_DOWNLOAD_DIR):
        os.makedirs(BASE_DOWNLOAD_DIR)
        return
    try:
        current_time = time.time()
        for folder in os.listdir(BASE_DOWNLOAD_DIR):
            folder_path = os.path.join(BASE_DOWNLOAD_DIR, folder)
            if os.path.isdir(folder_path):
                if current_time - os.path.getmtime(folder_path) > 600:
                    shutil.rmtree(folder_path, ignore_errors=True)
    except:
        pass

clean_server()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/download', methods=['POST'])
def process_download():
    url = request.form.get('url')
    if not url:
        return jsonify({"error": "الرجاء إدخال رابط"}), 400

    request_id = str(int(time.time()))
    current_job_dir = os.path.join(BASE_DOWNLOAD_DIR, request_id)
    os.makedirs(current_job_dir, exist_ok=True)

    # --- المحاولة الأولى: استخدام yt-dlp (الأفضل للجودة) ---
    success = False
    error_log = ""

    try:
        ydl_opts = {
            'format': 'best', # صيغة واحدة لتجنب مشاكل الدمج
            'outtmpl': f'{current_job_dir}/media_%(playlist_index)s.%(ext)s',
            'quiet': True,
            'ignoreerrors': True,
            'no_warnings': True,
            'noplaylist': False,
            # هوية متصفح قوية
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
            }
        }
        
        # محاولة خاصة لإنستغرام وتيك توك
        if "instagram" in url or "tiktok" in url:
             ydl_opts['http_headers']['User-Agent'] = 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148'

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        # التحقق هل نزل شيء؟
        if len(os.listdir(current_job_dir)) > 0:
            success = True
        else:
            error_log = "yt-dlp لم يجد ملفات."

    except Exception as e:
        error_log = str(e)
        success = False

    # --- المحاولة الثانية: نظام الطوارئ (Scraping Fallback) ---
    # يعمل فقط إذا فشلت المحاولة الأولى، وكان الرابط لملف واحد (فيديو/صورة)
    if not success:
        print(f"yt-dlp failed ({error_log}), trying fallback scraper...")
        if fallback_scraper(url, current_job_dir):
            success = True

    # --- النتيجة النهائية ---
    if success:
        files_list = sorted(os.listdir(current_job_dir))
        return jsonify({
            "status": "success",
            "folder_id": request_id,
            "files": files_list,
            "count": len(files_list)
        })
    else:
        shutil.rmtree(current_job_dir, ignore_errors=True)
        return jsonify({"error": "فشل التحميل من السيرفر. الموقع قد يحظر عناوين الاستضافة (IP Block)."}), 500

# --- دالة الطوارئ (تقوم بمسح الصفحة يدوياً للبحث عن الفيديو) ---
def fallback_scraper(url, save_dir):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://www.google.com/'
        }
        
        session = requests.Session()
        response = session.get(url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            return False

        soup = BeautifulSoup(response.text, 'html.parser')
        media_url = None
        ext = ".mp4" # افتراضي

        # 1. البحث عن فيديو في وسوم meta (شائع في انستا وتيك توك وفيسبوك)
        og_video = soup.find("meta", property="og:video")
        if og_video:
            media_url = og_video["content"]
        
        # 2. البحث عن تويتر فيديو
        if not media_url:
            twitter_stream = soup.find("meta", property="twitter:player:stream")
            if twitter_stream:
                media_url = twitter_stream["content"]

        # 3. البحث عن صورة إذا لم نجد فيديو
        if not media_url:
            og_image = soup.find("meta", property="og:image")
            if og_image:
                media_url = og_image["content"]
                ext = ".jpg"

        # 4. البحث داخل وسم video مباشرة
        if not media_url:
            video_tag = soup.find("video")
            if video_tag and video_tag.get("src"):
                media_url = video_tag["src"]

        # إذا وجدنا رابطاً مباشراً، نقوم بتحميله
        if media_url:
            # تنظيف الرابط أحيانا يكون html entity
            media_url = media_url.replace("&amp;", "&")
            
            media_data = session.get(media_url, headers=headers, stream=True)
            if media_data.status_code == 200:
                # تخمين الامتداد الحقيقي
                content_type = media_data.headers.get('Content-Type', '')
                guessed_ext = mimetypes.guess_extension(content_type.split(';')[0])
                if guessed_ext:
                    ext = guessed_ext

                filename = os.path.join(save_dir, f"backup_download{ext}")
                with open(filename, 'wb') as f:
                    for chunk in media_data.iter_content(chunk_size=8192):
                        f.write(chunk)
                return True
                
    except Exception as e:
        print(f"Fallback failed: {e}")
    
    return False

@app.route('/get-file/<folder_id>/<filename>')
def get_file(folder_id, filename):
    try:
        directory = os.path.join(BASE_DOWNLOAD_DIR, folder_id)
        return send_from_directory(directory, filename, as_attachment=True)
    except Exception as e:
        return "File not found", 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
