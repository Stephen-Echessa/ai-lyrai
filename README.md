# Lyr.AI Chatbot

The AI backend for Lyr.AI, a music analysis chatbot that interprets lyrical context and provides in-depth song analysis. Built with FastAPI, LangGraph, and Python.

## Prerequisites

- Python 3.11+
- A Genius API key
- A Gemini API key (or any LLM API key)
- A Spotify Client ID and Secret from [developer.spotify.com](https://developer.spotify.com)

## Setup

1. Clone the repository

```bash
git clone https://github.com/Stephen-Echessa/lyrai_ai_code
cd lyrai_ai_code
```

2. Create a virtual environment and install dependencies

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

3. Create a `.env` file in the root directory

```bash
GEMINI_API_KEY=your_anthropic_api_key
GENIUS_API_KEY=your_genius_api_key
SPOTIFY_CLIENT_ID=your_spotify_client_id
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret
```

4. Run the server

```bash
uvicorn app:app --reload --port 8000
```

The server will be running at `http://localhost:8000`.
