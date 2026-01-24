<div align="center">
  
# SpotPulse

**Download Spotify playlists easily and quickly from YouTube.**

<img width=25% alt="iconnn" src="https://github.com/user-attachments/assets/065c4291-3d6b-4d07-8120-b2eef05b3411" />

</div>

A simple, console-based tool that:

- Scrapes tracks from any public Spotify playlist
- Downloads audio from YouTube using yt-dlp
- Supports "download all" and "download only new songs" (based on previous logs)
- Allows custom download folder
- Creates timestamped JSON logs of downloaded tracks
- Cleans up non-MP3 files automatically
- Features a beautiful, colorful terminal UI

## Features

- Paste Spotify playlist URL
- Extract track list (title + artist) using Selenium + headless Chrome
- Download songs as high-quality MP3s (with embedded metadata & thumbnails)
- "New songs only" mode – skips already downloaded tracks (using logs)
- Change default download folder (saved in `data.json`)
- Log every batch with timestamp (`logs/export_YYYY-MM-DD_HH-MM-SS.json`)
- Auto-renames files to clean `Artist - Title.mp3` format

## Preview

<img width=75% alt="Képernyőkép 2026-01-24 215753" src="https://github.com/user-attachments/assets/c1c6db1c-2a8a-4cad-bff3-1c5223258022" />

## Installation

### Prerequisites

- Python 3.9+
- Google Chrome browser installed (required for Selenium)

### Install dependencies

```bash
# Recommended: use a virtual environment
python -m venv venv
source venv/bin/activate      # Linux/macOS
venv\Scripts\activate         # Windows

# Install required packages
pip install -r requirements.txt
```

### Usage
```bash
python main.py  # Windows
python3 main.py # Linux/macOS
```
Or just run the .exe on windows
