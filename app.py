#!/usr/bin/env python3
"""
Universal Video Downloader Web App
Downloads videos from YouTube, Vimeo, TikTok, Twitter, Instagram, and 1000+ sites
Files stream directly to the user's browser for local download.
"""

from flask import Flask, render_template, request, send_file, jsonify
import os
import tempfile
import yt_dlp
import threading
from datetime import datetime

app = Flask(__name__)

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


def download_video(url: str, download_id: str, format_type: str = 'mp4'):
    """Download video in background thread, storing in temp directory"""
    temp_dir = tempfile.mkdtemp()

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
        'temp_dir': temp_dir,
        'url': url
    }

    if format_type == 'mp3':
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
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
            'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
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

        filepath = os.path.join(temp_dir, final_filename)
        if not os.path.exists(filepath):
            # Fallback: find any file in temp_dir
            for f in os.listdir(temp_dir):
                if f.endswith(f'.{ext}'):
                    filepath = os.path.join(temp_dir, f)
                    break

        downloads[download_id].update({
            'status': 'complete',
            'progress': '100',
            'filename': os.path.basename(filepath),
            'filepath': filepath,
            'error': None,
            'message': 'Download complete!',
            'title': info.get('title', 'Unknown'),
            'uploader': info.get('uploader', 'Unknown'),
            'duration': info.get('duration', 0),
            'thumbnail': info.get('thumbnail', '')
        })
        print(f"[{download_id}] Complete: {filepath}")

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

    if not url:
        return jsonify({'error': 'No URL provided'}), 400

    if format_type not in ['mp3', 'mp4']:
        return jsonify({'error': 'Invalid format. Use mp3 or mp4'}), 400

    download_id = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    thread = threading.Thread(target=download_video, args=(url, download_id, format_type))
    thread.start()

    return jsonify({'download_id': download_id})


@app.route('/status/<download_id>')
def check_status(download_id):
    status = downloads.get(download_id, {'status': 'not_found'})
    return jsonify(status)


@app.route('/stream/<download_id>')
def stream_file(download_id):
    """Stream the downloaded file directly to the user's browser"""
    download = downloads.get(download_id)
    if not download or download['status'] != 'complete':
        return jsonify({'error': 'File not ready'}), 404

    filepath = download.get('filepath')
    if not filepath or not os.path.exists(filepath):
        return jsonify({'error': 'File not found'}), 404

    filename = download.get('filename', 'download')
    mimetype = 'audio/mpeg' if filename.endswith('.mp3') else 'video/mp4'

    def cleanup():
        """Clean up temp file after streaming"""
        try:
            temp_dir = download.get('temp_dir')
            if temp_dir and os.path.exists(temp_dir):
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)
            downloads.pop(download_id, None)
        except Exception:
            pass

    response = send_file(
        filepath,
        mimetype=mimetype,
        as_attachment=True,
        download_name=filename
    )
    response.call_on_close(cleanup)
    return response


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
    port = int(os.environ.get('PORT', 8080))
    debug = os.environ.get('FLASK_ENV') != 'production'
    app.run(debug=debug, host='0.0.0.0', port=port)
