from flask import Flask, render_template, request, send_file
import yt_dlp
import os

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/download', methods=['POST'])
def download_video():
    url = request.form.get('url')
    
    if not url:
        return "الرجاء وضع رابط صحيح", 400

    # اسم الملف المؤقت الذي سيتم حفظه في السيرفر
    filename = 'video.mp4'
    
    ydl_opts = {
        'format': 'best',
        'outtmpl': filename,
        'overwrites': True  # الكتابة فوق الملف القديم لتوفير المساحة
    }

    try:
        # التحميل داخل السيرفر
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        # إرسال الملف لك
        return send_file(filename, as_attachment=True)
    except Exception as e:
        return f"حدث خطأ: {str(e)}"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)