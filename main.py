import yt_dlp
import json
import threading
from pytubefix import YouTube
import os
import sys
import subprocess

total = 0
done = 0
PROGRESS_FILE = "progress.json"

def update_progress():
  with open(PROGRESS_FILE, "w") as f:
    json.dump({"done": done, "total": total}, f)

def playlistToJson(playlist_url, output_file="playlist_videos.json"):
  ydl_opts = {'quiet': True, 'extract_flat': True, 'force_generic_extractor': True}
  with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    info = ydl.extract_info(playlist_url, download=False)
    if "entries" in info:
      video_urls = [entry["url"] for entry in info["entries"] if "url" in entry]
      with open(output_file, "w") as f:
        json.dump(video_urls, f, indent=2)
      print(f"Extracted {len(video_urls)} video URLs. Saved to {output_file}")
    else:
      print("No videos found in the playlist.")

def threadStarting(json_file):
  global total
  with open(json_file, "r") as f:
    video_urls = json.load(f)
  total = len(video_urls)
  update_progress()
  for url in video_urls:
    thread = threading.Thread(target=linkToAudioFile, args=(url,))
    thread.start()

def linkToAudioFile(link):
  global done
  yt = YouTube(link)
  stream = yt.streams.get_audio_only(subtype='mp4')
  path = stream.download(output_path='./songs', max_retries=10)
  mp4Tomp3(path)
  done += 1
  update_progress()

def normalize_volume(mp3_file):
  normalized_file = mp3_file.replace('.mp3', '_norm.mp3')
  subprocess.run([
    "ffmpeg", "-y", "-i", mp3_file,
    "-af", "loudnorm=I=-23:TP=-2:LRA=7",
    normalized_file
  ], check=True)
  os.replace(normalized_file, mp3_file)
  os.remove(normalized_file)

def mp4Tomp3(path):
  base, ext = os.path.splitext(path)
  new_file = base + '.mp3'
  os.rename(path, new_file)
  normalize_volume(new_file)

if __name__ == "__main__":
  if len(sys.argv) < 2:
    print("No playlist URL provided.")
    sys.exit(1)
  playlist_url = sys.argv[1]
  playlistToJson(playlist_url)
  threadStarting("playlist_videos.json")
