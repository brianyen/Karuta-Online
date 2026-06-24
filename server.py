from flask import Flask, jsonify, request, send_file, render_template, send_from_directory, request
from flask_socketio import SocketIO, join_room, emit
import subprocess
import os
import json
import random
import base64
import string
from dictionary_helpers import *

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
  "players": {},
  "players_sid": {}
}

@socketio.on('connect')
def handle_connect():
  print("User successfully connected.")

@socketio.on('join_game')
def join_game(data):
  try:
    room_key = data.get('room')
    player_id = data.get('player_id')
    if room_key not in room_dict["rooms"]:
      # ATTEMPTING TO JOIN A ROOM THAT DOES NOT EXIST
      emit('room_missing', to=request.sid)
      return
    player_entry = room_dict["players"].get(player_id)
    
    if player_entry and room_key == player_entry["room_code"]:
      # PLAYER EXISTS, REJOINING SAME ROOM 
      join_room(room_key)
      old_sid = player_entry["sid"] # update rev index then update player entry (new SID, status)
      room_dict["players_sid"].pop(old_sid, None)
      room_dict["players_sid"][request.sid] = player_id 
      player_entry["sid"] = request.sid
      player_entry["status"] = PlayerState.CONNECT

      # stuff down here might not be needed. kept for debugging for now mostly
      room_entry = room_dict["rooms"].get(room_key)
      player_info = room_entry["player_info"]
      if player_id not in player_info:
        print("ATTENTION: player seems to be rejoining a room, but they're not in the room's player list")
      if len(player_info) == 1:
        print("ATTENTION: player rejoining and after rejoining, room has 1 person. room should have probably been deconstructed")
      emit_room_status_switch(room_dict, room_key) 
    elif player_id in room_dict["players"]:
      # PLAYER EXISTS, MOVED ROOMS W/O DICT UPDATING (hopefully uncommon branch)
      print("ATTENTION: player with same session joined prev room w/o dict being updated!")
      old_sid = player_entry["sid"] # remove old entry in rev index
      room_dict["players_sid"].pop(old_sid, None)
      prev_room = player_entry["room_code"]

      # if in old room, this player was the last one then handle appropriately
      player_info = room_dict["rooms"][prev_room]["player_info"]
      if player_id in player_info:
        player_info.remove(player_id)
      else:
        print("ATTENTION: i think a player existed but not in the room the dict says they were....")
      if len(player_info) == 1:
        room_dict["rooms"][prev_room]["status"] = RoomState.GAME_FINISH
        emit_room_status_switch(room_dict, prev_room)
        
      add_player_to_room(room_dict, player_id, room_key, request)
    elif player_id not in room_dict["players"]:
      # PLAYER DOES NOT EXIST
      add_player_to_room(room_dict, player_id, room_key, request)
  except Exception as e:
    print(e)
    emit('room_missing', to=request.sid)

@socketio.on('leave_room')
def leave_room(data):
  player_id = data.get('player_id')
  room_key = data.get('room')
  try:
    remove_player_from_room(room_dict, player_id, room_key)
  except Exception as e:
    print(e)

@socketio.on('disconnect')
def disconnect_room(data):
  # some integrity checks, hopefully these won't be needed...
  player_id = room_dict["players_sid"].get(request.sid)
  if player_id == None or player_id not in room_dict["players"]:
    print("ATTENTION: got disconnection message, but the player doesn't even exist in the first place")
    return
  
  # set player status to disconnect --> set timer
  player_entry = room_dict["players"].get(player_id)
  player_entry["status"] = PlayerState.DISCONNECT
  handle_disconnect_timer(socketio, room_dict, player_id, player_entry["room_code"])

@app.route('/')
def home():
  return render_template("index.html")

@app.route('/practice')
def practice():
  return render_template("practice.html")

@app.route('/multiplayer')
def multiplayer():
  room_code = request.args.get("room")
  if room_code in room_dict["rooms"]: # more later
    return render_template("multiplayer.html", room=room_code)
  return jsonify({"error": "Room invalid"}), 500

@app.route('/create-room-rq')
def create_room():
  code = ''.join(random.choices(LETTERS, k=4)).upper()
  while (code in room_dict['rooms']):
    code = ''.join(random.choices(LETTERS, k=4)).upper()
  room_dict['rooms'][code] = {
    "player_info": [],
    "status": RoomState.LOBBY_1P
  }
  return jsonify({ "url": f"/multiplayer?room={code}"})

@app.route('/join-room-rq', methods=['POST'])
def join_room_rq():
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

