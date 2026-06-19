# Getting Started

Create venv with
```bash
python3 -m venv /path/to/venv
```

Activate venv with
```bash
source /path/to/venv
```

Install libraries with
```bash
pip install -r requirements.txt
```

To run webpage
```bash
python3 server.py
```

Open link shown in terminal

Note: if yt-dlp is bugging you about a JS runtime when you try downloading, try following the steps here: `https://github.com/yt-dlp/yt-dlp/wiki/EJS`. If you are receiving 403 forbidden errors from yt-dlp, it is possible either yt-dlp is not updated (try `pip install -U "yt-dlp[default,curl-cffi]"`) or YouTube has broken yt-dlp temporarily.