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
from threading import Lock
from collections import deque
import time

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

def add_player_to_room(socketio, room_dict, player_id, room_code, request):
    room_entry = room_dict["rooms"][room_code]
    room_full = False
    with room_entry["lock"]:
        player_info = room_dict["rooms"][room_code]["player_info"]
        if len(player_info) < 2:
            player_info.append(player_id) # freshly add player to room and room entry
            room_dict["players"][player_id] = {
                "sid": request.sid,
                "status": PlayerState.CONNECT,
                "room_code": room_code,
                "ready": False,
                "sync_ready": False,
                "cards": [],
                "cards_left": len(room_entry["available_songs"]) // 2,
                "response_time": -1,
                "fault_status": 0,
                "rtts": deque(maxlen=5)
            }
            room_dict["players_sid"][request.sid] = player_id
            ping_cycle(socketio, room_dict, player_id, request)
        else:
            room_full = True
    if room_full:
        emit('room_full', to=request.sid)
        return 1
    
    join_room(room_code)
    with room_entry["lock"]:
        if len(player_info) == 1: # temporary state stuff
            room_entry["status"] = RoomState.LOBBY_1P
        if len(player_info) == 2 and room_entry["status"] == RoomState.LOBBY_1P: # hopefully this only happens on game init
            # possibly the worst two lines of code i've ever written
            room_dict["players"][room_entry["player_info"][0]]["cards"] = room_entry["available_songs"][:round(len(room_entry["available_songs"]) / 2)]
            room_dict["players"][room_entry["player_info"][1]]["cards"] = room_entry["available_songs"][round(len(room_entry["available_songs"]) / 2):]

            room_entry["status"] = RoomState.LOBBY_2P
    emit_room_status_switch(room_dict, room_code)

def remove_player_from_room(room_dict, player_id, room_code):
    # remove the client from the room and room entry
    player_info = room_dict["rooms"][room_code]["player_info"]
    player_entry = room_dict["players"][player_id]
    leave_room(room_code)
    re_emit = False
    

    with room_dict["rooms"][room_code]["lock"]:
        if player_id in player_info:
            player_info.remove(player_id)

        if player_entry["ready"]:
            room_dict["rooms"][room_code]["ready_count"] -= 1
            if (room_dict["rooms"][room_code]["ready_count"] < 0):
                print("ATTENTION: READY COUNT IN THE NEGATIVES")
        if (len(player_info)) == 1: # 1 player left, they won
            room_dict["rooms"][room_code]["status"] = RoomState.GAME_FINISH
            re_emit = True
        if (len(player_info)) == 0: # no players left, delete the room entry
            room_dict["rooms"].pop(room_code, None)

        # remove the player/rev index entries from dict
        sid = player_entry["sid"]
        room_dict["players_sid"].pop(sid, None)
        room_dict["players"].pop(player_id, None)

    if re_emit:
        emit_room_status_switch(room_dict, room_code)
    
def handle_disconnect_timer(socketio, room_dict, player_id, room_code, sid):
    # in theory the player status should have just been set to disconnect. 
    # if after 60s the player is still disconnected remove them as if they left
    socketio.sleep(60)
    player_entry = room_dict["players"].get(player_id)

    if player_entry and player_entry["status"] == PlayerState.DISCONNECT and room_code == player_entry["room_code"]:
        if sid != room_dict["players_sid"].get(player_id):
            remove_player_from_room(room_dict, player_id, room_code)

def ping_cycle(socketio, room_dict, player_id, request):
    outlying_ping = False
    ping_timestamp = time.time()
    player_entry = room_dict["players"].get(player_id)
    rtt_queue = player_entry.get("rtts")
    if player_entry == None or rtt_queue == None:
        return

    def ping_response():
        if room_dict["players"].get(player_id) == None:
            return
        nonlocal outlying_ping
        outlying_ping = False
        rtt = time.time() - ping_timestamp

        if len(rtt_queue) >= 5:
            rtt_queue.popleft()
        rtt_queue.append(rtt)
    
    while True:
        if room_dict["players"].get(player_id) == None:
            return
        sid = room_dict["players_sid"].get(player_id)
        if sid == None:
            return
        if outlying_ping:
            if len(rtt_queue) >= 5:
                rtt_queue.popleft()
            rtt_queue.append(3)
            
            ping_timestamp = time.time()
            outlying_ping = True
            socketio.emit('ping_check', to=sid, callback=ping_response)
        else:
            ping_timestamp = time.time()
            outlying_ping = True
            socketio.emit('ping_check', to=sid, callback=ping_response)
        socketio.sleep(5)

