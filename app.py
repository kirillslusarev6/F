from flask import Flask, request, send_file, render_template, jsonify
from flask_cors import CORS
import yt_dlp
import os
import zipfile
import tempfile
import uuid

app = Flask(__name__)
CORS(app)

temp_storage = {}

def extract_playlist_info(url):
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'ignoreerrors': True,
    }
    
    tracks = []
    source = "unknown"
    
    if "music.yandex.ru" in url:
        source = "Яндекс Музыка"
    elif "vk.com" in url:
        source = "VK"
    elif "youtube.com" in url or "youtu.be" in url:
        source = "YouTube"
    else:
        source = "Другой источник"
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                return None, "Ссылка не распознана"
            
            if 'entries' in info and info['entries']:
                for entry in info['entries']:
                    if entry and isinstance(entry, dict):
                        tracks.append({
                            'title': entry.get('title', 'Без названия'),
                            'artist': entry.get('artist', entry.get('uploader', 'Неизвестен')),
                            'thumbnail': entry.get('thumbnail', ''),
                            'duration': entry.get('duration', 0),
                            'url': entry.get('webpage_url', url),
                            'source': source,
                        })
            elif isinstance(info, dict):
                tracks.append({
                    'title': info.get('title', 'Без названия'),
                    'artist': info.get('artist', info.get('uploader', 'Неизвестен')),
                    'thumbnail': info.get('thumbnail', ''),
                    'duration': info.get('duration', 0),
                    'url': info.get('webpage_url', url),
                    'source': source,
                })
            else:
                return None, "Неизвестный формат"
            
            if not tracks:
                return None, "Треки не найдены"
            return tracks, None
    except Exception as e:
        return None, f"Ошибка: {str(e)}"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/parse', methods=['POST'])
def parse_playlist():
    data = request.json
    url = data.get('url', '').strip()
    if not url:
        return jsonify({'error': 'Введите ссылку'}), 400
    
    tracks, error = extract_playlist_info(url)
    if error:
        return jsonify({'error': error}), 400
    
    session_id = str(uuid.uuid4())
    temp_storage[session_id] = tracks
    
    return jsonify({
        'tracks': tracks,
        'session_id': session_id,
        'count': len(tracks)
    })

@app.route('/download_one', methods=['POST'])
def download_one():
    data = request.json
    session_id = data.get('session_id')
    track_index = data.get('index')
    
    tracks = temp_storage.get(session_id, [])
    if not tracks or track_index >= len(tracks):
        return jsonify({'error': 'Трек не найден'}), 404
    
    track = tracks[track_index]
    temp_dir = tempfile.mkdtemp()
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
        'quiet': True,
        'no_warnings': True,
        'ignoreerrors': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([track['url']])
        
        files = os.listdir(temp_dir)
        mp3_files = [f for f in files if f.endswith('.mp3')]
        if mp3_files:
            file_path = os.path.join(temp_dir, mp3_files[0])
            return send_file(file_path, as_attachment=True, download_name=mp3_files[0])
        return jsonify({'error': 'Файл не найден'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/download_all', methods=['POST'])
def download_all():
    data = request.json
    session_id = data.get('session_id')
    tracks = temp_storage.get(session_id, [])
    if not tracks:
        return jsonify({'error': 'Плейлист не найден'}), 404
    
    temp_dir = tempfile.mkdtemp()
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
        'quiet': True,
        'no_warnings': True,
        'ignoreerrors': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            for track in tracks:
                try:
                    ydl.download([track['url']])
                except:
                    continue
        
        zip_path = tempfile.mktemp(suffix='.zip')
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for file in os.listdir(temp_dir):
                if file.endswith('.mp3'):
                    zipf.write(os.path.join(temp_dir, file), file)
        return send_file(zip_path, as_attachment=True, download_name='playlist.zip')
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)