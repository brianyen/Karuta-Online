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

PROGRESS_FILE = "progress.json"
MAPPING_FOLDER = "custom"
IMAGE_FOLDER = "images"

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
  if player_entry["ready"]:
    player_entry["ready"] = False
    room_dict["rooms"][player_entry["room_code"]]["ready_count"] -= 1
    if (room_dict["rooms"][player_entry["room_code"]]["ready_count"] < 0):
      print("ATTENTION: READY COUNT IN THE NEGATIVES")
  handle_disconnect_timer(socketio, room_dict, player_id, player_entry["room_code"])

@socketio.on('player_ready')
def player_ready(data):
  player_id = data.get('player_id')
  room_key = data.get('room')
  player_entry = room_dict["players"][player_id]
  room_entry = room_dict["rooms"][room_key]

  print(room_entry["status"])
  if room_entry["status"] != RoomState.LOBBY_2P and room_entry["status"] != RoomState.LOBBY_1P:
    return

  if not player_entry["ready"]:
    player_entry["ready"] = True
    room_entry["ready_count"] += 1
    if (room_entry["ready_count"] > 2):
      print("ATTENTION: READY COUNT > 3")

  print("ready_count:", room_entry["ready_count"])
  if (room_entry["ready_count"] == 2):
    song_choice(room_dict, player_id, room_key)
  return

@socketio.on('player_response')
def player_response(data):
  print("entering player response handler")
  player_id = data.get('player_id')
  room_key = data.get('room')
  response_time = data.get('response_time')
  player_entry = room_dict["players"][player_id]
  room_entry = room_dict["rooms"][room_key]

  other_player_id = [id for id in room_entry["player_info"] if id != player_id][0]
  other_player_entry = room_dict["players"][other_player_id]
  other_response_time = other_player_entry["response_time"]

  player_entry["response_time"] = response_time

  if response_time < 0: # tapped out
    player_entry["response_time"] == -2
    if other_response_time == -2: # other player tapped out
      print("both tapped out")
      pass_song(room_dict, player_id, room_key)
    elif other_response_time == -1: # still waiting on other player
      print("one tapped out")
      return
    elif other_response_time >= 0: # other player got the song
      print("one tapped out after other got song")
      declare_round_winner(room_dict, other_player_id, room_key)
    else:
      print("ATTENTION: tracked player response time is negative number besides -1, -2")
  else: # got the card
    player_entry["response_time"] == response_time
    if other_response_time == -2: # other player tapped out
      print("got song while other tapped out")
      declare_round_winner(room_dict, player_id, room_key)
    elif other_response_time == -1: # still waiting on other player
      print("got song")
      handle_card_buffer(socketio, room_dict, player_id, room_key)
    elif other_response_time >= 0: # other player got the song
      if other_response_time > response_time:
        print("got song faster")
        declare_round_winner(room_dict, player_id, room_key)
      elif other_response_time < response_time:
        print("got song slower")
        declare_round_winner(room_dict, other_player_id, room_key)
      elif other_response_time == response_time:
        print("got song at a tie")
        declare_round_winner(room_dict, random.choice([player_id, other_player_id]), room_key)
      else:
        print("ATTENTION: how did we even reach this branch man. response time might be none or something idk")
    else:
      print("ATTENTION: tracked player response time is negative number besides -1, -2")
  return

@socketio.on('player_unready')
def player_unready(data):
  player_id = data.get('player_id')
  room_key = data.get('room')
  player_entry = room_dict["players"][player_id]
  room_entry = room_dict["rooms"][room_key]

  if player_entry["ready"]:
    player_entry["ready"] = False
    room_entry["ready_count"] -= 1
    if (room_entry["ready_count"] < 0):
      print("ATTENTION: READY COUNT IN THE NEGATIVES")
  return

@socketio.on('fault_msg')
def handle_faults(data):
  player_id = data.get('player_id')
  room_key = data.get('room')
  fault_status = data.get('fault_status')
  player_entry = room_dict["players"][player_id]
  room_entry = room_dict["rooms"][room_key]

  other_player_id = [id for id in room_entry["player_info"] if id != player_id][0]
  other_player_entry = room_dict["players"][other_player_id]
  other_fault_status = other_player_entry["fault_status"]

  fault_args = { player_id: 0, other_player_id: 0 }

  if other_fault_status == 0:
    player_entry["fault_status"] = fault_status
  else:
    if other_fault_status == -1:
      if fault_status == -1:
        pass
      elif fault_status == 1:
        fault_args[player_id] = 1
        player_entry["cards_left"] += 1
        other_player_entry["cards_left"] -= 1
      else:
        print("ATTENTION: bad fault status 1", fault_status, other_fault_status)
    elif other_fault_status == 1:
      fault_args[other_player_id] = 1
      if fault_status == -1:
        player_entry["cards_left"] -= 1
        other_player_entry["cards_left"] += 1
      elif fault_status == 1:
        fault_args[player_id] = 1
      else:
        print("ATTENTION: bad fault status 2:", fault_status, other_fault_status)
    else:
      print("ATTENTION: bad fault status 3:", fault_status, other_fault_status)

  # need to check if there's a winner after faults
  if player_entry["cards_left"] == 0:
    declare_game_winner(room_dict, player_id, room_key)
  elif other_player_entry["cards_left"] == 0:
    declare_game_winner(room_dict, other_player_id, room_key)
  else:
    room_entry["status"] = RoomState.LOBBY_2P
    emit('fault_response', {"args": fault_args}, to=room_key)

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

@app.route('/create-room-rq', methods=['POST'])
def create_room():
  try:
    deck_name = request.json.get("deck")
    code = ''.join(random.choices(LETTERS, k=4)).upper()
    while (code in room_dict['rooms']):
      code = ''.join(random.choices(LETTERS, k=4)).upper()

    return init_room(room_dict, code, deck_name)
  except Exception as e:
    print(e)
    return jsonify({"error": str(e)}), 500
  
@app.route('/replay-room-rq', methods=['POST'])
def replay_room():
  try:
    deck_name = request.json.get("deck")
    code = request.json.get("code")
  
    if room_dict["rooms"].get(code) == None:
      return init_room(room_dict, code, deck_name)
    return jsonify({ "url": f"/multiplayer?room={code}"})
  except Exception as e:
    print(e)
    return jsonify({"error": str(e)}), 500

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
  print("serving audio now...")
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

