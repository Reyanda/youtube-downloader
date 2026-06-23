# 📥 YouTube Downloader

A simple, elegant YouTube downloader with a web interface. Download videos as MP4 or extract audio as MP3 with real-time progress tracking.

![Python](https://img.shields.io/badge/Python-3.7+-blue.svg)
![Flask](https://img.shields.io/badge/Flask-3.0+-green.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

## ✨ Features

- 🎬 **Download as MP4** - High quality video downloads
- 🎵 **Extract as MP3** - Audio extraction at 192kbps
- 📊 **Real-time Progress** - Live speed, ETA, and percentage
- 📁 **Custom Download Location** - Choose where files are saved
- 🌐 **Clean Web Interface** - Simple, responsive design
- 📜 **Download History** - View and re-download previous files

## 🚀 Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/youtube-downloader.git
cd youtube-downloader

# Install dependencies
pip install -r requirements.txt
```

### Running

```bash
python app.py
```

Then open **http://localhost:8080** in your browser.

## 📸 Screenshots

| Main Interface | Download Progress |
|----------------|------------------|
| ![Main](https://via.placeholder.com/400x300?text=Paste+URL+and+choose+format) | ![Progress](https://via.placeholder.com/400x300?text=Real-time+progress+bar) |

## 🛠️ Configuration

### Change Port

Edit `app.py` at the bottom:

```python
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=YOUR_PORT)
```

### Default Download Location

The default is `./downloads` folder in the project directory. Users can change this via the web interface.

## 📦 Requirements

- Python 3.7 or higher
- yt-dlp (YouTube downloader backend)
- Flask (Web framework)

## 🎯 Usage

1. **Paste YouTube URL** - Enter any YouTube video URL
2. **Choose Format** - Select MP4 (video) or MP3 (audio)
3. **Set Location** (optional) - Choose where to save files
4. **Click Download** - Watch real-time progress
5. **Access Files** - Download from the history list

## 🔧 Command Line Alternative

A simple CLI script is also included:

```bash
python downloader.py <youtube_url>
```

## 📝 License

MIT License - feel free to use this project for any purpose.

## 🤝 Contributing

Contributions are welcome! Feel free to:

- Report bugs
- Suggest features
- Submit pull requests

## ⚠️ Disclaimer

Please respect copyright laws and YouTube's Terms of Service. Only download videos you have permission to download.

## 🙏 Acknowledgments

- [yt-dlp](https://github.com/yt-dlp/yt-dlp) - The powerful YouTube downloader backend
- [Flask](https://flask.palletsprojects.com/) - The web framework

---

Made with ❤️ for easy YouTube downloads
