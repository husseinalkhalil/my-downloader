from flask import Flask, render_template, request, send_file
import yt_dlp
import os
import time
import glob
import requests

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/download', methods=['POST'])
def download_media():
    url = request.form.get('url')
    
    if not url:
        return "الرجاء إدخال رابط", 400

    # تنظيف أي ملفات قديمة (اختياري للصيانة)
    clean_old_files()

    # معرف فريد للملف (timestamp)
    file_id = str(int(time.time()))
    base_filename = f"media_{file_id}"
    
    try:
        # --- المحاولة الأولى: هل الرابط صورة مباشرة؟ (مثل .jpg .png) ---
        if is_direct_image(url):
            return download_direct_image(url, base_filename)

        # --- المحاولة الثانية: استخدام yt-dlp للفيديوهات ومنصات التواصل ---
        ydl_opts = {
            'format': 'best',  # أفضل جودة متاحة (فيديو أو صورة)
            # النقطة المهمة: نترك الامتداد %(ext)s ليحدده البرنامج تلقائياً
            'outtmpl': f'{base_filename}.%(ext)s',
            'quiet': True,
            'no_warnings': True,
            # السماح بتحميل قوائم التشغيل كملف واحد (للمنشورات التي تحتوي صوراً)
            'noplaylist': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        # البحث عن الملف الذي تم تحميله (لأننا لا نعرف صيغته مسبقاً)
        # نبحث عن أي ملف يبدأ بـ media_123456
        found_files = glob.glob(f"{base_filename}.*")
        
        if not found_files:
            return "فشل التحميل: لم يتم العثور على وسائط.", 500

        final_file = found_files[0] # نأخذ أول ملف وجدناه
        
        # تحديد اسم الملف عند التحميل (Download Name)
        extension = os.path.splitext(final_file)[1]
        download_name = f"downloaded_media{extension}"

        return send_file(final_file, as_attachment=True, download_name=download_name)

    except Exception as e:
        return f"حدث خطأ: {str(e)}", 500

def is_direct_image(url):
    # وظيفة للتحقق مما إذا كان الرابط ينتهي بصيغة صورة معروفة
    image_extensions = ['.jpg', '.jpeg', '.png', '.webp', '.gif']
    return any(url.lower().endswith(ext) for ext in image_extensions)

def download_direct_image(url, base_filename):
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        # تخمين الامتداد من الرابط أو نوع المحتوى
        if 'image/jpeg' in response.headers.get('Content-Type', ''):
            ext = '.jpg'
        elif 'image/png' in response.headers.get('Content-Type', ''):
            ext = '.png'
        else:
            ext = os.path.splitext(url)[1] or '.jpg'

        full_filename = f"{base_filename}{ext}"
        
        with open(full_filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                
        return send_file(full_filename, as_attachment=True, download_name=f"image{ext}")
    except Exception as e:
        raise Exception(f"فشل تحميل الصورة المباشرة: {str(e)}")

def clean_old_files():
    # دالة مساعدة لحذف الملفات القديمة جداً من السيرفر
    try:
        for file in glob.glob("media_*"):
            # إذا مر على الملف أكثر من 10 دقائق نحذفه
            if time.time() - os.path.getmtime(file) > 600:
                os.remove(file)
    except:
        pass

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
