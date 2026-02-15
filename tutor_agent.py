"""
Tutor Agent — Voice-based AI tutor using Pipecat + Sarvam AI + Google Gemini

Pipeline:
  Student Audio → Sarvam STT (Saaras v3) → Gemini 2.5 Pro → Sarvam TTS (Bulbul v3) → Audio Output

Based on: https://docs.sarvam.ai/api-reference-docs/cookbook/example-voice-agents/tutor-agent
Modified to use Google Gemini 2.5 Pro (reasoning model) instead of OpenAI.
Uses SmallWebRTCTransport for peer-to-peer browser connection (no Daily key needed).
"""

import os
import sys

from dotenv import load_dotenv
from loguru import logger

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.frames.frames import LLMRunFrame
from pipecat.processors.logger import FrameLogger
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.runner.types import RunnerArguments
from pipecat.services.sarvam.stt import SarvamSTTService
from pipecat.services.sarvam.tts import SarvamTTSService
from pipecat.transcriptions.language import Language
from pipecat.services.google.llm import GoogleLLMService
from pipecat.transports.base_transport import BaseTransport, TransportParams
from pipecat.transports.smallwebrtc.connection import SmallWebRTCConnection
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport

# Frames
from pipecat.frames.frames import (
    Frame,
    LLMMessagesFrame,
    LLMFullResponseEndFrame,
    TTSAudioRawFrame,
    OutputTransportMessageFrame,
    StartFrame,
    EndFrame,
    CancelFrame,
    InterruptionFrame
)
from pipecat.processors.frame_processor import FrameProcessor

# System Prompts
from prompts import SYSTEM_PROMPT

class TutorStatusProcessor(FrameProcessor):
    """
    Watches the pipeline for specific frames to infer state.
    """
    def __init__(self):
        super().__init__()
        self._is_speaking = False

    async def process_frame(self, frame: Frame, direction):
        # Log all frames to see what's passing through
        logger.debug(f"TutorStatusProcessor processing: {frame}")
        
        # Standard system frame handling (start/stop interruptions etc.)
        await super().process_frame(frame, direction)

        # 1. Detect "Processing" (Thinking)
        if isinstance(frame, LLMMessagesFrame):
            logger.debug("TutorStatusProcessor: Emitting 'processing' status")
            await self.push_frame(OutputTransportMessageFrame(message={"type": "status", "status": "processing"}))

        # 2. Detect "Speaking"
        if isinstance(frame, TTSAudioRawFrame):
            if not self._is_speaking:
                self._is_speaking = True
                logger.debug("TutorStatusProcessor: Emitting 'speaking' status")
                await self.push_frame(OutputTransportMessageFrame(message={"type": "status", "status": "speaking"}))
        
        # 3. Detect "Listening" (End of Turn)
        if isinstance(frame, LLMFullResponseEndFrame):
             self._is_speaking = False
             logger.debug("TutorStatusProcessor: Emitting 'listening' status")
             await self.push_frame(OutputTransportMessageFrame(message={"type": "status", "status": "listening"}))

        # Push the original frame
        await self.push_frame(frame, direction)

load_dotenv(override=True)

try:
    logger.remove(0)
except ValueError:
    pass
logger.add(sys.stderr, level="DEBUG")




async def run_bot(transport: BaseTransport, handle_sigint: bool = True):
    """Run the tutor bot pipeline with the provided transport."""

    # SSL Fix for macOS (Robust method using certifi)
    import ssl
    import certifi
    os.environ['SSL_CERT_FILE'] = certifi.where()
    
    # Fallback monkeypatch just in case
    try:
        _create_unverified_https_context = ssl._create_unverified_context
    except AttributeError:
        pass
    else:
        ssl._create_default_https_context = _create_unverified_https_context

    # NLTK Fix: Download required tokenizers
    import nltk
    try:
        nltk.data.find('tokenizers/punkt_tab')
    except LookupError:
        nltk.download('punkt_tab')
    try:
        nltk.data.find('tokenizers/punkt')
    except LookupError:
        nltk.download('punkt')

    # ── Sarvam STT (Speech-to-Text) — Saaras v2.5 (Compatible with current SDK) ──
    stt = SarvamSTTService(
        api_key=os.getenv("SARVAM_API_KEY"),
        target_language_code="hi-IN",  # Auto-detect for multilingual students
        model="saaras:v2.5", # Downgraded from v3 to fix 'mode' argument error
        # mode="transcribe", # Removed as v2.5 doesn't support/need it
        voice_id="ishita"
    )

    # ── Sarvam TTS (Text-to-Speech) — Bulbul v3 ──
    tts = SarvamTTSService(
        api_key=os.getenv("SARVAM_API_KEY"),
        model="bulbul:v3",
        voice_id="ishita",  # Clear and articulate voice for teaching
        params=SarvamTTSService.InputParams(
            pace=0.9,  # Slightly slower for better understanding
            target_language_code="hi-IN", # Supports mixed EN/HI output
        ),
    )

    # ── LLM — Google Gemini 2.5 Pro (strong reasoning model) ──
    llm = GoogleLLMService(
        api_key=os.getenv("GOOGLE_API_KEY"),
        model="gemini-2.5-pro",
        params=GoogleLLMService.InputParams(
            max_tokens=8192,
            temperature=0.7,
            thinking=GoogleLLMService.ThinkingConfig(
                thinking_budget=4096,
            ),
        ),
    )

    # ── Conversation context ──
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    context = LLMContext(messages)
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(
            vad_analyzer=SileroVADAnalyzer(),
        ),
    )

    # ── Pipeline: Audio In → STT → Context → LLM → TTS → Audio Out ──
    pipeline = Pipeline(
        [
            transport.input(),
            FrameLogger("AudioIn", color="green"),
            stt,
            user_aggregator,
            TutorStatusProcessor(), # <-- Inject status processor here (before LLM)
            llm,
            tts,
            transport.output(),
            assistant_aggregator,
        ]
    )

    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            enable_metrics=True,
            enable_usage_metrics=True,
        ),
    )

    # ── Event handlers ──
    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        logger.info("Student connected")
        messages.append(
            {
                "role": "system",
                "content": "Greet the student warmly and ask what subject or topic they'd like to learn today.",
            }
        )
        await task.queue_frames([LLMRunFrame()])

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.info("Student disconnected")
        await task.cancel()

    try:
        logger.info("Initializing pipeline components...")
        runner = PipelineRunner(handle_sigint=handle_sigint)
        logger.info("Starting pipeline runner...")
        await runner.run(task)
        logger.info("Pipeline runner finished.")
    except Exception as e:
        logger.exception(f"Bot execution failed: {e}")
        raise


async def bot(runner_args: RunnerArguments):
    """Main bot entry point compatible with Pipecat runner."""
    logger.info("Starting the tutor bot")

    webrtc_connection: SmallWebRTCConnection = runner_args.webrtc_connection

    transport = SmallWebRTCTransport(
        webrtc_connection=webrtc_connection,
        params=TransportParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
        ),
    )

    if transport is None:
        logger.error("Failed to create transport")
        return

    await run_bot(transport, runner_args)
    logger.info("Bot process completed")


if __name__ == "__main__":
    from pipecat.runner.run import main

    main()
