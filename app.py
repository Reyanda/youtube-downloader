#!/usr/bin/env python3
"""
Universal Video Downloader Web App
Downloads videos from YouTube, Vimeo, TikTok, Twitter, Instagram, and 1000+ sites
"""

from flask import Flask, render_template, request, send_from_directory, jsonify
import os
import yt_dlp
import threading
from datetime import datetime

app = Flask(__name__)
DEFAULT_DOWNLOAD_DIR = os.path.join(os.path.dirname(__file__), 'downloads')
os.makedirs(DEFAULT_DOWNLOAD_DIR, exist_ok=True)

# Track user preferences
user_preferences = {
    'download_dir': DEFAULT_DOWNLOAD_DIR
}

# Track download status
downloads = {}


def progress_hook(d, download_id):
    """Progress hook for yt-dlp"""
    if d['status'] == 'downloading':
        downloads[download_id].update({
            'status': 'downloading',
            'progress': d.get('_percent_str', '0%').strip('%'),
            'speed': d.get('_speed_str', 'N/A'),
            'eta': d.get('_eta_str', 'N/A'),
            'size': d.get('_total_bytes_str', d.get('_total_bytes_estimate_str', 'N/A')),
            'downloaded': d.get('_downloaded_bytes_str', 'N/A')
        })
    elif d['status'] == 'finished':
        downloads[download_id].update({
            'status': 'processing',
            'progress': '100',
            'message': 'Processing video...'
        })


def download_video(url: str, download_id: str, format_type: str = 'mp4', download_dir: str = None):
    """Download video in background thread with progress tracking"""
    download_dir = download_dir or DEFAULT_DOWNLOAD_DIR
    os.makedirs(download_dir, exist_ok=True)

    downloads[download_id] = {
        'status': 'starting',
        'progress': '0',
        'speed': 'N/A',
        'eta': 'N/A',
        'size': 'N/A',
        'downloaded': 'N/A',
        'filename': None,
        'error': None,
        'message': 'Initializing...',
        'format': format_type,
        'download_dir': download_dir,
        'url': url
    }

    if format_type == 'mp3':
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(download_dir, '%(title)s.%(ext)s'),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'progress_hooks': [lambda d: progress_hook(d, download_id)],
        }
    else:  # mp4
        ydl_opts = {
            'format': 'bestvideo+bestaudio/best',
            'outtmpl': os.path.join(download_dir, '%(title)s.%(ext)s'),
            'merge_output_format': 'mp4',
            'progress_hooks': [lambda d: progress_hook(d, download_id)],
        }

    try:
        print(f"[{download_id}] Downloading: {url}")
        downloads[download_id]['status'] = 'downloading'
        downloads[download_id]['message'] = 'Starting download...'

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            base = os.path.splitext(ydl.prepare_filename(info))[0]
            ext = 'mp3' if format_type == 'mp3' else 'mp4'
            final_filename = f"{base}.{ext}"

        downloads[download_id].update({
            'status': 'complete',
            'progress': '100',
            'filename': os.path.basename(final_filename),
            'error': None,
            'message': 'Download complete!',
            'title': info.get('title', 'Unknown'),
            'uploader': info.get('uploader', 'Unknown'),
            'duration': info.get('duration', 0),
            'thumbnail': info.get('thumbnail', '')
        })
        print(f"[{download_id}] Complete: {final_filename}")

    except Exception as e:
        downloads[download_id].update({
            'status': 'error',
            'error': str(e),
            'message': f'Error: {str(e)}'
        })
        print(f"[{download_id}] Error: {e}")


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/download', methods=['POST'])
def start_download():
    url = request.json.get('url')
    format_type = request.json.get('format', 'mp4')
    download_dir = request.json.get('download_dir')

    if not url:
        return jsonify({'error': 'No URL provided'}), 400

    if format_type not in ['mp3', 'mp4']:
        return jsonify({'error': 'Invalid format. Use mp3 or mp4'}), 400

    # Validate download directory if provided
    if download_dir:
        download_dir = os.path.expanduser(download_dir)
        if not os.path.exists(download_dir):
            try:
                os.makedirs(download_dir, exist_ok=True)
            except Exception as e:
                return jsonify({'error': f'Cannot create directory: {str(e)}'}), 400
        user_preferences['download_dir'] = download_dir

    download_id = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    actual_dir = download_dir or user_preferences.get('download_dir', DEFAULT_DOWNLOAD_DIR)
    thread = threading.Thread(target=download_video, args=(url, download_id, format_type, actual_dir))
    thread.start()

    return jsonify({'download_id': download_id})


@app.route('/status/<download_id>')
def check_status(download_id):
    status = downloads.get(download_id, {'status': 'not_found'})
    return jsonify(status)


@app.route('/downloads')
def list_downloads():
    download_dir = user_preferences.get('download_dir', DEFAULT_DOWNLOAD_DIR)
    files = []
    if os.path.exists(download_dir):
        for f in os.listdir(download_dir):
            if f.endswith('.mp4') or f.endswith('.mp3'):
                path = os.path.join(download_dir, f)
                files.append({
                    'name': f,
                    'size': os.path.getsize(path),
                    'url': f'/files/{f}',
                    'type': 'audio' if f.endswith('.mp3') else 'video'
                })
    return jsonify(sorted(files, key=lambda x: os.path.getmtime(os.path.join(download_dir, x['name'])), reverse=True))


@app.route('/files/<filename>')
def serve_file(filename):
    download_dir = user_preferences.get('download_dir', DEFAULT_DOWNLOAD_DIR)
    return send_from_directory(download_dir, filename)


@app.route('/preferences', methods=['GET', 'POST'])
def preferences():
    if request.method == 'POST':
        new_dir = request.json.get('download_dir')
        if new_dir:
            new_dir = os.path.expanduser(new_dir)
            if not os.path.exists(new_dir):
                return jsonify({'error': 'Directory does not exist'}), 400
            user_preferences['download_dir'] = new_dir
        return jsonify({'success': True, 'download_dir': user_preferences['download_dir']})
    else:
        return jsonify({
            'download_dir': user_preferences.get('download_dir', DEFAULT_DOWNLOAD_DIR)
        })


@app.route('/supported-sites')
def supported_sites():
    """Return list of popular supported sites"""
    sites = [
        {'name': 'YouTube', 'url': 'youtube.com', 'icon': '📺'},
        {'name': 'Vimeo', 'url': 'vimeo.com', 'icon': '🎬'},
        {'name': 'TikTok', 'url': 'tiktok.com', 'icon': '🎵'},
        {'name': 'Twitter/X', 'url': 'twitter.com', 'icon': '🐦'},
        {'name': 'Instagram', 'url': 'instagram.com', 'icon': '📸'},
        {'name': 'Facebook', 'url': 'facebook.com', 'icon': '👥'},
        {'name': 'Twitch', 'url': 'twitch.tv', 'icon': '🎮'},
        {'name': 'Reddit', 'url': 'reddit.com', 'icon': '🔴'},
        {'name': 'SoundCloud', 'url': 'soundcloud.com', 'icon': '🎧'},
        {'name': 'Dailymotion', 'url': 'dailymotion.com', 'icon': '🎥'},
        {'name': 'TED', 'url': 'ted.com', 'icon': '🎤'},
        {'name': 'Vine', 'url': 'vine.co', 'icon': '🍇'},
        {'name': 'Snapchat', 'url': 'snapchat.com', 'icon': '👻'},
        {'name': 'LinkedIn', 'url': 'linkedin.com', 'icon': '💼'},
    ]
    return jsonify(sites)


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8080)
