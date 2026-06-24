import json
import random
import string
from flask import jsonify
from flask_socketio import SocketIO, join_room, leave_room, emit
from enum import Enum
from threading import Timer

class RoomState(Enum):
  LOBBY_1P = 1 # 1 player waiting for 2nd to join
  LOBBY_2P = 2 # 2 players, server waiting for both to be ready
  GAME_ACTIVE = 3
  GAME_FINISH = 4

class PlayerState(Enum):
  CONNECT = 1
  DISCONNECT = 2

def add_player_to_room(room_dict, player_id, room_code, request):
    player_info = room_dict["rooms"][room_code]["player_info"]
    if len(player_info) >= 2:
        emit('room_full', to=request.sid)
        return 1
    
    room_dict["rooms"][room_code]["player_info"].append(player_id) # freshly add player to room and room entry
    room_dict["players"][player_id] = {
        "sid": request.sid,
        "status": PlayerState.CONNECT,
        "room_code": room_code
    }
    room_dict["players_sid"][request.sid] = player_id
    join_room(room_code)
    if len(player_info) == 1: # temporary state stuff
        room_dict["rooms"][room_code]["status"] = RoomState.LOBBY_1P
    if len(player_info) == 2:
        room_dict["rooms"][room_code]["status"] = RoomState.LOBBY_2P
    emit_room_status_switch(room_dict, room_code)

def remove_player_from_room(room_dict, player_id, room_code):
    # remove the client from the room and room entry
    player_info = room_dict["rooms"][room_code]["player_info"]
    leave_room(room_code)
    if player_id in player_info:
        player_info.remove(player_id)

    if (len(player_info)) == 1: # 1 player left, they won
        room_dict["rooms"][room_code]["status"] = RoomState.GAME_FINISH
        emit_room_status_switch(room_dict, room_code)
    if (len(player_info)) == 0: # no players left, delete the room entry
        room_dict["rooms"].pop(room_code, None)
    else:
        print("ATTENTION: player left room but player somehow wasn't even in the room")

    # remove the player/rev index entries from dict
    sid = room_dict["players"][player_id]["sid"]
    room_dict["players_sid"].pop(sid, None)
    room_dict["players"].pop(player_id, None)
    
def handle_disconnect_timer(socketio, room_dict, player_id, room_code):
    # in theory the player status should have just been set to disconnect. 
    # if after 60s the player is still disconnected remove them as if they left
    socketio.sleep(60)
    player_entry = room_dict["players"].get(player_id)

    if player_entry and player_entry["status"] == PlayerState.DISCONNECT:
        remove_player_from_room(room_dict, player_id, room_code)

def emit_room_status_switch(room_dict, room_code):
    match room_dict["rooms"][room_code]["status"]:
        case RoomState.LOBBY_1P:
            emit('create_success_1p', to=room_code)
            return
        case RoomState.LOBBY_2P:
            emit('create_success_2p', to=room_code)
            return
        case RoomState.GAME_ACTIVE:
            emit('play_song', {}, to=room_code)
        case RoomState.GAME_FINISH:
            emit('game_finished', {}, to=room_code)