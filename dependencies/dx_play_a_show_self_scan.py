import random
from fuzzywuzzy import process
import os
import configparser
import json
from pathlib import Path
import sys
import pprint
import json

# removes any comments from a RB dta, and then returns a nice, tokenized list to parse
def clean_dta(dta_path: Path) -> list:
    with open(dta_path, encoding="latin1") as f:
        lines = [line.lstrip() for line in f]
    reduced_lines = [x.split(";", 1)[0] for x in lines]
    dta_as_str = ''.join(reduced_lines)
    dta_as_list = dta_as_str.replace("(", " ( ").replace(")", " ) ").split()
    return dta_as_list

# parse, read_from_tokens, and atom have all been originally written by Peter Norvig
# parse and atom have been tweaked for the purposes of parsing RB dtas
# explanations of his functions can be found here: http://norvig.com/lispy.html
def parse(program: list):
    "Read a Scheme expression from a string."
    program.insert(0, "(")
    program.append(")")
    return read_from_tokens(program)

def read_from_tokens(tokens: list):
    "Read an expression from a sequence of tokens."
    if len(tokens) == 0:
        raise SyntaxError('unexpected EOF')
    token = tokens.pop(0)
    if token == '(':
        L = []
        while tokens[0] != ')':
            L.append(read_from_tokens(tokens))
        tokens.pop(0)  # pop off ')'
        return L
    elif token == ')':
        raise SyntaxError('unexpected )')
    else:
        return atom(token)

def atom(token: str):
    "Numbers become numbers; every other token is a symbol."
    try:
        return int(token)
    except ValueError:
        try:
            return float(token)
        except ValueError:
            return (str(token)).strip("'").strip('"')

# clean up name entry in case there are parentheses in the song title (i.e. (Don't Fear) The Reaper)
def dict_from_name(parsed_name) -> str:
    new_song_name_list = []
    for s in range(len(parsed_name)):
        if s > 0:
            if type(parsed_name[s]) == list:
                new_song_name_list.append("(" + " ".join(str(x) for x in parsed_name[s]) + ")")
            elif parsed_name[s] != "":
                new_song_name_list.append(str(parsed_name[s]))
    return " ".join(new_song_name_list)

# parse song part difficulties and return a dict
def dict_from_rank(parsed_rank: list):
    rank_dict = {}
    for rank in parsed_rank:
        if type(rank) == list:
            rank_dict[rank[0]] = rank[1]
    return rank_dict

# parse song info (pans, vols, etc) and return a dict
def dict_from_song(parsed_song: list):
    song_info_dict = {}
    try:
        for info in parsed_song:
            if type(info) == list:
                if "drum_" in info[0]:
                    song_info_dict[info[0]] = {}
                    song_info_dict[info[0]][info[1][0]] = info[1][1]
                elif info[0] == "name":
                    song_info_dict[info[0]] = dict_from_name(info[1])
                # elif info[0] == "song":
                #    song_info_dict[info[0]] = dict_from_song(info[1])
                elif info[0] == "rank":
                    song_info_dict[info[0]] = dict_from_rank(info[1])
                elif info[0] in ["crowd_channels"]:
                    song_info_dict[info[0]] = info[1:]
                elif info[0] not in ["tracks", "pans", "vols", "preview", "anim_tempo", "bank",
                                     "song_scroll_speed", "midi_file", "drum_freestyle", "drum_solo",
                                     "solo", "version", "format", "album_art", "tuning_offset_cents",
                                     "ugc", "context", "downloaded", "base_points", "cores", "seqs", "hopo_threshold", "song"]:
                    song_info_dict[info[0]] = info[1]
    except Exception as e:
        print(f"Error processing song info: {e}")
    return song_info_dict

# convert the list of lists that parse returns into a big song dictionary
def dict_from_parsed(parsed: list):
    keys_to_ignore = ["song", "master", "context", "bank", "anim_tempo", "preview", 
                      "decade", "unlockable", "song_location", "downloaded", "exported",
                      "album_art", "version", "format", "song_id", "tuning_offset_cents",
                      "game_origin", "encoding", "song_tonality", "real_guitar_tuning", "real_bass_tuning",
                      "album_track_number", "song_scroll_speed", "guide_pitch_volume", "ugc"]

    big_songs_dict = {}
    for song in parsed:
        song_dict = {}
        shortname = None  # Initialize shortname variable
        skip_entry = False  # Flag to skip processing

        for a in range(len(song)):
            if skip_entry:
                skip_entry = False
                continue

            if a == 0:  # the shortname
                shortname = song[0]
                song_dict["shortname"] = shortname  # Include shortname in the entry
            elif song[a][0] == "name":
                song_dict["name"] = dict_from_name(song[a])
            elif song[a][0] == "rank":
                song_dict["rank"] = dict_from_rank(song[a])
            elif song[a][0] in keys_to_ignore:
                skip_entry = True
            else:
                val = []
                for b in range(len(song[a])):
                    if b == 0:
                        key = song[a][b]
                    else:
                        val.append(song[a][b])
                if all(isinstance(item, str) for item in val):
                    song_dict[key] = (" ".join(x for x in val)).strip('"')
                else:
                    song_dict[key] = val if len(val) > 1 else val[0]

        if shortname is not None:  # Check if shortname is not empty
            big_songs_dict[shortname] = song_dict

    return big_songs_dict

