import json
import random
import string
import os
from flask import jsonify
from flask_socketio import join_room, leave_room, emit
from enum import Enum
from mutagen import File
from pathlib import Path
from urllib.parse import quote

SONGS_FOLDER = "stored-songs"
METADATA_FOLDER = "metadata"
MAPPING_FOLDER = "custom"
IMAGE_FOLDER = "images"
BUCKET_URL = "https://karuta-worker.workers-larp2011.workers.dev"

LETTERS = string.ascii_letters

class RoomState(Enum):
  LOBBY_1P = 1 # 1 player waiting for 2nd to join
  LOBBY_2P = 2 # 2 players, server waiting for both to be ready
  STARTED_SYNC = 3
  STARTED_SONG = 4
  RESULTS_SENT = 5
  GAME_FINISH = 6

class PlayerState(Enum):
  CONNECT = 1
  DISCONNECT = 2

def add_player_to_room(room_dict, player_id, room_code, request):
    player_info = room_dict["rooms"][room_code]["player_info"]
    room_entry = room_dict["rooms"][room_code]
    if len(player_info) >= 2:
        emit('room_full', to=request.sid)
        return 1
    
    player_info.append(player_id) # freshly add player to room and room entry
    room_dict["players"][player_id] = {
        "sid": request.sid,
        "status": PlayerState.CONNECT,
        "room_code": room_code,
        "ready": False,
        "sync_ready": False,
        # "cards": [],
        "cards_left": len(room_entry["available_songs"]) // 2,
        "response_time": -1,
        "fault_status": 0,
    }
    room_dict["players_sid"][request.sid] = player_id
    join_room(room_code)
    if len(player_info) == 1: # temporary state stuff
        room_entry["status"] = RoomState.LOBBY_1P
    if len(player_info) == 2 and room_entry["status"] == RoomState.LOBBY_1P:
        room_entry["status"] = RoomState.LOBBY_2P
    emit_room_status_switch(room_dict, room_code)

def remove_player_from_room(room_dict, player_id, room_code):
    # remove the client from the room and room entry
    player_info = room_dict["rooms"][room_code]["player_info"]
    player_entry = room_dict["players"][player_id]
    leave_room(room_code)
    if player_id in player_info:
        player_info.remove(player_id)

    if player_entry["ready"]:
        room_dict["rooms"][room_code]["ready_count"] -= 1
        if (room_dict["rooms"][room_code]["ready_count"] < 0):
            print("ATTENTION: READY COUNT IN THE NEGATIVES")
    if (len(player_info)) == 1: # 1 player left, they won
        room_dict["rooms"][room_code]["status"] = RoomState.GAME_FINISH
        emit_room_status_switch(room_dict, room_code)
    if (len(player_info)) == 0: # no players left, delete the room entry
        room_dict["rooms"].pop(room_code, None)

    # remove the player/rev index entries from dict
    sid = player_entry["sid"]
    room_dict["players_sid"].pop(sid, None)
    room_dict["players"].pop(player_id, None)
    
def handle_disconnect_timer(socketio, room_dict, player_id, room_code):
    # in theory the player status should have just been set to disconnect. 
    # if after 60s the player is still disconnected remove them as if they left
    socketio.sleep(60)
    player_entry = room_dict["players"].get(player_id)

    if player_entry and player_entry["status"] == PlayerState.DISCONNECT:
        remove_player_from_room(room_dict, player_id, room_code)

def song_choice(room_dict, player_id, room_code, from_join=False):
    room_entry = room_dict["rooms"][room_code]
    if len(room_entry["all_songs"]) == 0:
        # hopefully doesn't happen too often (can happen if both players tap out, i guess)
        room_entry["status"] = RoomState.GAME_FINISH
        emit_room_status_switch(room_dict, room_code)
    next_song = room_entry["all_songs"].pop(random.randint(0, len(room_entry["all_songs"]) - 1))
    if next_song in room_entry["unplayed_songs"]:
        room_entry["unplayed_songs"].remove(next_song)
    room_entry["status"] = RoomState.STARTED_SYNC
    room_entry["ready_count"] = 0
    room_entry["current_song"] = next_song
    
    reset_players(room_dict, room_code)
    deckstem = Path(room_entry["deck_name"]).stem

    emit('start_sync', { "audio_url": os.path.join(BUCKET_URL, SONGS_FOLDER, deckstem, quote(next_song)) }, to=room_code)

