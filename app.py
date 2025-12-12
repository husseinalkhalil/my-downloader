from flask import Flask, render_template, request, send_from_directory, jsonify
import yt_dlp
import os
import time
import shutil
import requests
import re # مكتبة البحث في النصوص (Regex)
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

    success = False
    
    # --- 1. المحاولة الأولى: yt-dlp (الأفضل للجودة) ---
    try:
        ydl_opts = {
            'format': 'best',
            'outtmpl': f'{current_job_dir}/media_%(playlist_index)s.%(ext)s',
            'quiet': True,
            'ignoreerrors': True,
            'no_warnings': True,
            'noplaylist': False, # تفعيل القوائم
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            }
        }
        
        if "instagram" in url:
             ydl_opts['http_headers']['User-Agent'] = 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148'

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        if len(os.listdir(current_job_dir)) > 0:
            success = True

    except Exception:
        pass # ننتقل للخطة البديلة بصمت

    # --- 2. المحاولة الثانية: الصياد الذكي (Regex Hunter) ---
    # يعمل إذا فشل yt-dlp في إيجاد أي ملف
    if not success:
        print("yt-dlp returned nothing, starting Regex Hunter...")
        if regex_gallery_scraper(url, current_job_dir):
            success = True

    # --- النتيجة ---
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
        return jsonify({"error": "فشل التحميل: لم يتم العثور على وسائط (قد يكون الحساب خاصاً أو محظوراً)."}), 500


# --- وظيفة الصياد الذكي (لاستخراج صور متعددة) ---
def regex_gallery_scraper(url, save_dir):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        }
        
        session = requests.Session()
        response = session.get(url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            return False

        html_content = response.text
        found_urls = set() # نستخدم set لمنع التكرار

        # 1. بحث خاص بتويتر (X) - روابط الصور عالية الجودة
        # تويتر يستخدم صيغة: pbs.twimg.com/media/XXXXX?format=jpg
        twitter_pattern = r'https://pbs\.twimg\.com/media/[\w\-]+\?format=[\w]+&name=[\w]+|https://pbs\.twimg\.com/media/[\w\-]+\.[\w]+'
        twitter_matches = re.findall(twitter_pattern, html_content)
        for link in twitter_matches:
            # تنظيف الرابط للحصول على أفضل جودة
            clean_link = link.replace('&name=small', '&name=large').replace('&name=medium', '&name=large')
            if "name=large" not in clean_link and "?" in clean_link:
                 clean_link += "&name=large"
            found_urls.add(clean_link)

        # 2. بحث عام عن روابط الصور (jpg, png, jpeg)
        # يبحث عن أي رابط يبدأ بـ http وينتهي بصيغة صورة
        if not found_urls:
            general_pattern = r'https?://[^\s<>"]+?\.(?:jpg|jpeg|png)(?:\?[^\s<>"]*)?'
            matches = re.findall(general_pattern, html_content)
            
            for link in matches:
                # فلترة: نستبعد الأيقونات الصغيرة وصور الإعلانات
                if any(x in link for x in ['icon', 'logo', 'avatar', 'profile', 'svg', 'ad', 'pixel']):
                    continue
                found_urls.add(link)

        # 3. التحميل الفعلي للملفات التي وجدناها
        count = 0
        if found_urls:
            print(f"Found {len(found_urls)} potential images via Regex")
            
            for media_url in found_urls:
                # محاولة تحميل الملف
                try:
                    # تنظيف الرابط من الرموز الغريبة (unicode escape)
                    media_url = media_url.replace(r'\/', '/') 
                    
                    media_data = session.get(media_url, headers=headers, stream=True, timeout=5)
                    
                    # التحقق من حجم الملف (لتجاهل الصور الصغيرة جداً < 5KB)
                    if len(media_data.content) < 5000: 
                        continue

                    # تحديد الامتداد
                    content_type = media_data.headers.get('Content-Type', '')
                    ext = mimetypes.guess_extension(content_type.split(';')[0]) or ".jpg"
                    
                    count += 1
                    filename = os.path.join(save_dir, f"image_{count}{ext}")
                    
                    with open(filename, 'wb') as f:
                        f.write(media_data.content)
                        
                    # نكتفي بأول 10 صور لتجنب تحميل الموقع كاملاً بالخطأ
                    if count >= 10: break
                    
                except:
                    continue

        return count > 0

    except Exception as e:
        print(f"Regex Scraper failed: {e}")
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