# the main parse function - supply a path to a dta, and it will return a big song dictionary
def parse_dta(dta_path: Path, rpcs3_path: Path) -> dict:
    print(dta_path)
    parsed = parse(clean_dta(dta_path))
    parsed_dta_dict = dict_from_parsed(parsed)
    #pprint.pprint(parsed_dta_dict, sort_dicts=False)
    return parsed_dta_dict

def read_json(json_file_path):
    try:
        with open(json_file_path, 'r') as file:
            data = json.load(file)
        return data
    except FileNotFoundError:
        print(f"Error: JSON file '{json_file_path}' not found. Please make sure the file exists.")
        return None
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON file '{json_file_path}': {e}")
        return None

def get_random_artist(data):
    artists = {song["artist"] for song in data.values() if "artist" in song and isinstance(song["artist"], str)}
    return random.choice(list(artists)) if artists else None

def get_random_year(data):
    years = {song.get("year", song.get("year_released")) for song in data.values() if "year" in song or "year_released" in song}
    #print("All years:", years)  # Add this line to print all years
    return random.choice(list(years)) if years else None

def get_random_genre(data):
    genres = {song["genre"] for song in data.values() if "genre" in song}
    return random.choice(list(genres)) if genres else None

def get_random_song(data):
    song = random.choice(list(data.values()))
    return song["name"], song["artist"]

def eval_random_song(data):
    song = random.choice(list(data.values()))
    return song["name"], song["artist"], song["shortname"]

def clear_playlist(output_file):
    with open(output_file, 'w') as output:
        output.write("")
    print(f"Playlist cleared in {output_file}")

def get_random_song_from_artist(data, artist):
    artist_songs = [song for song in data.values() if "artist" in song and isinstance(song["artist"], str) and song["artist"] == artist]

    if not artist_songs:
        print(f"No songs found for the artist '{artist}'.")
        return None

    song = random.choice(artist_songs)
    return song["name"], song["artist"]

def fuzzy_search(data, config_file, target_title, rpcs3_path):
    output_file_path = rpcs3_path / "dev_hdd0" / "game" / "BLUS30463" / "USRDIR" / "dx_playlist.dta"

    if target_title.startswith('genre:'):
        genre_to_search = target_title[len('genre:'):].strip()
        genre_matches = [
            (song["name"], song["artist"], song["shortname"])
            for song in data.values()
            if "genre" in song and genre_to_search.lower() == song["genre"].lower()
        ]

        if genre_matches:
            random_song_title, random_artist, random_short_name = random.choice(genre_matches)
            print(f"Random song matching genre '{genre_to_search}': '{random_song_title}' by '{random_artist}'")
            append_short_name_to_output(output_file_path, random_short_name, rpcs3_path)
        else:
            print(f"No songs found in the genre '{genre_to_search}'.")
    elif target_title.startswith('year:'):
        year_to_search = target_title[len('year:'):].strip()
        year_matches = [
            (song["name"], song["artist"], song["shortname"]) 
            for song in data.values() 
            if ("year_released" in song and str(year_to_search) == str(song["year_released"])) or ("year" in song and year_to_search == song["year"])
        ]

        if year_matches:
            random_song_title, random_artist, random_short_name = random.choice(year_matches)
            print(f"Random song from the year '{year_to_search}': '{random_song_title}' by '{random_artist}'")
            append_short_name_to_output(output_file_path, random_short_name, rpcs3_path)
        else:
            print(f"No songs found in the year '{year_to_search}'.")
    elif target_title == 'csv':
        song_title, artist = get_random_song(data)
        print(f"Random song title from the JSON file: '{song_title}' by '{artist}'")
    elif target_title.startswith('artist:'):
        artist_to_search = target_title[len('artist:'):].strip()
        artist_matches = [
            (song.get("name", ""), song.get("artist", ""), song.get("shortname", ""))
            for song in data.values()
            if "artist" in song and isinstance(song["artist"], str) and artist_to_search.lower() == song["artist"].lower()
        ]

        if artist_matches:
            random_song_title, random_artist, random_short_name = random.choice(artist_matches)
            print(f"Random song by artist '{artist_to_search}': '{random_song_title}' by '{random_artist}'")
            append_short_name_to_output(output_file_path, random_short_name, rpcs3_path)
        else:
            print(f"No songs found for the artist '{artist_to_search}'.")
    elif target_title.startswith('title:'):
        title_to_search = target_title[len('title:'):].strip()
        title_matches = process.extract(
            title_to_search, 
            [(song.get("name", ""), song.get("artist", ""), song.get("shortname", ""))
             for song in data.values()],
            limit=1
        )

        if title_matches and title_matches[0][1] >= 80:  # Adjust the threshold as needed
            random_song_title, random_artist, random_short_name = title_matches[0][0]
            print(f"Random song with title '{title_to_search}': '{random_song_title}' by '{random_artist}'")
            append_short_name_to_output(output_file_path, random_short_name, rpcs3_path)
        else:
            print(f"No songs found with a similar title to '{title_to_search}'.")

