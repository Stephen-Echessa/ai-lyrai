import json
import os
import re
import requests
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from lyricsgenius import Genius
from difflib import SequenceMatcher

load_dotenv()

client_id = os.getenv("SPOTIFY_CLIENT_ID")
client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
genius_token = os.getenv("GENIUS_API_KEY")

spotify_auth = SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
sp = spotipy.Spotify(auth_manager=spotify_auth)
genius = Genius(genius_token)
genius.skip_non_songs = True
genius.excluded_terms = ["(Remix)", "(Live)", "(Acoustic)"]


def _parse_spotify_track_id(song_url: str) -> str:
    if song_url.startswith("spotify:track:"):
        result = song_url.split(":")[-1]
        return result

    track_match = re.search(r"track[/:]([A-Za-z0-9]+)", song_url)
    if track_match:
        result = track_match.group(1)
        return result

    query_match = re.search(r"[?&]id=([A-Za-z0-9]+)", song_url)
    if query_match:
        result = query_match.group(1)
        return result

    return song_url


def _spotify_track_to_dict(track: dict) -> dict:
    album = track.get("album", {})
    artists = [artist.get("name", "") for artist in track.get("artists", [])]
    artist_ids = [artist.get("id") for artist in track.get("artists", []) if artist.get("id")]
    result = {
        "id": track.get("id"),
        "name": track.get("name"),
        "artists": artists,
        "artist_ids": artist_ids,
        "album_name": album.get("name"),
        "album_id": album.get("id"),
        "album_type": album.get("album_type"),
        "release_date": album.get("release_date"),
        "release_date_precision": album.get("release_date_precision"),
        "duration_ms": track.get("duration_ms"),
        "explicit": track.get("explicit"),
        "popularity": track.get("popularity"),
        "preview_url": track.get("preview_url"),
        "spotify_url": track.get("external_urls", {}).get("spotify"),
        "album_cover_url": (album.get("images") or [{}])[0].get("url"),
        "album_total_tracks": album.get("total_tracks"),
    }
    return result


def spotify_track_metadata(song_url: str) -> dict:
    """Return structured Spotify metadata for a song URL or Spotify track ID."""
    track_id = _parse_spotify_track_id(song_url)
    try:
        track = sp.track(track_id)
    except Exception as exc:
        err = {"error": "Unable to fetch Spotify track metadata", "detail": str(exc), "song_url": song_url}
        print("[tools debug] spotify_track_metadata ->", err, "\n")
        return err

    result = _spotify_track_to_dict(track)
    return result


def _normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r'\(.*?\)|\[.*?\]', '', text)  # remove (Remastered), [Live], etc.
    text = re.sub(r'\bfeat\.?\b|\bft\.?\b', '', text)  # normalize features
    text = re.sub(r'[^\w\s]', '', text)  # strip punctuation
    return text.strip()


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, _normalize(a), _normalize(b)).ratio()


def _search_genius_for_spotify_track(song_name: str, artist_name: str):
    title_threshold = 0.75
    artist_threshold = 0.75

    try:
        song = genius.search_song(title=song_name, artist=artist_name)
        if song is None:
            return None
        
        title_score = _similarity(song.title, song_name)
        artist_score = _similarity(song.artist, artist_name)

        if title_score < title_threshold or artist_score < artist_threshold:
            print(
                f"[tools debug] Match rejected — "
                f"title: '{song.title}' vs '{song_name}' ({title_score:.2f}), "
                f"artist: '{song.artist}' vs '{artist_name}' ({artist_score:.2f})"
            )
            return None

        return song
        
    except Exception:
        print("[tools debug] _search_genius_for_spotify_track -> exception during genius search for", song_name, artist_name, "\n")
        return None


def genius_artist_profile(song: dict) -> dict:
    """Return artist profile data from Genius for the given artist name."""
    try:
        genius_artist = genius.artist(artist_id=song.primary_artist['id'])
    except Exception as exc:
        err = {"error": "Unable to fetch Genius artist profile", "detail": str(exc), "artist_name": genius_artist["artist"]["name"] if genius_artist else None}
        print("[tools debug] genius_artist_profile ->", err, "\n")
        return err

    if not genius_artist:
        err = {"error": "Artist not found on Genius", "artist_name": genius_artist}
        print("[tools debug] genius_artist_profile ->", err, "\n")
        return err

    # Extract description safely
    genius_description = None
    raw_description = genius_artist["artist"]["description"]
    if isinstance(raw_description, dict):
        genius_description = raw_description.get("plain") or raw_description.get("html")
    elif isinstance(raw_description, str) and raw_description.strip().lower() != "?":
        genius_description = raw_description.strip()

    result = {
        "name": genius_artist["artist"]["name"],
        "description": genius_description,
    }

    return result


def genius_song_lyrics(song: dict) -> dict:
    """Return Genius lyrics and basic metadata for a Spotify song URL."""
    result = {
        "title": getattr(song, "title", None),
        "artist": getattr(song, "artist", None),
        "url": getattr(song, "url", None),
        "lyrics": getattr(song, "lyrics", None),
    }
    # print("[tools debug] genius_song_lyrics ->", {"title": result.get("title"), "artist": result.get("artist")}, "\n")
    return result


def genius_song_description(song: dict) -> dict:
    """Return Genius song description, contributors, and page metadata for a Spotify song URL."""
    song_info = getattr(song, "to_dict", lambda: lambda: {})()
    result = {
        "description": song_info.get("description"),
        "writer_artists": [item.get("name") for item in song_info.get("writer_artists", []) if item.get("name")],
        "producer_artists": [item.get("name") for item in song_info.get("producer_artists", []) if item.get("name")],
    }
    # print("[tools debug] genius_song_description ->", {"title": result.get("title"), "writers": len(result.get("writer_artists"))}, "\n")
    return result