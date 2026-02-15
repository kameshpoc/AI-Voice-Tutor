# 🎓 Voice Tutor Agent

A real-time **voice-based AI tutor** built with [Pipecat](https://docs.pipecat.ai/), [Sarvam AI](https://docs.sarvam.ai/) (Indian-language STT/TTS), and **Google Gemini 2.5 Pro** (reasoning LLM).

Based on the [Sarvam AI Tutor Agent cookbook](https://docs.sarvam.ai/api-reference-docs/cookbook/example-voice-agents/tutor-agent).

## Pipeline

```
Student Audio → Sarvam STT (Saaras v3) → Gemini 2.5 Pro → Sarvam TTS (Bulbul v3) → Audio Output
```

## Features

- 🗣️ **Multilingual speech recognition** — auto-detects Indian languages
- 🧠 **Gemini 2.5 Pro reasoning** — strong problem-solving for math, science, and more
- 🔊 **Natural Indian-English voice** — Sarvam Bulbul v3 with clear articulation
- 📚 **Multi-subject tutor** — Maths, Science, Languages, Social Studies
- 🎯 **Adaptive teaching** — adjusts explanations to student level
- 🎤 **Browser UI** — beautiful mic mute/unmute interface with live transcript

## Quick Start

### 1. Prerequisites

- Python 3.9+
- API keys from:
  - [Sarvam AI](https://dashboard.sarvam.ai/) — STT & TTS
  - [Google AI Studio](https://aistudio.google.com/) — Gemini LLM

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Set Up Environment

```bash
cp .env.example .env
# Edit .env and add your real API keys
```

### 4. Run the Agent

```bash
python3 server.py
```

This starts the FastAPI server which:
1. Serves the web UI at **http://localhost:7860**
2. Handles WebRTC signaling at `/api/offer`
3. Spawns the tutor bot for each new connection

### 5. Use the Tutor

1. Open **http://localhost:7860** in your browser
2. Click **"Connect to Tutor"**
3. Click the **mic button** to unmute
4. Start speaking — the tutor will respond!

## Project Structure

```
tutor_agent/
├── tutor_agent.py      # Main agent — Pipecat pipeline (Sarvam + Gemini)
├── static/
│   └── index.html      # Browser UI with mic button
├── requirements.txt    # Python dependencies
├── .env.example        # API key template
└── README.md
```

## Customization

### Change Language

Edit `tutor_agent.py`:

```python
# Hindi tutor
stt = SarvamSTTService(..., language="hi-IN")
tts = SarvamTTSService(..., target_language_code="hi-IN", speaker="simran")
```

### Available Languages

`en-IN` `hi-IN` `bn-IN` `ta-IN` `te-IN` `gu-IN` `kn-IN` `ml-IN` `mr-IN` `pa-IN` `od-IN` `unknown` (auto-detect)

### Available Voices

- **Female**: Ritu, Priya, Neha, Pooja, Simran, Kavya, **Ishita** (default), Shreya, Roopa, and more
- **Male**: Shubh, Aditya, Rahul, Rohan, Amit, Dev, and more
