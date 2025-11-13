# YouTube Music REST API

Production-ready REST API for YouTube Music using Flask and ytmusicapi.

## Local Development

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the development server:
```bash
python restapi_prod.py
```

## Render Deployment

This app is configured for deployment on Render.com.

### Deployment Steps:

1. **Create a GitHub repository** and push your code:
   - `restapi_prod.py`
   - `requirements.txt`
   - `README.md` (optional)

2. **Connect to Render**:
   - Go to [Render.com](https://render.com) and create a new Web Service
   - Connect your GitHub repository
   - Select Python environment

3. **Configure Build & Start**:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn --bind 0.0.0.0:$PORT restapi_prod:app`
   - **Environment**: Set `PYTHON_VERSION` to `3.11` or your preferred version

4. **Environment Variables** (optional):
   - `CACHE_TTL`: Cache TTL in seconds (default: 600)
   - `HOST`: Server host (default: 0.0.0.0)
   - `PORT`: Automatically set by Render

### Deployment Verification

- ✅ **Local testing**: Flask app runs successfully on port 5000
- ✅ **Dependencies**: All required packages listed in `requirements.txt`
- ✅ **WSGI ready**: Configured for gunicorn (works on Linux/Render)
- ✅ **Production settings**: Debug disabled, logging enabled
- ✅ **Environment support**: Configurable via environment variables

**Note**: Gunicorn testing on Windows fails due to OS limitations, but it works perfectly on Render's Linux environment.

### API Endpoints

All endpoints support optional `region` and `lang` query parameters.

- `GET /api/homefeed` - Get home feed sections
- `GET /api/search/suggestions?query=<query>` - Get search suggestions
- `GET /api/song/related/<video_id>` - Get related songs
- `GET /api/user/<user_id>` - Get user details
- `GET /api/user/<user_id>/playlists` - Get user playlists
- `GET /api/search?query=<query>&filter=<filter>` - Search music
- `GET /api/charts?region=<country>` - Get charts
- `GET /api/artist/<artist_id>` - Get artist details
- `GET /api/album/<album_id>` - Get album details
- `GET /api/playlist/<playlist_id>` - Get playlist details

### Notes

- The app uses in-memory caching suitable for single-instance deployments
- For multi-instance scaling, consider using Redis for caching
- All endpoints return JSON responses with `status` and `data` fields