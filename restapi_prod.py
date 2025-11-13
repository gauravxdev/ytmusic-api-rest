import os
import logging
from flask import Flask, jsonify, request
from ytmusicapi import YTMusic
import time

app = Flask(__name__)

# Configure logging for production
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Public instance: default region/location; you may optionally create new instance per-request with region/lang
yt_public = YTMusic(language='en', location='IN')

# Simple in-memory cache (for single-instance deployment; consider Redis for multi-instance)
_CACHE = {}
_CACHE_TTL = int(os.getenv('CACHE_TTL', 10 * 60))  # 10 minutes, configurable via env

def _cache_get(key):
    entry = _CACHE.get(key)
    if not entry:
        return None
    ts, value = entry
    if time.time() - ts > _CACHE_TTL:
        del _CACHE[key]
        return None
    return value

def _cache_set(key, value):
    _CACHE[key] = (time.time(), value)

def _normalize_item(item, t):
    base_thumbnails = item.get("thumbnails", [])

    # For songs, add larger YouTube thumbnail sizes
    if t == "song" and item.get("videoId"):
        video_id = item.get("videoId")
        youtube_thumbnails = [
            {
                "height": 90,
                "url": f"https://img.youtube.com/vi/{video_id}/default.jpg",
                "width": 120
            },
            {
                "height": 180,
                "url": f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg",
                "width": 320
            },
            {
                "height": 360,
                "url": f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
                "width": 480
            },
            {
                "height": 480,
                "url": f"https://img.youtube.com/vi/{video_id}/sddefault.jpg",
                "width": 640
            },
            {
                "height": 720,
                "url": f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
                "width": 1280
            }
        ]
        # Combine original thumbnails with YouTube ones
        base_thumbnails = youtube_thumbnails

    return {
        "type": t,
        "id": item.get("videoId") or item.get("playlistId") or item.get("browseId") or item.get("id"),
        "title": item.get("title") or item.get("name"),
        "thumbnails": base_thumbnails,
        **({"artists": item.get("artists")} if t == "song" else {}),
        **({"year": item.get("year")} if t == "album" else {}),
        **({"subscribers": item.get("subscribers")} if t == "artist" else {}),
    }

def _dedupe(lst):
    seen = set()
    out = []
    for x in lst:
        key = (x["type"], x["id"])
        if key in seen:
            continue
        seen.add(key)
        out.append(x)
    return out

@app.route('/api/homefeed', methods=['GET'])
def api_homefeed():
    region = request.args.get('region', 'IN')
    lang = request.args.get('lang', 'en')
    limit = int(request.args.get('limit', 10))
    key = f"homefeed:{region}:{lang}:{limit}"
    cached = _cache_get(key)
    if cached:
        return jsonify({"status":"success","data":cached})
    yt = YTMusic(language=lang, location=region)
    sections = yt.get_home(limit=limit)
    feed = []
    for sec in sections:
        items = sec.get("contents", [])
        mapped = []
        for it in items:
            if "videoId" in it:
                t = "song"
            elif "playlistId" in it:
                t = "playlist"
            elif "browseId" in it:
                t = "album"  # or artist – heuristic
            else:
                t = "unknown"
            mapped.append(_normalize_item(it, t))
        feed.append({"sectionTitle": sec.get("title"), "items": _dedupe(mapped)})
    _cache_set(key, feed)
    return jsonify({"status":"success","data":{"feed":feed}})

@app.route('/api/search/suggestions', methods=['GET'])
def api_search_suggestions():
    q = request.args.get('query')
    if not q:
        return jsonify({"status":"error","message":"missing query param"}), 400
    region = request.args.get('region', 'IN')
    lang = request.args.get('lang', 'en')
    yt = YTMusic(language=lang, location=region)
    try:
        suggestions = yt.get_search_suggestions(q)
    except Exception as e:
        logger.error(f"get_search_suggestions failed: {str(e)}")
        return jsonify({"status":"error","message": f"get_search_suggestions failed: {str(e)}"}), 500
    return jsonify({"status":"success","data": {"suggestions": suggestions}})

@app.route('/api/song/related/<video_id>', methods=['GET'])
def api_song_related(video_id):
    region = request.args.get('region', 'IN')
    lang = request.args.get('lang', 'en')
    limit = int(request.args.get('limit', 10))
    yt = YTMusic(language=lang, location=region)
    try:
        raw = yt.get_song_related(video_id)
    except Exception as e:
        logger.error(f"get_song_related failed: {str(e)}")
        return jsonify({"status":"error","message":f"get_song_related failed: {str(e)}"}), 500

    items = []
    # raw may be list of sections
    for section in raw:
        contents = section.get("contents", [])
        for it in contents:
            if "videoId" in it:
                items.append({
                    "type": "song",
                    "id": it.get("videoId"),
                    "title": it.get("title"),
                    "artists": it.get("artists"),
                    "thumbnails": it.get("thumbnails")
                })
    items = items[:limit]
    return jsonify({"status":"success","data": {"related": items}})

@app.route('/api/user/<user_id>', methods=['GET'])
def api_user_detail(user_id):
    region = request.args.get('region', 'IN')
    lang = request.args.get('lang', 'en')
    yt = YTMusic(language=lang, location=region)
    try:
        raw = yt.get_user(user_id)
    except Exception as e:
        logger.error(f"get_user failed: {str(e)}")
        return jsonify({"status":"error","message":f"get_user failed: {str(e)}"}), 500
    # return raw dict so you can inspect structure
    return jsonify({"status":"success","data": raw})

