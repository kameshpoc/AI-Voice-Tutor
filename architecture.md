# Technical Architecture: Voice Tutor Agent

## 1. Overview

The Voice Tutor Agent is a real-time, multimodal AI application designed to provide interactive voice-based tutoring. It leverages a sophisticated pipeline of Speech-to-Text (STT), Large Language Model (LLM) reasoning, and Text-to-Speech (TTS) services to create a natural, conversational educational experience. The system is particularly tailored for the Indian context, supporting multiple Indian languages and English with natural accents.

## 2. System Architecture

The system follows a client-server architecture with a persistent WebRTC connection for low-latency audio streaming.

```mermaid
graph TD
    subgraph Client [Frontend (Browser)]
        UI[User Interface]
        Mic[Microphone Input]
        Speaker[Audio Output]
        W_PC[WebRTC PeerConnection]
        W_DC[Data Channel]
    end

    subgraph Server [Backend (Python/FastAPI)]
        API[FastAPI Server]
        Bot[Tutor Bot Process]
        
        subgraph Pipeline [Pipecat Pipeline]
            Transport[SmallWebRTCTransport]
            VAD[Silero VAD]
            STT[Sarvam STT (Saaras)]
            UserAgg[User Context Aggregator]
            Status[TutorStatusProcessor]
            LLM[Google Gemini 2.5 Pro]
            TTS[Sarvam TTS (Bulbul)]
            AsstAgg[Assistant Context Aggregator]
        end
    end

    %% Audio Flow
    Mic -->|Audio Stream| W_PC
    W_PC -->|RTP| Transport
    Transport -->|Frame| Pipeline
    Pipeline -->|Audio Frame| Transport
    Transport -->|RTP| W_PC
    W_PC -->|Audio Stream| Speaker

    %% Signaling
    UI -->|HTTP Post /api/offer| API
    API -->|Spawn| Bot
    Bot -->|SDP Answer| UI

    %% Data Flow
    Status -.->|Status Events| W_DC
    W_DC -.->|Update UI| UI
```

## 3. Component Details

### 3.1 Frontend (Client)
- **Technology**: Plain HTML/CSS/JavaScript (Vanilla).
- **Responsibility**:
    - Captures user microphone input.
    - Plays back agent audio response.
    - Manages WebRTC connection (SDP Offer/Answer).
    - Visualizes audio activity.
    - Displays real-time conversation transcripts.
    - Handles connection state (Connecting, Connected, Disconnected).
- **Communication**:
    - **Audio**: WebRTC `MediaStreamTrack`.
    - **Data**: WebRTC Data Channel (`pipecat-data`) for status updates (`listening`, `processing`, `speaking`) and transcriptions.

### 3.2 Backend (Server)
- **Technology**: Python 3.9+, FastAPI, Pipecat.
- **Entry Point**: `server.py` hosts the FastAPI application.
    - Serves static assets for the frontend.
    - Exposes `/api/offer` endpoint for WebRTC signaling.
    - Spawns a background `run_bot` task for each new client connection.

### 3.3 AI Pipeline (Pipecat)
The core logic resides in `tutor_agent.py`, utilizing the `pipecat` framework to manage a stream of "frames" (audio, text, messages).

#### Pipeline Stages:
1.  **Transport Input**: Receives raw audio from WebRTC.
2.  **VAD (Voice Activity Detection)**: Uses `SileroVADAnalyzer` to detect when the user starts/stops speaking.
3.  **STT (Speech-to-Text)**:
    -   **Service**: Sarvam AI (`Saaras v2.5`).
    -   **Function**: Transcribes user audio to text. Supports auto-detection of Indian languages.
4.  **User Context Aggregator**: Collects transcribed text and appends it to the conversation context.
5.  **Status Processor (`TutorStatusProcessor`)**:
    -   Custom processor that monitors pipeline frames.
    -   Detects states:
        -   `LLMMessagesFrame` → "Thinking" (Processing).
        -   `TTSAudioRawFrame` → "Speaking".
        -   `LLMFullResponseEndFrame` → "Listening".
    -   Sends these states to the frontend via the WebRTC data channel.
6.  **LLM (Large Language Model)**:
    -   **Service**: Google Gemini 2.5 Pro.
    -   **Function**: Generates educational responses based on the transcript and system prompt.
    -   **Configuration**: High reasoning budget, temperature 0.7 for creative yet accurate teaching.
7.  **TTS (Text-to-Speech)**:
    -   **Service**: Sarvam AI (`Bulbul v3`).
    -   **Function**: Converts LLM text response into natural-sounding speech.
    -   **Voice**: "Ishita" (Indian English/Hindi).
8.  **Transport Output**: Sends generated audio back to the client via WebRTC.
9.  **Assistant Context Aggregator**: Appends the assistant's response to the conversation history.

## 4. Key Technologies & Services

| Component | Technology | Description |
| :--- | :--- | :--- |
| **Framework** | **Pipecat** | Open-source framework for building voice agents. Handles the pipeline, frame processing, and transport abstraction. |
| **Server** | **FastAPI** | High-performance async web server for hosting the UI and signaling API. |
| **Transport** | **SmallWebRTC** | Lightweight WebRTC transport for peer-to-peer audio and data streaming. |
| **STT** | **Sarvam AI (Saaras)** | Specialized speech recognition model for Indian languages. |
| **LLM** | **Google Gemini 2.5 Pro** | Multimodal reasoning model capable of complex problem solving and instruction. |
| **TTS** | **Sarvam AI (Bulbul)** | High-quality text-to-speech engine with Indian accents. |

## 5. Data Flow

1.  **Initialization**: User clicks "Connect". Browser sends SDP offer to `/api/offer`. Server initializes pipeline and returns SDP answer. Connection established.
2.  **User Speaks**: Audio flows from Browser → WebRTC → Transport → VAD → STT.
3.  **Transcription**: STT converts audio to text. `UserAggregator` adds it to context.
4.  **Reasoning**: `TutorStatusProcessor` detects LLM activation and sends "Processing" status to UI. Context is sent to Gemini LLM.
5.  **Response Generation**: Gemini streams text response.
6.  **Synthesis**: Text flows to TTS. `TutorStatusProcessor` detects audio frames and sends "Speaking" status to UI.
7.  **Playback**: TTS audio flows to Transport → WebRTC → Browser Speaker.
8.  **Completion**: Response finishes. `TutorStatusProcessor` detects end of response and sends "Listening" status.

## 6. Security & Deployment

-   **Environment Variables**: API keys (`SARVAM_API_KEY`, `GOOGLE_API_KEY`) are managed via `.env`.
-   **SSL/Certificates**: Local development handles SSL verification patches for macOS/simpler setups. Production deployment would require a proper HTTPS setup for WebRTC/Microphone permissions in modern browsers.
