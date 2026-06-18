from flask import Flask, jsonify, request, send_file, render_template, send_from_directory
import subprocess
import os
import json
import random
import base64

app = Flask(__name__)

SONGS_FOLDER = "songs"
STORED_SONGS_FOLDER = "stored-songs"
PROGRESS_FILE = "progress.json"
MAPPING_FOLDER = "custom"
IMAGE_FOLDER = "images"

@app.route('/')
def home():
  return render_template("index.html")

@app.route('/practice')
def practice():
  return render_template("practice.html")

@app.route('/edit-deck')
def edit_deck():
  return render_template("edit.html")

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

@app.route('/stored-songs/<deckname>/<filename>')
def serve_audio_deck(deckname, filename):
  return send_file(os.path.join(STORED_SONGS_FOLDER, deckname, filename))

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

@app.route('/write-mapping', methods=['POST'])
def write_custom_mapping():
  try:
    data = request.json
    filename = data.get("filename")
    mapping = data.get("mapping")

    print("filename", filename)
    print("mapping", mapping)

    if not os.path.isdir(MAPPING_FOLDER):
      os.mkdir(MAPPING_FOLDER)
    with open(os.path.join(MAPPING_FOLDER, filename), "w") as f:
      f.write(json.dumps(mapping, indent=4))
    return jsonify({"message": "Mapping saved successfully!"})
  except Exception as e:
    print("Error saving mapping", e)
    return jsonify({"error": str(e)}), 500
   
@app.route('/get-mapping', methods=['GET'])
def get_custom_mapping():
  filename = request.args.get("filename")
  path = os.path.join(MAPPING_FOLDER, filename)
  
  if os.path.exists(path):
    with open(path, "r") as f:
      return json.load(f)
  return jsonify({"error": "Custom mapping not found"})

@app.route('/write-images', methods=['POST'])
def write_custom_images():
  try:
    data = request.json
    filename = data.get("filename")
    image_list = data.get("imageList")
    path = os.path.join(IMAGE_FOLDER, filename)

    if not os.path.isdir(IMAGE_FOLDER):
      os.mkdir(IMAGE_FOLDER)
    if not os.path.isdir(path):
      os.mkdir(path)
    for file in os.listdir(path):
      file_path = os.path.join(path, file)
      if os.path.isfile(file_path):
        os.remove(file_path)
    for obj in image_list:
      if obj["image"]:
        header, encoded = obj["image"].split(',', 1)
        file_ext = header.split('/')[1].split(';')[0]
        file_name = f"{obj["id"]}.{file_ext}"
        file_path = os.path.join(path, file_name)
        img_bytes = base64.b64decode(encoded)
        with open(file_path, "wb") as f:
          f.write(img_bytes)
    
    return jsonify({"message": "Images saved successfully"})
  except Exception as e:
    return jsonify({"error", str(e)}), 500

@app.route('/get-images', methods=['GET'])
def get_custom_images():
  filename = request.args.get("filename")
  path = os.path.join(IMAGE_FOLDER, filename)
  out = {}

  if not os.path.isdir(IMAGE_FOLDER):
      os.mkdir(IMAGE_FOLDER)
  if not os.path.isdir(path):
    os.mkdir(path)
  for file in os.listdir(path):
    file_path = os.path.join(path, file)
    with open(file_path, "rb") as f:
      encoded = base64.b64encode(f.read()).decode('utf-8')
      ext = path.split('.')[-1]
      out[file[:file.rfind('.')]] = f"data:image/{ext};base64,{encoded}"
  try:
    return jsonify(out)
  except Exception as e:
    return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
  app.run(debug=True)

