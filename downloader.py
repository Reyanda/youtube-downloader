#!/usr/bin/env python3
"""
Simple YouTube Downloader
Downloads MP4 videos from YouTube URLs
"""

import sys
import yt_dlp


def download_video(url: str, output_path: str = "./downloads") -> bool:
    """
    Download video from YouTube URL as MP4

    Args:
        url: YouTube video URL
        output_path: Directory to save the video (default: ./downloads)

    Returns:
        True if successful, False otherwise
    """
    ydl_opts = {
        'format': 'bestvideo+bestaudio/best',
        'outtmpl': f'{output_path}/%(title)s.%(ext)s',
        'merge_output_format': 'mp4',
    }

    try:
        print(f"Downloading: {url}")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        print("Download complete!")
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False


def main():
    if len(sys.argv) < 2:
        print("Usage: python downloader.py <youtube_url>")
        print("Example: python downloader.py https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        sys.exit(1)

    url = sys.argv[1]

    # Create downloads directory
    import os
    os.makedirs("./downloads", exist_ok=True)

    if download_video(url):
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