def append_short_name_to_output(output_file, short_name, rpcs3_path):
    output_file = str(output_file).strip('\"')  # Convert to string before stripping

    with open(output_file, 'r') as output:
        existing_content = output.read().strip()

    existing_short_names = [s.strip('()') for s in existing_content.split()]

    existing_short_names.append(short_name)

    with open(output_file, 'w') as output:
        output.write(f"({' '.join(existing_short_names)})")

    print(f"Short Name '({short_name})' appended to {output_file}")

def refresh_options(data):
    year = get_random_year(data)
    artist = get_random_artist(data)
    song_title, _ = get_random_song(data)
    random_song_name = {get_random_song(data)}
    genre = get_random_genre(data)
    song_title_direct, artist_direct, short_name_direct = eval_random_song(data)
    print(" ")
    return year, artist, song_title, genre, song_title_direct, artist_direct, short_name_direct

def get_rpcs3_path():
    rpcs3_path = input("Enter the path for RPCS3: ")
    rpcs3_path = Path(rpcs3_path)
    
    if not rpcs3_path.is_dir():
        print("Invalid RPCS3 path provided.")
        exit()

    return rpcs3_path

def parse_and_export_to_json():
    rpcs3_path = get_rpcs3_path()
    # Assuming rpcs3_path is a pathlib.Path object
    output_file_path = rpcs3_path / "dev_hdd0" / "game" / "BLUS30463" / "USRDIR" / "dx_playlist.dta"

    # Convert the Path object to a string
    output_file_path_str = str(output_file_path)

    # Check if the directory exists
    if not os.path.exists(output_file_path.parent):
        print(f"Error: Directory {output_file_path.parent} does not exist.")
        sys.exit()
    # Check if the file exists
    if not os.path.isfile(output_file_path_str):
        print(f"Error: File {output_file_path_str} does not exist.")
        sys.exit()

    dta_files = list(rpcs3_path.rglob("songs.dta"))

    if not dta_files:
        print("No 'songs.dta' files found in the specified RPCS3 folder.")
        exit()

    all_parsed_dicts = {}

    for dta_file in dta_files:
        parsed_dict = parse_dta(dta_file, rpcs3_path)  # Pass rpcs3_path to parse_dta
        all_parsed_dicts.update(parsed_dict)


    # Export the output JSON to the working directory
    output_json_path = rpcs3_path / "output.json"
    data = read_json(output_json_path)

    with open(output_json_path, 'w') as json_file:
        json.dump(all_parsed_dicts, json_file, indent=2)

    print(f"\nJSON file 'output.json' created in the RPCS3 folder.")

    data = read_json(output_json_path)

    if data:
        song_title_index = "name"
        artist_index = "artist"
        year_index = "year"
        genre_index = "genre"
        short_name_index = "shortname"

        year, artist, song_title, genre, song_title_direct, artist_direct, short_name_direct = refresh_options(data)
        while True:
            print("Welcome to Rock Band 3 Deluxe Play A Show!")
            print("Choose an option:")
            print(f"1. A random song from {year}")
            print(f"2. A random song by {artist}")
            print(f"3. '{song_title_direct}' by '{artist_direct}'")
            print(f"4. A random {genre} song")
            print("5. Refresh options")
            # print("6. Random song by search")
            print("7. Clear the playlist")
            print("0. Exit")

            choice = input("Enter the number of your choice: ")

            if choice == '1':
                fuzzy_search(data, output_file_path, f'year:{year}', rpcs3_path)
                year, artist, song_title, genre, song_title_direct, artist_direct, short_name_direct = refresh_options(data)
            elif choice == '2':
                fuzzy_search(data, output_file_path, f'artist:{artist}', rpcs3_path)
                year, artist, song_title, genre, song_title_direct, artist_direct, short_name_direct = refresh_options(data)
            elif choice == '3':
                append_short_name_to_output(output_file_path, short_name_direct, rpcs3_path)
                year, artist, song_title, genre, song_title_direct, artist_direct, short_name_direct = refresh_options(data)
            elif choice == '4':
                fuzzy_search(data, output_file_path, f'genre:{genre}', rpcs3_path)
                year, artist, song_title, genre, song_title_direct, artist_direct, short_name_direct = refresh_options(data)
            elif choice == '5':
                print("Options refreshed.")
                year, artist, song_title, genre, song_title_direct, artist_direct, short_name_direct = refresh_options(data)
            elif choice == '6':
                search_string = input("Enter a Song Title or Artist to search for: ")
                fuzzy_search(data, output_file_path, f'title:{search_string}', rpcs3_path)
                print(" ")
            elif choice == '7':
                clear_playlist(output_file_path)
                year, artist, song_title, genre, song_title_direct, artist_direct, short_name_direct = refresh_options(data)
            elif choice == '0':
                print("Exiting Play A Show. Goodbye!")
                break
            else:
                print("Invalid choice.")

# Call the new function to run both parts
parse_and_export_to_json()