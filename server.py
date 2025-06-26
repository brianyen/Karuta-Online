from flask import Flask, jsonify, request, send_file, render_template, send_from_directory
import subprocess
import os
import json
import random

app = Flask(__name__)

SONGS_FOLDER = "songs"
PROGRESS_FILE = "progress.json"

@app.route('/')
def home():
  return render_template("index.html")

@app.route('/practice')
def practice():
  return render_template("practice.html")

@app.route('/run-script', methods=['POST'])
def run_script():
  try:
    data = request.json
    playlist_url = data.get("playlist_url")

    if not playlist_url:
      return jsonify({"error": "No playlist URL provided"}), 400

    subprocess.Popen(["python", "main.py", playlist_url])
    return jsonify({"message": "Script started successfully!"})
  except Exception as e:
    return jsonify({"error": str(e)}), 500

@app.route('/progress', methods=['GET'])
def get_progress():
  if os.path.exists(PROGRESS_FILE):
    with open(PROGRESS_FILE, "r") as f:
      return jsonify(json.load(f))
  return jsonify({"done": 0, "total": 0})

@app.route('/clear-songs', methods=['POST'])
def clear_songs():
  try:
    files = [f for f in os.listdir(SONGS_FOLDER) if f.endswith('.mp3')]
    for f in files:
      os.remove(os.path.join(SONGS_FOLDER, f))
    return jsonify({"message": "Songs folder cleared successfully!"})
  except Exception as e:
    return jsonify({"error": str(e)}), 500

@app.route('/get-songs', methods=['GET'])
def get_songs():
  """Returns a list of available MP3 files."""
  files = [f for f in os.listdir(SONGS_FOLDER) if f.endswith('.mp3')]
  return jsonify({"songs": files})

@app.route('/random-song', methods=['GET'])
def random_song():
  files = [f for f in os.listdir(SONGS_FOLDER) if f.endswith('.mp3')]
  if files:
    song = random.choice(files)
    return jsonify({"song": song, "audio_file": f"/songs/{song}"})
  return jsonify({"error": "No songs available"}), 404

@app.route('/songs/<filename>')
def serve_audio(filename):
  return send_file(os.path.join(SONGS_FOLDER, filename))

@app.route('/get-playlists', methods=['GET'])
def get_playlists():
  if not os.path.exists("playlists"):
    return jsonify({"playlists": []})
  files = [f for f in os.listdir("playlists") if f.endswith('.json')]
  return jsonify({"playlists": files})

@app.route('/load-playlist', methods=['GET'])
def load_playlist():
  filename = request.args.get("filename")
  if not filename:
    return jsonify({"error": "No filename provided"}), 400
  filepath = os.path.join("playlists", filename)
  if not os.path.exists(filepath):
    return jsonify({"error": "Playlist not found"}), 404
  with open(filepath, "r") as f:
    songs = json.load(f)
  return jsonify({"songs": songs})

if __name__ == '__main__':
  app.run(debug=True)