def pass_song(room_dict, player_id, room_code):
    # switch this part to looking through each player's array to find the song. for now, sides dont exist so just look through "available_songs"
    room_entry = room_dict["rooms"][room_code]
    current_song = room_entry["current_song"]
    available_songs = room_entry["available_songs"]
    unplayed_songs = room_entry["unplayed_songs"]
    update = { "winner": "", "remove": "", "add": "" }

    if current_song in available_songs: # need to reroll
        update["remove"] = current_song
        available_songs.remove(current_song)
        if len(unplayed_songs) >= 1: # at least one dead song exists, add it
            next_song = unplayed_songs.pop(0)
            available_songs.append(next_song)
            update["add"] = next_song
        else:   
            for id in room_entry["player_info"]:
                room_dict["players"][id]["cards_left"] -= 1

    emit("round_results", update, to=room_code)
    room_entry["status"] = RoomState.RESULTS_SENT
    room_entry["current_song"] = ""
    reset_players(room_dict, room_code)

def declare_round_winner(room_dict, player_id, room_code):
    room_entry = room_dict["rooms"][room_code]
    current_song = room_entry["current_song"]
    player_entry = room_dict["players"][player_id]
    player_entry["cards_left"] -= 1
    available_songs = room_entry["available_songs"]
    update = { "winner": player_id, "remove": current_song, "add": "" }

    if current_song in available_songs:
        available_songs.remove(current_song)
    else: 
        print("ATTENTION: round was won on some song but it's no longer in the dictionary's available songs")

    emit("round_results", update, to=room_code)
    room_entry["status"] = RoomState.RESULTS_SENT
    room_entry["current_song"] = ""
    reset_players(room_dict, room_code)
    return

def declare_game_winner(room_dict, player_id, room_code):
    room_dict["rooms"][room_code]["status"] = RoomState.GAME_FINISH
    emit_room_status_switch(room_dict, room_code, winner=player_id)
    return

def handle_card_buffer(socketio, room_dict, player_id, room_code):
    room_entry = room_dict["rooms"][room_code]
    saved_song = room_entry["current_song"]
    socketio.sleep(1)

    if saved_song != room_entry["current_song"]: # other logic already handled everything
        return

    player_entry = room_dict["players"][player_id]
    player_response_time = player_entry["response_time"]

    other_player_id = [id for id in room_entry["player_info"] if id != player_id][0]
    other_player_entry = room_dict["players"][other_player_id]
    other_response_time = other_player_entry["response_time"]

    if (other_response_time < 0) or (other_response_time > player_response_time):
        declare_round_winner(room_dict, player_id, room_code)
    else:
        declare_round_winner(room_dict, other_player_id, room_code)

def reset_players(room_dict, room_code):
    room_entry = room_dict["rooms"].get(room_code)
    for pid in room_entry["player_info"]:
        player_entry = room_dict["players"][pid]
        player_entry["ready"] = False
        player_entry["sync_ready"] = False
        player_entry["response_time"] = -1
        player_entry["fault_status"] = 0

def init_room(room_dict, room_code, deck):
    filepath = os.path.join("playlists", deck)
    all_songs = []
    with open(filepath, "r") as f:
      all_songs = json.load(f)
    random.shuffle(all_songs)

    room_dict['rooms'][room_code] = {
      "player_info": [],
      "status": RoomState.LOBBY_1P,
      "deck_name": deck,
      "all_songs": all_songs,
      "available_songs": all_songs[:(len(all_songs) // 4) * 2], # replace with per-playing tracking eventually
      "unplayed_songs": all_songs[(len(all_songs) // 4) * 2:],
      "ready_count": 0,
      "sync_count": 0,
      "current_song": ""
    }

    with open(os.path.join(METADATA_FOLDER, deck), 'r') as f:
        metadata = json.load(f)
        room_dict["rooms"][room_code]["metadata"] = metadata

    return jsonify({ "url": f"/multiplayer?room={room_code}"})

def emit_room_status_switch(room_dict, room_code, winner=""):
    room_entry = room_dict["rooms"][room_code]
    send_params = {
        "deck": room_entry["deck_name"],
        "songs": room_entry["available_songs"],
        "scores": {}
    }

    for id in room_entry["player_info"]:
        send_params["scores"][id] = room_dict["players"][id]["cards_left"]

    match room_entry["status"]:
        case RoomState.LOBBY_1P:
            emit('1p_room', send_params, to=room_code)
            return
        case RoomState.LOBBY_2P:
            emit('2p_room', send_params, to=room_code)
            return
        case RoomState.STARTED_SYNC:
            emit('re_emission', send_params, to=room_code)
        case RoomState.STARTED_SONG:
            emit('re_emission', send_params, to=room_code)
            return
        case RoomState.RESULTS_SENT:
            emit('re_emission', send_params, to=room_code)
            return
        case RoomState.GAME_FINISH:
            code = ''.join(random.choices(LETTERS, k=4)).upper()
            while (code in room_dict['rooms']):
                code = ''.join(random.choices(LETTERS, k=4)).upper()
            send_params["winner"] = winner
            send_params["next_code"] = code
            emit('game_finished', send_params, to=room_code)
            for id in room_entry["player_info"]:
                room_dict["players"].pop(id, None)
            room_dict["rooms"].pop(room_code, None)