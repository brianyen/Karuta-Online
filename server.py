from flask import Flask, jsonify, request, send_file, render_template, send_from_directory
from flask_socketio import SocketIO, join_room
import subprocess
import os
import json
import random
import base64
import string
from enum import Enum

app = Flask(__name__)
app.config['SECRET_KEY'] = 'password'

socketio = SocketIO(app, async_mode='gevent')

SONGS_FOLDER = "stored-songs"
PROGRESS_FILE = "progress.json"
MAPPING_FOLDER = "custom"
IMAGE_FOLDER = "images"
LETTERS = string.ascii_letters

room_dict = {
  "rooms": {},
  "players": {}
}

class RoomState(Enum):
  LOBBY = 1

class PlayerState(Enum):
  CONNECT = 1
  DISCONNECT = 2

@socketio.on('connect')
def handle_connect():
  print("User successfully connected.")

@socketio.on('join_game')
def join_game(data):
  room = data.get('room')
  join_room(room)
  print(f"User joined room {room}")

@app.route('/')
def home():
  return render_template("index.html")

@app.route('/practice')
def practice():
  return render_template("practice.html")

@app.route('/multiplayer')
def multiplayer():
  room_code = request.args.get("room")
  if room_code in room_dict["rooms"] and len(room_dict["rooms"][room_code]["player_info"]) <= 2: # more later
    return render_template("multiplayer.html", room=room_code)
  return jsonify({"error": "Room invalid"}), 500

@app.route('/create-room-rq')
def create_room():
  code = ''.join(random.choices(LETTERS, k=4)).upper()
  while (code in room_dict['rooms']):
    code = ''.join(random.choices(LETTERS, k=4)).upper()
  room_dict['rooms'][code] = {
    "player_info": [],
    "status": RoomState.LOBBY,
    "disconnect_timer": None
  }
  return jsonify({ "url": f"/multiplayer?room={code}"})

@app.route('/join-room-rq', methods=['POST'])
def join_room():
  try:
    data = request.json
    room_code = data.get("room_code")

    if room_code not in room_dict["rooms"]:
      return jsonify({"url": ""})
    if len(room_dict["rooms"][room_code]["player_info"]) >= 2:
      return jsonify({"url": ""})
    
    return jsonify({"url": f"/multiplayer?room={room_code}"})

  except Exception as e:
    print(e)
    return jsonify({"error": str(e)}), 500

@app.route('/stored-songs/<deckname>/<filename>')
def serve_audio_deck(deckname, filename):
  return send_file(os.path.join(SONGS_FOLDER, deckname, filename))

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

@app.route('/get-mapping', methods=['GET'])
def get_custom_mapping():
  filename = request.args.get("filename")
  path = os.path.join(MAPPING_FOLDER, filename)
  
  if os.path.exists(path):
    with open(path, "r") as f:
      return json.load(f)
  return jsonify({"error": "Custom mapping not found"})

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
  socketio.run(app, debug=True)