@app.route('/api/user/<user_id>/playlists', methods=['GET'])
def api_user_playlists(user_id):
    region = request.args.get('region', 'IN')
    lang = request.args.get('lang', 'en')
    yt = YTMusic(language=lang, location=region)
    # optionally accept params token for pagination
    params = request.args.get('params')
    try:
        if params:
            playlists_raw = yt.get_user_playlists(user_id, params=params)
        else:
            playlists_raw = yt.get_user_playlists(user_id)
    except Exception as e:
        logger.error(f"get_user_playlists failed: {str(e)}")
        return jsonify({"status":"error","message":f"get_user_playlists failed: {str(e)}"}), 500

    normalized = []
    for p in playlists_raw:
        normalized.append({
            "title": p.get("title"),
            "playlistId": p.get("playlistId"),
            "thumbnails": p.get("thumbnails"),
            "count": p.get("count")
        })
    return jsonify({"status":"success","data": {"playlists": normalized}})

@app.route('/api/search', methods=['GET'])
def api_search():
    q = request.args.get('query')
    if not q:
        return jsonify({"status":"error","message":"missing query param"}), 400
    filter_ = request.args.get('filter', 'all')
    region = request.args.get('region', 'IN')
    lang = request.args.get('lang', 'en')
    yt = YTMusic(language=lang, location=region)
    raw = yt.search(q, filter=filter_)
    results = []
    for r in raw:
        rt = r.get("resultType")
        if rt == "song":
            t = "song"
        elif rt == "album":
            t = "album"
        elif rt == "artist":
            t = "artist"
        elif rt == "playlist":
            t = "playlist"
        else:
            t = "song"
        results.append(_normalize_item(r, t))
    return jsonify({"status":"success","data":{"results":_dedupe(results)}})

@app.route('/api/charts', methods=['GET'])
def api_charts():
    country = request.args.get('region', 'IN')  # rename param to country ISO code
    key = f"charts:{country}"
    cached = _cache_get(key)
    if cached:
        return jsonify({"status":"success","data":cached})

    try:
        raw = yt_public.get_charts(country=country)
    except Exception as e:
        logger.error(f"failed get_charts: {str(e)}")
        return jsonify({"status":"error","message":f"failed get_charts: {str(e)}"}), 500

    # parse videos as songs
    videos_raw = raw.get("videos", [])
    artists_raw = raw.get("artists", [])
    genres_raw = raw.get("genres", [])  # optional
    playlists_from_genres = []
    if genres_raw:
        for g in genres_raw:
            # each genre item may have playlistId
            playlists_from_genres.append({
                "type": "playlist",
                "id": g.get("playlistId"),
                "title": g.get("title"),
                "thumbnails": g.get("thumbnails")
            })

    songs = [_normalize_item(v, "song") for v in videos_raw]
    artists = [_normalize_item(a, "artist") for a in artists_raw]

    data = {
        "songs": _dedupe(songs),
        "artists": _dedupe(artists),
        "genrePlaylists": _dedupe(playlists_from_genres)
    }

    _cache_set(key, data)
    return jsonify({"status":"success","data":data})

@app.route('/api/artist/<artist_id>', methods=['GET'])
def api_artist_detail(artist_id):
    region = request.args.get('region', 'IN')
    lang = request.args.get('lang', 'en')
    yt = YTMusic(language=lang, location=region)
    raw = yt.get_artist(artist_id)
    songs = raw.get("songs", {}).get("results", []) if isinstance(raw.get("songs"), dict) else raw.get("songs", [])
    albums = raw.get("albums", {}).get("results", []) if isinstance(raw.get("albums"), dict) else raw.get("albums", [])
    result = {
        "artist": _normalize_item(raw, "artist"),
        "songs": [_normalize_item(it, "song") for it in songs],
        "albums": [_normalize_item(it, "album") for it in albums]
    }
    return jsonify({"status":"success","data":result})

@app.route('/api/album/<album_id>', methods=['GET'])
def api_album_detail(album_id):
    region = request.args.get('region', 'IN')
    lang = request.args.get('lang', 'en')
    yt = YTMusic(language=lang, location=region)
    raw = yt.get_album(album_id)
    tracks = raw.get("tracks", [])
    result = {
        "album": _normalize_item(raw, "album"),
        "tracks": [_normalize_item(it, "song") for it in tracks]
    }
    return jsonify({"status":"success","data":result})

@app.route('/api/playlist/<playlist_id>', methods=['GET'])
def api_playlist_detail(playlist_id):
    region = request.args.get('region', 'IN')
    lang = request.args.get('lang', 'en')
    yt = YTMusic(language=lang, location=region)
    raw = yt.get_playlist(playlist_id, limit=50)
    tracks = raw.get("tracks", [])
    result = {
        "playlist": _normalize_item(raw, "playlist"),
        "tracks": [_normalize_item(it, "song") for it in tracks]
    }
    return jsonify({"status":"success","data":result})

# For production deployment with WSGI server like gunicorn
# Run with: gunicorn --bind 0.0.0.0:8000 restapi_prod:app
# Or use the app object directly if needed

if __name__ == '__main__':
    # For local testing only; in production, use WSGI server
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', 5000))
    app.run(host=host, port=port, debug=False)