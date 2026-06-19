import yt_dlp
import json
import threading
import os
import sys
import subprocess
import time

total = 0
done = 0
PROGRESS_FILE = "progress.json"
MAX_THREADS = 50
sema = threading.Semaphore(MAX_THREADS)

def update_progress():
    with open(PROGRESS_FILE, "w") as f:
        json.dump({"done": done, "total": total}, f)

def playlistToJson(playlist_url, output_file="playlist_videos.json"):
    ydl_opts = {'quiet': True, 'extract_flat': True, 'force_generic_extractor': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(playlist_url, download=False)
        if "entries" in info:
            video_urls = {"id": info["id"], "urls": [entry["url"] for entry in info["entries"] if "url" in entry]}
            with open(output_file, "w") as f:
                json.dump(video_urls, f, indent=2)
            print(f"Extracted {len(video_urls)} video URLs. Saved to {output_file}")
        else:
            print("No videos found in the playlist.")

def mp4Tomp3(path):
    base, ext = os.path.splitext(path)
    new_file = base + '.mp3'
    os.rename(path, new_file)
    normalize_volume(new_file)
    return os.path.basename(new_file)

def normalize_volume(mp3_file):
    normalized_file = mp3_file.replace('.mp3', '_norm.mp3')
    subprocess.run([
        "ffmpeg", "-y", "-i", mp3_file,
        "-af", "loudnorm=I=-23:TP=-2:LRA=7",
        normalized_file
    ], check=True)
    os.replace(normalized_file, mp3_file)

def linkToAudioFile(link, downloaded_songs, id):
    global done
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': f'./stored-songs/{id}/%(title)s.%(ext)s',
        'quiet': True,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }
    with sema:
        print(f"================ ABOUT TO TRY DOWNLOADING LINK: {link}")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(link, download=True)
            # Prepare the filename and force .mp3 extension
            filename = ydl.prepare_filename(info)
            base, _ = os.path.splitext(filename)
            mp3_file = base + ".mp3"
        # Normalize volume after conversion
        normalize_volume(mp3_file)
        downloaded_songs.append(os.path.basename(mp3_file))
        done += 1
        update_progress()

def threadStarting(json_file):
    global total
    downloaded_songs = []
    with open(json_file, "r") as f:
        json_data = json.load(f)
    id = json_data["id"]
    video_urls = json_data["urls"]
    total = len(video_urls)
    update_progress()
    threads = []
    for url in video_urls:
        thread = threading.Thread(target=linkToAudioFile, args=(url, downloaded_songs, id))
        thread.start()
        threads.append(thread)
    for thread in threads:
        thread.join()
    # Save the downloaded songs list to a JSON file in a separate "playlists" folder.
    if not os.path.exists("playlists"):
        os.makedirs("playlists")
    timestamp = int(time.time())
    playlist_filename = f"playlists/{id}.json"
    with open(playlist_filename, "w") as f:
        json.dump(downloaded_songs, f, indent=2)
    print(f"Downloaded songs list saved to {playlist_filename}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("No playlist URL provided.")
        sys.exit(1)
    playlist_url = sys.argv[1]
    print(f'PLAYLIST URL FOUND: ====== {playlist_url} ======')
    playlistToJson(playlist_url)
    threadStarting("playlist_videos.json")
