import os
import json
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import google.generativeai as genai
import spotipy
from spotipy.oauth2 import SpotifyOAuth

app = Flask(__name__)
app.secret_key = "finbeat_super_secret_key"
app.config['SESSION_COOKIE_NAME'] = 'FinBeat Cookie'

# 1. AI Configuration (Gemini API)
# Make sure to set your environment variable: export GEMINI_API_KEY="your-key"
genai.configure(api_key=os.environ.get("GEMINI_API_KEY", "YOUR_GEMINI_KEY_HERE"))
model = genai.GenerativeModel('gemini-1.5-flash')

# 2. Spotify API Configuration
# Get these credentials from developers.spotify.com
SPOTIFY_CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID", "YOUR_SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET", "YOUR_SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = "http://localhost:5000/spotify-callback"

# Global temporary in-memory database for demo simplicity
expenses = [
    {"category": "Food", "amount": 450, "description": "Dinner at restaurant"},
    {"category": "Utilities", "amount": 1200, "description": "Electricity bill"},
    {"category": "Entertainment", "amount": 699, "description": "Movie tickets"}
]

def get_spotify_oauth():
    return SpotifyOAuth(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET,
        redirect_uri=SPOTIFY_REDIRECT_URI,
        scope="user-library-read playlist-modify-public playlist-read-private"
    )

@app.route('/')
def index():
    # Calculate totals
    total_spent = sum(item['amount'] for item in expenses)
    
    # Check if Spotify is connected
    spotify_connected = False
    token_info = session.get('token_info', None)
    if token_info:
        spotify_connected = True

    return render_template('index.html', expenses=expenses, total_spent=total_spent, spotify_connected=spotify_connected)

@app.route('/add-expense', methods=['POST'])
def add_expense():
    data = request.json
    category = data.get('category')
    amount = float(data.get('amount', 0))
    description = data.get('description', '')
    
    if category and amount:
        expenses.append({
            "category": category,
            "amount": amount,
            "description": description
        })
        return jsonify({"status": "success", "message": "Expense added successfully!"})
    return jsonify({"status": "error", "message": "Invalid data submitted."}), 400

@app.route('/ai-analyze', methods=['GET'])
def ai_analyze():
    if not expenses:
        return jsonify({"analysis": "No expenses logged yet. Add some data to let the AI process it!"})
    
    # Construct a structured prompt for the AI
    expense_summary = json.dumps(expenses, indent=2)
    prompt = f"""
    You are a professional financial advisor mixed with a music psychologist. 
    Analyze the following recent personal expenses data:
    {expense_summary}
    
    Provide a concise, 2-sentence financial critique or encouraging remark about their spending habits. 
    Then, suggest a specific 'Vibe/Genre' of music they should listen to right now based on their financial health (e.g., if they spent too much, suggest 'Calm Ambient Jazz to reduce stress'; if they are budgeting well, suggest 'Upbeat Electronic Pop to celebrate').
    
    Format the output strictly as a JSON object with two keys: "critique" and "music_genre". Do not wrap it in markdown codeblocks.
    """
    
    try:
        response = model.generate_content(prompt)
        ai_data = json.loads(response.text.strip())
        session['last_suggested_genre'] = ai_data.get('music_genre', 'lofi')
        return jsonify(ai_data)
    except Exception as e:
        return jsonify({"critique": "AI analysis currently unavailable, but keep tracking!", "music_genre": "Lo-Fi Beats"})

@app.route('/spotify-login')
def spotify_login():
    sp_oauth = get_spotify_oauth()
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)

@app.route('/spotify-callback')
def spotify_callback():
    sp_oauth = get_spotify_oauth()
    session.clear()
    code = request.args.get('code')
    token_info = sp_oauth.get_access_token(code)
    session['token_info'] = token_info
    return redirect(url_for('index'))

@app.route('/get-playlist', methods=['GET'])
def get_playlist():
    token_info = session.get('token_info', None)
    if not token_info:
        return jsonify({"error": "Spotify not authenticated"}), 401
    
    sp = spotipy.Spotify(auth=token_info['access_token'])
    genre_query = session.get('last_suggested_genre', 'chill out hits')
    
    try:
        # Search Spotify for a playlist matching the AI's structural recommendation
        results = sp.search(q=genre_query, type='playlist', limit=3)
        playlists = results['playlists']['items']
        
        output_playlists = []
        for p in playlists:
            output_playlists.append({
                "name": p['name'],
                "url": p['external_urls']['spotify'],
                "image": p['images'][0]['url'] if p['images'] else ''
            })
            
        return jsonify({"playlists": output_playlists, "query": genre_query})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)