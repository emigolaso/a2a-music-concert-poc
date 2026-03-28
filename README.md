# A2A Music + Concert POC

Thin POC composed of:

- a custom Spotify MCP server
- a Spotify music agent using the OpenAI Agents SDK pattern with watsonx-hosted inference
- a LangGraph-powered concert agent
- two A2A-compatible HTTP apps for watsonx Orchestrate import

## Quick start

1. Activate a Python environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -e .
```

3. Copy `.env.example` to `.env` and fill in credentials.

Required variables:

- `SPOTIFY_CLIENT_ID`
- `SPOTIFY_CLIENT_SECRET`
- `SPOTIFY_REFRESH_TOKEN`
- `WATSONX_PROJECT_ID`
- `WATSONX_APIKEY`
- `WATSONX_URL`

4. Start the Spotify A2A app:

```bash
uvicorn a2a_music_concert.deployment_app:app --host 0.0.0.0 --port 8000
```

5. Start the concert A2A app:

```bash
uvicorn a2a_music_concert.concert_deployment_app:app --host 0.0.0.0 --port 8001
```

6. Validate the endpoints:

```bash
curl http://127.0.0.1:8000/healthz
curl http://127.0.0.1:8000/.well-known/agent-card.json
curl http://127.0.0.1:8001/healthz
curl http://127.0.0.1:8001/.well-known/agent-card.json
```

## Spotify refresh token helper

After you set `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET` in `.env`, run:

```bash
python scripts/get_spotify_refresh_token.py
```

This will:

- create `.env` from `.env.example` if needed
- open the Spotify authorization page in your browser
- listen on `http://127.0.0.1:8787/callback`
- exchange the auth code for a refresh token
- write `SPOTIFY_REFRESH_TOKEN` back into `.env`

## Expected flow

- Ask the music agent for your top artist recently.
- Use the returned artist in a second request to the concert agent.
- Import both agents into watsonx Orchestrate as external A2A agents.