def song_choice(room_dict, player_id, room_code, from_join=False):
    room_entry = room_dict["rooms"][room_code]
    re_emit = False
    with room_entry["lock"]:
        if len(room_entry["all_songs"]) == 0:
            # hopefully doesn't happen too often (can happen if both players tap out, i guess)
            room_entry["status"] = RoomState.GAME_FINISH
            re_emit = True
        next_song = room_entry["all_songs"].pop(random.randint(0, len(room_entry["all_songs"]) - 1))
        if next_song in room_entry["unplayed_songs"]:
            room_entry["unplayed_songs"].remove(next_song)
        room_entry["status"] = RoomState.STARTED_SYNC
        room_entry["ready_count"] = 0
        room_entry["current_song"] = next_song
        reset_players(room_dict, room_code)
    
    if re_emit:
        emit_room_status_switch(room_dict, room_code)
    else:
        deckstem = Path(room_entry["deck_name"]).stem

        emit('start_sync', { "audio_url": os.path.join(BUCKET_URL, SONGS_FOLDER, deckstem, quote(next_song)) }, to=room_code)

def pass_song(room_dict, player_id, room_code):
    # switch this part to looking through each player's array to find the song. for now, sides dont exist so just look through "available_songs"
    room_entry = room_dict["rooms"][room_code]
    update = { "winner": "", "remove": "", "add": "" }
    with room_entry["lock"]:
        current_song = room_entry["current_song"]
        unplayed_songs = room_entry["unplayed_songs"]
        for id in room_entry["player_info"]:
            player_entry = room_dict["players"][id]
            player_songs = player_entry["cards"]

            if current_song in player_songs:
                update["remove"] = current_song
                player_songs.remove(current_song)
                if len(unplayed_songs) >= 1:
                    next_song = unplayed_songs.pop(0)
                    player_songs.append(next_song)
                    update["add"] = next_song
                else:
                    for id in room_entry["player_info"]:
                        room_dict["players"][id]["cards_left"] -= 1

        room_entry["status"] = RoomState.RESULTS_SENT
        room_entry["current_song"] = ""
        reset_players(room_dict, room_code)

    emit("round_results", update, to=room_code)

def declare_round_winner(room_dict, player_id, room_code):
    room_entry = room_dict["rooms"][room_code]
    update = {}
    with room_entry["lock"]:
        current_song = room_entry["current_song"]
        update = { "winner": player_id, "remove": current_song, "add": "" }
        player_entry = room_dict["players"][player_id]
        player_entry["cards_left"] -= 1

        for id in room_entry["player_info"]:
            player_entry = room_dict["players"][id]
            player_songs = player_entry["cards"]

            if current_song in player_songs:
                update["remove"] = current_song
                player_songs.remove(current_song)

        room_entry["status"] = RoomState.RESULTS_SENT
        room_entry["current_song"] = ""
        reset_players(room_dict, room_code)

    emit("round_results", update, to=room_code)

def declare_game_winner(room_dict, player_id, room_code):
    room_dict["rooms"][room_code]["status"] = RoomState.GAME_FINISH
    emit_room_status_switch(room_dict, room_code, winner=player_id)
    return

def handle_card_buffer(socketio, room_dict, player_id, room_code):
    room_entry = room_dict["rooms"][room_code]
    saved_song = room_entry["current_song"]

    to_sleep = 0.5
    with room_entry["lock"]:
        for id in room_entry["player_info"]:
            rtt_queue = room_dict["players"][id].get("rtts")
            for rtt in rtt_queue:
                to_sleep = max(to_sleep, 1.3 * rtt)

    print("to_sleep chosen to be:", to_sleep)
    socketio.sleep(to_sleep)

    with room_entry["lock"]:
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
      "current_song": "",
      "lock": Lock()
    }

    with open(os.path.join(METADATA_FOLDER, deck), 'r') as f:
        metadata = json.load(f)
        room_dict["rooms"][room_code]["metadata"] = metadata

    return jsonify({ "url": f"/multiplayer?room={room_code}"})

def emit_room_status_switch(room_dict, room_code, winner=""):
    room_entry = room_dict["rooms"][room_code]
    with room_entry["lock"]:
        send_params = {
            "deck": room_entry["deck_name"],
            "songs": {},
            "scores": {} # replace with actual  length i guess
        }

        for id in room_entry["player_info"]:
            send_params["scores"][id] = room_dict["players"][id]["cards_left"]
            send_params["songs"][id] = room_dict["players"][id]["cards"]

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
            for id in room_entry["player_info"]:
                remove_player_from_room(room_dict, id, room_code)
            room_dict["rooms"].pop(room_code, None)
            emit('game_finished', send_params, to=room_code)