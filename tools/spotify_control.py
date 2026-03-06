import spotipy
from spotipy.oauth2 import SpotifyOAuth
import time
import logging
logging.getLogger("spotipy").setLevel(logging.CRITICAL)

SCOPE = "user-read-playback-state user-modify-playback-state user-read-currently-playing playlist-read-private"

def _load_key(name: str) -> str:
    with open("Keys.txt", "r") as f:
        for line in f:
            if line.startswith(name):
                return line.split("=", 1)[1].strip()
    raise ValueError(f"{name} key not found in Keys.txt")

def _get_spotify() -> spotipy.Spotify:
    return spotipy.Spotify(auth_manager=SpotifyOAuth(
        client_id=_load_key("SPOTIFY_CLIENT_ID"),
        client_secret=_load_key("SPOTIFY_CLIENT_SECRET"),
        redirect_uri=_load_key("SPOTIFY_REDIRECT_URI"),
        scope=SCOPE,
        cache_path="memory/.spotify_cache"
    ))

def _get_country() -> str:
    try:
        sp = _get_spotify()
        return sp.current_user().get("country", "IN")
    except:
        return "IN"

def _ensure_active_device(sp) -> bool:
    # Check if any device is active
    devices = sp.devices()["devices"]
    if not devices:
        return False

    # If no active device, transfer to first available
    active = [d for d in devices if d["is_active"]]
    if not active:
        sp.transfer_playback(
            device_id=devices[0]["id"],
            force_play=False
        )
        time.sleep(1)

    return True

def _start_playback(sp, **kwargs) -> bool:
    # Try to start playback, activate device if needed
    try:
        sp.start_playback(**kwargs)
        return True
    except spotipy.exceptions.SpotifyException as e:
        if "NO_ACTIVE_DEVICE" in str(e):
            # Find and activate a device
            devices = sp.devices()["devices"]
            if not devices:
                return False
            sp.transfer_playback(
                device_id=devices[0]["id"],
                force_play=True
            )
            time.sleep(1)
            # Retry playback
            sp.start_playback(**kwargs)
            return True
        raise e

def play_pause() -> str:
    try:
        sp = _get_spotify()
        playback = sp.current_playback()
        if playback and playback["is_playing"]:
            sp.pause_playback()
            return "Paused"
        else:
            _start_playback(sp)
            return "Playing"
    except Exception as e:
        return f"Could not control playback: {e}"

def next_track() -> str:
    try:
        sp = _get_spotify()
        sp.next_track()
        time.sleep(0.5)
        return get_current_track()
    except Exception as e:
        return f"Could not skip: {e}"

def previous_track() -> str:
    try:
        sp = _get_spotify()
        sp.previous_track()
        time.sleep(0.5)
        return get_current_track()
    except Exception as e:
        return f"Could not go back: {e}"

def get_current_track() -> str:
    try:
        sp = _get_spotify()
        current = sp.current_playback()
        if not current or not current.get("item"):
            return "Nothing playing right now"
        track = current["item"]["name"]
        artist = current["item"]["artists"][0]["name"]
        status = "Playing" if current["is_playing"] else "Paused"
        return f"{status}: {track} by {artist}"
    except Exception as e:
        return f"Could not get current track: {e}"

def play_song(query: str) -> str:
    try:
        sp = _get_spotify()
        results = sp.search(q=query, type="track", limit=1)
        tracks = results["tracks"]["items"]
        if not tracks:
            return f"Could not find '{query}'"
        track = tracks[0]
        _start_playback(sp, uris=[track["uri"]])
        return f"Playing {track['name']} by {track['artists'][0]['name']}"
    except Exception as e:
        return f"Could not play song: {e}"

def play_artist(artist_name: str) -> str:
    try:
        sp = _get_spotify()
        results = sp.search(
            q=f"artist:{artist_name}",
            type="track",
            limit=10
        )
        tracks = results["tracks"]["items"]
        if not tracks:
            return f"Could not find tracks for '{artist_name}'"
        uris = [t["uri"] for t in tracks]
        _start_playback(sp, uris=uris)
        return f"Playing {artist_name}"
    except Exception as e:
        return f"Could not play artist: {e}"

def play_playlist(playlist_name: str) -> str:
    try:
        sp = _get_spotify()
        playlists = sp.current_user_playlists()["items"]

        target = None
        for pl in playlists:
            if playlist_name.lower() in pl["name"].lower():
                target = pl
                break

        if not target:
            results = sp.search(q=playlist_name, type="playlist", limit=1)
            items = results["playlists"]["items"]
            if items:
                target = items[0]

        if not target:
            return f"Could not find playlist '{playlist_name}'"

        _start_playback(sp, context_uri=target["uri"])
        return f"Playing playlist: {target['name']}"
    except Exception as e:
        return f"Could not play playlist: {e}"

def set_volume(level: int) -> str:
    try:
        level = max(0, min(100, level))
        sp = _get_spotify()
        sp.volume(level)
        return f"Spotify volume set to {level}%"
    except Exception as e:
        return f"Could not set volume: {e}"

def play_by_mood(mood: str) -> str:
    mood_map = {
        "happy": "happy upbeat hits",
        "sad": "sad emotional songs",
        "focus": "focus study concentration",
        "workout": "workout gym motivation",
        "sleep": "sleep calm relaxing",
        "party": "party hits dance",
        "chill": "chill lofi relaxed",
        "angry": "intense aggressive metal",
        "romantic": "romantic love songs",
    }
    query = mood_map.get(mood.lower(), f"{mood} music")
    return play_playlist(query)

def get_user_playlists() -> str:
    try:
        sp = _get_spotify()
        playlists = sp.current_user_playlists()["items"]
        if not playlists:
            return "No playlists found"
        names = [pl["name"] for pl in playlists[:10]]
        return "Your playlists: " + ", ".join(names)
    except Exception as e:
        return f"Could not get playlists: {e}"