import socket
import time
from flask import Flask, render_template
from flask_socketio import SocketIO
import json
import os
import csv

app = Flask(__name__)
socketio = SocketIO(app)

HOST = '127.0.0.1'
PORT = 8888
WRAM_SIZE = 32768
WRAM_START = 0xC000

CHARMAP = {
    0x50: "<END>", 0x7F: " ",
    0x80: "ア", 0x81: "イ", 0x82: "ウ", 0x83: "エ", 0x84: "オ",
    0x85: "カ", 0x86: "キ", 0x87: "ク", 0x88: "ケ", 0x89: "コ",
    0x8A: "サ", 0x8B: "シ", 0x8C: "ス", 0x8D: "セ", 0x8E: "ソ",
    0x8F: "タ", 0x90: "チ", 0x91: "ツ", 0x92: "テ", 0x93: "ト",
}

def load_csv_to_dict(path):
    data = {}
    try:
        with open(path, mode='r', encoding='utf-8') as f:
            for row in csv.reader(f):
                if len(row) >= 2: data[row[0]] = row[1]
    except FileNotFoundError:
        pass
    return data 

def load_json_to_dict(filepath):
    if not os.path.exists(filepath):
        print(f"Error: The file '{filepath}' was not found.")
        return None
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data
    except json.JSONDecodeError as e:
        print(f"Error: Failed to decode JSON. {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None

def get_wram(sock, size):
    sock.sendall(b'\x01')
    chunks = []
    bytes_recd = 0
    while bytes_recd < size:
        chunk = sock.recv(min(size - bytes_recd, 4096))
        if not chunk:
            raise ConnectionError("Socket closed")
        chunks.append(chunk)
        bytes_recd += len(chunk)
    return b''.join(chunks)

def get_range(start, end, data):
    ln = end - start + 1
    return data[start:start + ln] if 0 <= start < len(data) else b""

def decode_text(data):
    s = ""
    for b in data:
        if b == 0x50: break
        if b in CHARMAP:
            s += CHARMAP[b]
        elif 0x80 <= b <= 0xFF:
            s += "?"
        else:
            s += chr(b) if 32 <= b <= 126 else "."
    return s

def get_party_members(data, base):
    total = data[base]
    if total == 0 or total > 6:
        return []
    members = []
    member = base + 0x1
    for i in range(total):
        members.append(f"{data[member]:02X}")
        member += 0x1
    return members

def get_moves(data, base):
    moves = []
    for move in range(4):
        moves.append(f"{data[base]:02X}")
        base += 0x01
    return moves

def get_move_pp(data, base):
    move_pp = []
    for move in range(4):
        move_pp.append(data[base])
        base += 0x01
    return move_pp

def get_dvs(data, base):
    dv_byte1 = data[base]
    dv_byte2 = data[base + 1]
    dv_atk = (dv_byte1 >> 4) & 0x0F
    dv_def = dv_byte1 & 0x0F
    dv_spd = (dv_byte2 >> 4) & 0x0F
    dv_spc = dv_byte2 & 0x0F
    dv_hp = ((dv_atk & 1) << 3) | ((dv_def & 1) << 2) | ((dv_spd & 1) << 1) | (dv_spc & 1)
    dvs = {
        'hp': dv_hp,
        'atk': dv_atk,
        'def': dv_def,
        'spc': dv_spc,
        'spd': dv_spd,
    }
    return dvs

def get_stats(data, base):
    stats = data[base: base+ 14]
    return {
        "pokemon_current_hp": int.from_bytes(stats[0:2], 'big'),
        "pokemon_total_hp": int.from_bytes(stats[2:4], 'big'),
        "pokemon_atk": int.from_bytes(stats[4:6], 'big'),
        "pokemon_def": int.from_bytes(stats[6:8], 'big'),
        "pokemon_spd": int.from_bytes(stats[8:10], 'big'),
        "pokemon_spatk": int.from_bytes(stats[10:12], 'big'),
        "pokemon_spdef": int.from_bytes(stats[12:14], 'big'),
    }


def get_battle_lead_details(data):
    return {
        "species" : f"{data[0xB02]:02X}",
        "item" : f"{data[0xB03]:02X}", 
        "moves" : get_moves(data, 0xB04), 
        "dvs" : get_dvs(data, 0xB08), 
        "moves_pp" : get_move_pp(data, 0xB0A), 
        "happiness" : data[0xB0E], 
        "level" : data[0xB0F], 
        "status" : data[0xB10], 
        "stats" : get_stats(data, 0xB12)
    }

def get_overworld_party_member_details(data, base):
    # base = 0x19F0
    return {
        "species" : f"{data[base]:02X}",
        "item" : f"{data[base + 0x01]:02X}", 
        "moves" : get_moves(data, base + 0x02), 
        "experience" : int.from_bytes(get_range(base + 0x08, base + 0x0A, data), 'big'),
        "dvs" : get_dvs(data, base + 0x15), 
        "moves_pp" : get_move_pp(data, base + 0x17), 
        "happiness" : data[base + 0x1B], 
        "level" : data[base + 0x1F], 
        "status" : data[base + 0x20], 
        "stats" : get_stats(data, base + 0x22)
    }

def get_battle_enemy_details(data):
    base = 0x10DF 
    return {
        "species" : f"{data[base]:02X}",
        "item" : f"{data[base + 0x03]:02X}", 
        "moves" : get_moves(data, base + 0x04), 
        "dvs" : get_dvs(data, base + 0x08), 
        "moves_pp" : get_move_pp(data, base + 0x0A), 
        "level" : data[base + 0x0F], 
        "status" : data[base + 0x10], 
        "stats" : get_stats(data, base + 0x12)
    }

def get_map_details(data):
    base = 0x19c6
    map_data = f"{data[base]:02X}"
    if map_data == "00":
        return "", ""
    map_id_data = f"{data[base + 0x1]:02X}"
    map_group = MAPS[map_data]['name']
    map_id = MAPS[map_data]['maps'][map_id_data]
    return map_group, map_id

def get_player_details(data):
    base = 0x1566
    johto_badge_names = ["Zephyr", "Hive", "Plain", "Fog", "Mineral", "Storm", "Glacier", "Rising"]
    kanto_badge_names = ["Boulder", "Cascade", "Thunder", "Rainbow", "Soul", "Marsh", "Volcano", "Earth"]
    map_group, map_id = get_map_details(data)
    return {
        "id" : int.from_bytes(get_range(0x11B3, 0x11B4, data), 'big'),
        "money" : int.from_bytes(get_range(base, base + 0x2, data), 'big'),
        "mum_money" : int.from_bytes(get_range(base + 0x3, base + 0x5, data), 'big'),
        "coins" : int.from_bytes(get_range(base + 0x7, base + 0x8, data), 'big'),
        "total_item" : data[base + 0x44],
        "johto_badges": [johto_badge_names[i] for i in range(8) if data[base + 0x9] & (1 << i)],
        "kanto_badges": [kanto_badge_names[i] for i in range(8) if data[base + 0xA] & (1 << i)],
        "map_group": map_group,
        "map_id": map_id
    }

def create_stats_table(stats):
    stat_str = f"""
    <table>
      <tr>
        <th></th>
        <th>HP:</th>
        <th>ATK:</th>
        <th>DEF:</th>
        <th>SPA:</th>
        <th>SPD:</th>
        <th>SPE:</th>
      <tr>
        <th>Stats:</th>
        <td>{stats['pokemon_current_hp']}/{stats['pokemon_total_hp']}</th>
        <td>{stats['pokemon_atk']}</th>
        <td>{stats['pokemon_def']}</th>
        <td>{stats['pokemon_spatk']}</th>
        <td>{stats['pokemon_spdef']}</th>
        <td>{stats['pokemon_spd']}</th>
      </tr>
   </table>
    """
    return stat_str

def create_dv_table(dvs):
    dv_str = f"""
    <table>
      <tr>
        <th></th>
        <th>HP:</th>
        <th>ATK:</th>
        <th>DEF:</th>
        <th>SPC:</th>
        <th>SPE:</th>
        <th>   </th>
        <th>   </th>
        <th>   </th>
      <tr>
        <th>DVs:</th>
        <td>{dvs['hp']}</th>
        <td>{dvs['atk']}</th>
        <td>{dvs['def']}</th>
        <td>{dvs['spc']}</th>
        <td>{dvs['spd']}</th>
        <td>   </td>
        <td>   </td>
        <td>   </td>
      </tr>
   </table>
    """
    return dv_str

def create_move_table(moves, moves_pp):
    move_str = """
    <table>
      <tr>
        <th>Name</th>
        <th>Type</th>
        <th>Power</th>
        <th>Accuracy</th>
        <th>PP</th>
      </tr>
    """
    for move, pp in zip(moves, moves_pp):
        if move == "00":
            move_str += f"""
              <tr>
                <td>-</td>
                <td>-</td>
                <td>-</td>
                <td>-</td>
                <td>-</td>
              </tr>
            """
        else:
            move_details = MOVES[move] 
            move_str += f"""
              <tr>
                <td>{move_details['name']}</td>
                <td>{move_details['type']}</td>
                <td>{move_details['power']}</td>
                <td>{move_details['accuracy']}</td>
                <td>{pp}</td>
              </tr>
            """
    move_str += "</table>"
    return move_str

def create_badge_table(johto_badges, kanto_badges):
    if len(johto_badges) == 0:
        return "<table><tr>-</tr></table>" 
    badge_table = "<table><tr>"
    if len(kanto_badges) > 0:
        img_attributes = "decoding='async' loading='lazy' width='25' height='24' referrerpolicy='no-referrer'"
    else:
        img_attributes = "decoding='async' loading='lazy' width='50' height='49' referrerpolicy='no-referrer'"
    badge_count = 0
    for badge in johto_badges:
        badge_count += 1
        badge_table += f"<td><img src='{BADGES.get(badge, 'Oops')}' {img_attributes}><td>"
        if badge_count == 4:
            badge_table += "</tr><tr>"
    if len(kanto_badges) == 0:
        badge_table += "</tr></table>"
        return badge_table
    badge_table += "</tr><tr>"
    badge_count = 0
    for badge in kanto_badges:
        badge_count += 1
        badge_table += f"<td><img src='{BADGES.get(badge, 'Oops')}' {img_attributes}><td>"
        if badge_count == 4:
            badge_table += "</tr><tr>"
    badge_table += "</tr></table>"
    return badge_table
  
def create_party_str(party):
    if len(party) == 0:
        update_overlay('party-poke-sprites', "-")
        return ""
    img_attributes = "decoding='async' loading='lazy' width='60' height='60' referrerpolicy='no-referrer'"
    party_str = "" 
    for member in party: 
        if member == "00":
            continue
        sprite = POKEMON[member]['party_sprite']
        party_str += f"<img alt='' src='{sprite}' {img_attributes}>"
    return party_str

def update_overlay_route_info(player):
    update_overlay("enemy-pokemon-sprite", "-")
    update_overlay("enemy-level", player['map_group'])
    update_overlay("enemy-held-item", player['map_id'])
    update_overlay("enemy-moves", "-")
    update_overlay("enemy-stats", "-")
    update_overlay("enemy-dvs-or-team", "-")

def update_overlay_wild_enemy(enemy):
    if enemy['species'] == "00":
        update_overlay("enemy-pokemon-sprite", "-")
        update_overlay("enemy-level", "-")
        update_overlay("enemy-held-item", "-")
        update_overlay("enemy-moves", "-")
        update_overlay("enemy-stats", "-")
        update_overlay("enemy-dvs-or-team", "-")
        return
    img_attributes = "decoding='async' loading='lazy' width='120' height='120' referrerpolicy='no-referrer'"
    sprite = POKEMON[enemy['species']]['sprite']
    update_overlay("enemy-pokemon-sprite", f"<img alt='' src='{sprite}' {img_attributes}>")
    update_overlay("enemy-level", f"Level: {enemy['level']}")
    update_overlay("enemy-held-item", f"Held item: {ITEMS.get(enemy['item'], 'None')}")
    update_overlay("enemy-moves", create_move_table(enemy['moves'], enemy['moves_pp']))
    update_overlay("enemy-stats", create_stats_table(enemy['stats']))
    update_overlay("enemy-dvs-or-team", create_dv_table(enemy['dvs']))

def update_overlay_enemy(enemy):
    if enemy['species'] == "00":
        update_overlay("enemy-pokemon-sprite", "-")
        update_overlay("enemy-level", "-")
        update_overlay("enemy-held-item", "-")
        update_overlay("enemy-moves", "-")
        update_overlay("enemy-stats", "-")
        return
    img_attributes = "decoding='async' loading='lazy' width='120' height='120' referrerpolicy='no-referrer'"
    sprite = POKEMON[enemy['species']]['sprite']
    update_overlay("enemy-pokemon-sprite", f"<img alt='' src='{sprite}' {img_attributes}>")
    update_overlay("enemy-level", f"Level: {enemy['level']}")
    update_overlay("enemy-held-item", f"Held item: {ITEMS.get(enemy['item'], 'None')}")
    update_overlay("enemy-moves", create_move_table(enemy['moves'], enemy['moves_pp']))
    update_overlay("enemy-stats", create_stats_table(enemy['stats']))

def update_overlay_lead(lead):
    if lead['species'] == "00":
        update_overlay("lead-poke-sprite", "-")
        update_overlay("lead-lvl-happiness", "-")
        update_overlay("lead-held-item", "-")
        update_overlay("lead-moves", "-")
        update_overlay("lead-stats", "-")
        update_overlay("lead-dvs", "-")
        return
    img_attributes = "decoding='async' loading='lazy' width='120' height='120' referrerpolicy='no-referrer'"
    sprite = POKEMON[lead['species']]['sprite']
    update_overlay("lead-poke-sprite", f"<img alt='' src='{sprite}' {img_attributes}>")
    update_overlay("lead-lvl-happiness", f"Level: {lead['level']} Happiness: {lead['happiness']}")
    update_overlay("lead-held-item", f"Held item: {ITEMS.get(lead['item'], 'None')}")
    update_overlay("lead-moves", create_move_table(lead['moves'], lead['moves_pp']))
    update_overlay("lead-stats", create_stats_table(lead['stats']))
    update_overlay("lead-dvs", create_dv_table(lead['dvs']))

def create_player_info_str(player):
    return f"ID: {player['id']} Money: {player['money']}"

def update_overlay(eid, content):
    socketio.emit('update_data', {'id': eid, 'content': content})

def overworld_update(data):
    party = get_party_members(data, 0x19E8)
    player = get_player_details(data)
    lead = get_overworld_party_member_details(data, 0x19F0)
    update_overlay("badge-space", create_badge_table(player['johto_badges'], player['kanto_badges']))
    update_overlay_lead(lead)
    update_overlay("party-poke-sprites", create_party_str(party))
    update_overlay("player-info", create_player_info_str(player))
    update_overlay_route_info(player)

def wild_battle_update(data):
    party = get_party_members(data, 0x19E8)
    lead = get_battle_lead_details(data)
    enemy = get_battle_enemy_details(data)
    update_overlay_lead(lead)
    update_overlay_wild_enemy(enemy)

def trainer_battle_update(data):
    party = get_party_members(data, 0x19E8)
    lead = get_battle_lead_details(data)
    enemy_party = get_party_members(data, 0x1cc6)
    enemy = get_battle_enemy_details(data)
    update_overlay_lead(lead)
    update_overlay_enemy(enemy)
    update_overlay("party-poke-sprites", create_party_str(party))
    update_overlay("enemy-dvs-or-team", create_party_str(enemy_party))


def update_loop():
   with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((HOST, PORT))
        while True:
            try:
                data = get_wram(s, WRAM_SIZE)
                state = data[0x1108]
                match state:
                    case 0: # overworld
                        overworld_update(data)
                    case 1: # wild battle
                        wild_battle_update(data)
                    case 2: # trainer battle
                        trainer_battle_update(data)
                    case _: # lol, I have no clue
                        print(f"Game state: {state}. No update defined")
            except (ConnectionError, BrokenPipeError):
                break
            time.sleep(1)

MAPS = load_json_to_dict('./data/maps.json')
POKEMON = load_json_to_dict('./data/pokemon_data.json')
MOVES = load_json_to_dict('./data/moves_data.json')
BADGES = load_csv_to_dict('./data/badges.csv')
ITEMS = load_csv_to_dict('./data/items.csv')

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == "__main__":
    socketio.start_background_task(update_loop)
    socketio.run(app, debug=False)
