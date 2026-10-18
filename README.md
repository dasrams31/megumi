# Megumi

Megumi Kato - Live2D-style AI companion web app.

- Flask UI (mobile-first): full-screen anime character, chat bubbles, mic
  (Web Speech API), TTS (speechSynthesis), ID/JP language toggle.
- Chat backend: 9Router model `spark/muse` (Muse Spark via local muse-bridge).
  The 9Router API key is read at runtime from
  `~/workspace/9router-setup/user-api-key` (never committed).
- Character art: `static/megumi.jpg` (AI-generated).

Run: `./venv/bin/python app.py` (127.0.0.1:18101).
Deploy: `megumi-web.service` + `megumi-tunnel.service` (SSH -R 127.0.0.1:18087),
Caddy vhost `megumi.ramadanadipa.com` -> 127.0.0.1:18087 on the VPS server.
