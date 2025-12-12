from flask import Flask, render_template, request, send_from_directory, jsonify
import yt_dlp
import os
import time
import glob
import shutil

app = Flask(__name__)

# المجلد الأساسي للتنزيلات
BASE_DOWNLOAD_DIR = "downloads"

def clean_server():
    """تنظيف الملفات القديمة التي مر عليها أكثر من 10 دقائق"""
    if not os.path.exists(BASE_DOWNLOAD_DIR):
        os.makedirs(BASE_DOWNLOAD_DIR)
        return

    current_time = time.time()
    try:
        # البحث داخل مجلد التنزيلات
        for folder in os.listdir(BASE_DOWNLOAD_DIR):
            folder_path = os.path.join(BASE_DOWNLOAD_DIR, folder)
            # إذا كان مجلداً ومر عليه وقت طويل نحذفه
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

    # إنشاء مجلد فرعي لكل طلب (باستخدام التوقيت)
    request_id = str(int(time.time()))
    current_job_dir = os.path.join(BASE_DOWNLOAD_DIR, request_id)
    os.makedirs(current_job_dir, exist_ok=True)

    # إعدادات yt-dlp
    ydl_opts = {
        'format': 'best',
        # ترقيم الملفات: media_1.mp4, media_2.jpg
        'outtmpl': f'{current_job_dir}/media_%(playlist_index)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        'ignoreerrors': True,
        'noplaylist': False, # تفعيل القوائم
        
        # إعدادات إنستغرام وتويتر
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Instagram 123.0.0.21.115',
        }
    }
    
    # تغيير الهوية لغير إنستغرام
    if "instagram.com" not in url:
        ydl_opts['http_headers']['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/115.0.0.0 Safari/537.36'

    try:
        # بدء التحميل للسيرفر
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        # جرد الملفات التي تم تحميلها
        files_list = []
        # نبحث عن جميع الملفات في المجلد
        for filename in os.listdir(current_job_dir):
            files_list.append(filename)

        if not files_list:
            shutil.rmtree(current_job_dir)
            return jsonify({"error": "فشل التحميل: لم يتم العثور على وسائط."}), 500

        # إرسال قائمة الملفات للمتصفح (JSON)
        # المتصفح هو من سيقوم بطلب تحميلها واحداً تلو الآخر
        return jsonify({
            "status": "success",
            "folder_id": request_id,
            "files": sorted(files_list), # ترتيب الملفات 1, 2, 3
            "count": len(files_list)
        })

    except Exception as e:
        shutil.rmtree(current_job_dir, ignore_errors=True)
        return jsonify({"error": str(e)}), 500

# هذا الرابط الجديد هو الذي سيستخدمه المتصفح لتحميل الملفات فعلياً
@app.route('/get-file/<folder_id>/<filename>')
def get_file(folder_id, filename):
    try:
        directory = os.path.join(BASE_DOWNLOAD_DIR, folder_id)
        return send_from_directory(directory, filename, as_attachment=True)
    except Exception as e:
        return "File not found", 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
