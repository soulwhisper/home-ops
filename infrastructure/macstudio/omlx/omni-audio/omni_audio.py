from __future__ import annotations

import asyncio
import base64
import binascii
import io
import json
import os
import re
import secrets
import tempfile
import threading
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

import librosa
import numpy as np
import soundfile as sf
from fastapi import (
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

INPUT_SAMPLE_RATE = 16000
MAX_UPLOAD_BYTES = 100 * 1024 * 1024
MAX_AUDIO_SECONDS = 600
MAX_REALTIME_BYTES = MAX_AUDIO_SECONDS * INPUT_SAMPLE_RATE * 2
MAX_WAITING_REQUESTS = 4
ASR_PROMPTS = {
    "zh": "请仔细听这段音频片段，并将其内容逐字记录。",
    "en": "Please listen to the audio snippet carefully and transcribe the content.\n",
}
CONVERSATION_PROMPTS = {
    "zh": "请仔细听用户的音频，并用中文简洁、自然地回答。",
    "en": "Listen carefully to the user's audio and respond concisely and naturally in English.",
    "auto": "Listen carefully to the user's audio. Respond concisely and naturally in the same language, English or Chinese.",
}


def load_api_keys() -> set[str]:
    """Load the oMLX upstream key and the gateway's Omni lane key without logging either."""
    upstream = os.environ.get("OMNI_API_KEY")
    if upstream is None:
        settings_path = Path.home() / ".omlx" / "settings.json"
        with settings_path.open() as handle:
            upstream = json.load(handle)["auth"]["api_key"]
    lane = os.environ.get("OMNI_LANE_API_KEY")
    if not upstream or upstream == "INJECT_AT_DEPLOY":
        raise RuntimeError("A usable oMLX auth.api_key or OMNI_API_KEY is required")
    if not lane or lane == "INJECT_AT_DEPLOY":
        raise RuntimeError(
            "OMNI_LANE_API_KEY must contain the agentgateway Omni credential"
        )
    return {upstream, lane}


def key_matches(value: str, api_keys: set[str]) -> bool:
    return any(secrets.compare_digest(value.encode(), key.encode()) for key in api_keys)


def authorized(header: str | None, api_keys: set[str]) -> bool:
    if not header or not header.startswith("Bearer "):
        return False
    return key_matches(header[7:], api_keys)


def normalize_audio(input_path: Path, output_path: Path) -> float:
    """Convert an uploaded clip to 16 kHz mono PCM WAV and bound its duration."""
    duration = librosa.get_duration(path=str(input_path))
    if duration > MAX_AUDIO_SECONDS:
        raise ValueError(f"Audio exceeds the {MAX_AUDIO_SECONDS}-second limit")
    samples, _ = librosa.load(input_path, sr=INPUT_SAMPLE_RATE, mono=True)
    if samples.size == 0:
        raise ValueError("Audio contains no samples")
    duration = len(samples) / INPUT_SAMPLE_RATE
    if duration > MAX_AUDIO_SECONDS:
        raise ValueError(f"Audio exceeds the {MAX_AUDIO_SECONDS}-second limit")
    sf.write(output_path, samples, INPUT_SAMPLE_RATE, subtype="PCM_16")
    return duration


def pcm16_to_wav(payload: bytes, output_path: Path) -> float:
    if len(payload) % 2:
        raise ValueError("PCM16 input has an odd byte length")
    samples = np.frombuffer(payload, dtype=np.int16).astype(np.float32) / 32768.0
    sf.write(output_path, samples, INPUT_SAMPLE_RATE, subtype="PCM_16")
    return len(samples) / INPUT_SAMPLE_RATE


def wav_to_pcm16(wav_bytes: bytes) -> bytes:
    samples, _ = sf.read(io.BytesIO(wav_bytes), dtype="float32")
    clipped = np.clip(samples, -1.0, 1.0)
    return (clipped * 32767).astype(np.int16).tobytes()


def temporary_path(suffix: str) -> Path:
    descriptor, path = tempfile.mkstemp(suffix=suffix)
    os.close(descriptor)
    return Path(path)


class SpeechRequest(BaseModel):
    model: str = "omni"
    input: str = Field(min_length=1, max_length=10000)
    voice: str | None = None
    response_format: str = "wav"
    max_tokens: int = Field(default=512, gt=0, le=2048)


class ChatRequest(BaseModel):
    model: str = "omni"
    messages: list[dict[str, Any]] = Field(min_length=1)
    max_tokens: int = Field(default=512, gt=0, le=2048)
    temperature: float = Field(default=0.6, ge=0.0, le=2.0)
    top_p: float = Field(default=0.95, gt=0.0, le=1.0)


def decode_inline_data(value: str) -> bytes:
    if not isinstance(value, str):
        raise ValueError("Inline media data must be a base64 string")
    encoded = value.partition(",")[2] if value.startswith("data:") else value
    try:
        return base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as error:
        raise ValueError("Inline media must be valid base64") from error


def write_chat_media(
    messages: list[dict[str, Any]], directory: Path
) -> tuple[list[str], list[str]]:
    """Decode inline image/audio parts into temporary files without dropping message markers."""
    images: list[str] = []
    audio: list[str] = []
    image_suffixes = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/webp": ".webp",
        "image/gif": ".gif",
    }
    audio_suffixes = {"wav", "mp3", "m4a", "aac", "ogg", "flac", "opus", "webm"}
    for message in messages:
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if not isinstance(part, dict):
                continue
            kind = part.get("type")
            if kind in ("image", "image_url", "input_image"):
                reference = part.get(
                    "image_url", part.get("image", part.get("url", ""))
                )
                if isinstance(reference, dict):
                    reference = reference.get("url", "")
                if not isinstance(reference, str) or not reference.startswith(
                    "data:image/"
                ):
                    raise ValueError(
                        "Images must use an inline data:image/*;base64 URI"
                    )
                mime = reference[5:].split(";", 1)[0].lower()
                if mime not in image_suffixes:
                    raise ValueError(f"Unsupported image type: {mime}")
                path = directory / f"image-{len(images)}{image_suffixes[mime]}"
                path.write_bytes(decode_inline_data(reference))
                images.append(str(path))
            elif kind == "input_audio":
                reference = part.get("input_audio", {})
                data = reference.get("data", "") if isinstance(reference, dict) else ""
                audio_format = (
                    str(reference.get("format", "wav")).lower()
                    if isinstance(reference, dict)
                    else "wav"
                )
                if audio_format not in audio_suffixes:
                    raise ValueError(f"Unsupported audio format: {audio_format}")
                path = directory / f"audio-{len(audio)}.{audio_format}"
                payload = decode_inline_data(data)
                if len(payload) > MAX_UPLOAD_BYTES:
                    raise ValueError("Inline audio exceeds the 100 MiB limit")
                path.write_bytes(payload)
                normalized = directory / f"audio-{len(audio)}-normalized.wav"
                normalize_audio(path, normalized)
                audio.append(str(normalized))
    return images, audio


class OmniEngine:
    """A pinned MiniCPM-O engine using mlx-vlm directly, without oMLX audio routing."""

    def __init__(self, model_path: Path, voice_dir: Path):
        self.model_path = model_path
        self.voice_dir = voice_dir
        self._model = None
        self._processor = None
        self._lock = threading.Lock()

    def start(self) -> None:
        if self._model is not None:
            return
        from mlx_vlm import load

        self._model, self._processor = load(str(self.model_path))

    def _voice_path(self, voice: str | None) -> str | None:
        if voice is None or not voice.strip():
            return None
        voice = voice.strip()
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", voice):
            raise ValueError(
                "Voice names may contain only lowercase letters, digits, '_' and '-'"
            )
        path = self.voice_dir / f"{voice}.wav"
        if not path.is_file():
            raise ValueError(f"Unknown voice: {voice}")
        return str(path)

    def _text_from_audio(
        self,
        audio_path: Path,
        prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> str:
        from mlx_vlm import generate
        from mlx_vlm.prompt_utils import apply_chat_template

        formatted = apply_chat_template(
            self._processor,
            self._model.config,
            prompt,
            num_audios=1,
            enable_thinking=False,
        )
        result = generate(
            model=self._model,
            processor=self._processor,
            prompt=formatted,
            audio=[str(audio_path)],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        text = result.text.strip()
        if not text:
            raise RuntimeError("Omni returned an empty audio response")
        return text

    def _synthesize(
        self, text: str, voice: str | None, max_tokens: int
    ) -> tuple[bytes, int]:
        from mlx_vlm import generate_audio
        from mlx_vlm.prompt_utils import apply_chat_template

        formatted = apply_chat_template(
            self._processor,
            self._model.config,
            text,
            enable_thinking=False,
            use_tts_template=True,
        )
        kwargs: dict[str, Any] = {}
        if reference := self._voice_path(voice):
            kwargs["ref_audio_path"] = reference
        result = generate_audio(
            model=self._model,
            processor=self._processor,
            prompt=formatted,
            max_tokens=max_tokens,
            temperature=0.3,
            **kwargs,
        )
        return result.to_wav_bytes(), result.sample_rate

    def chat(self, payload: ChatRequest) -> str:
        from mlx_vlm import generate
        from mlx_vlm.prompt_utils import apply_chat_template

        with tempfile.TemporaryDirectory(prefix="omni-chat-") as directory:
            images, audio = write_chat_media(payload.messages, Path(directory))
            formatted = apply_chat_template(
                self._processor,
                self._model.config,
                payload.messages,
                num_images=len(images),
                num_audios=len(audio),
                enable_thinking=False,
            )
            media_kwargs: dict[str, Any] = {}
            if images:
                media_kwargs["image"] = images
            if audio:
                media_kwargs["audio"] = audio
            with self._lock:
                result = generate(
                    model=self._model,
                    processor=self._processor,
                    prompt=formatted,
                    max_tokens=payload.max_tokens,
                    temperature=payload.temperature,
                    top_p=payload.top_p,
                    **media_kwargs,
                )
        text = result.text.strip()
        if not text:
            raise RuntimeError("Omni returned an empty chat response")
        return text

    def transcribe(
        self,
        audio_path: Path,
        language: str | None,
        prompt: str | None,
        max_tokens: int,
    ) -> str:
        language_key = "zh" if language and language.lower().startswith("zh") else "en"
        instruction = ASR_PROMPTS[language_key]
        if prompt and prompt.strip():
            instruction += f"\nAdditional vocabulary or context: {prompt.strip()}"
        with self._lock:
            return self._text_from_audio(audio_path, instruction, max_tokens, 0.0)

    def synthesize(
        self, text: str, voice: str | None, max_tokens: int
    ) -> tuple[bytes, int]:
        with self._lock:
            return self._synthesize(text, voice, max_tokens)

    def conversation(
        self,
        audio_path: Path,
        language: str | None,
        voice: str | None,
        max_tokens: int,
    ) -> tuple[str, bytes, int]:
        language_key = language if language in CONVERSATION_PROMPTS else "auto"
        with self._lock:
            text = self._text_from_audio(
                audio_path,
                CONVERSATION_PROMPTS[language_key],
                max_tokens,
                0.3,
            )
            wav, sample_rate = self._synthesize(text, voice, max_tokens)
        return text, wav, sample_rate


class EngineLimiter:
    """Serialize model calls and retain capacity until cancelled workers actually finish."""

    def __init__(self):
        self._model_lock = asyncio.Lock()
        self._counter_lock = asyncio.Lock()
        self._waiting = 0

    async def _release(self, lock_acquired: bool) -> None:
        if lock_acquired:
            self._model_lock.release()
        async with self._counter_lock:
            self._waiting -= 1

    async def _release_when_done(self, worker: asyncio.Task) -> None:
        try:
            await worker
        except Exception:
            pass
        finally:
            await self._release(True)

    async def run(self, function: Callable[[], Any]) -> Any:
        async with self._counter_lock:
            if self._waiting >= MAX_WAITING_REQUESTS:
                raise HTTPException(
                    status_code=429, detail="Omni inference queue is full"
                )
            self._waiting += 1
        lock_acquired = False
        worker: asyncio.Task | None = None
        try:
            await self._model_lock.acquire()
            lock_acquired = True
            worker = asyncio.create_task(asyncio.to_thread(function))
            return await asyncio.shield(worker)
        finally:
            if worker is not None and not worker.done():
                asyncio.create_task(self._release_when_done(worker))
            else:
                await self._release(lock_acquired)


def create_app(
    engine: OmniEngine | None = None, api_keys: set[str] | None = None
) -> FastAPI:
    engine = engine or OmniEngine(
        model_path=Path(
            os.environ.get(
                "OMNI_MODEL_PATH",
                "~/Library/Application Support/omni-audio/model",
            )
        ).expanduser(),
        voice_dir=Path(os.environ.get("OMNI_VOICE_DIR", "~/.omlx/voices")).expanduser(),
    )
    api_keys = api_keys or load_api_keys()
    limiter = EngineLimiter()

    async def lifespan(_: FastAPI):
        await asyncio.to_thread(engine.start)
        yield

    app = FastAPI(lifespan=lifespan)

    @app.middleware("http")
    async def authenticate_before_body_parsing(request: Request, call_next):
        if request.url.path.startswith("/v1/") and not authorized(
            request.headers.get("authorization"), api_keys
        ):
            return JSONResponse(
                status_code=401, content={"detail": "Invalid or missing bearer token"}
            )
        try:
            content_length = int(request.headers.get("content-length", "0"))
        except ValueError:
            return JSONResponse(
                status_code=400, content={"detail": "Invalid Content-Length"}
            )
        if content_length > MAX_UPLOAD_BYTES:
            return JSONResponse(
                status_code=413, content={"detail": "Request exceeds the 100 MiB limit"}
            )
        return await call_next(request)

    @app.exception_handler(ValueError)
    async def invalid_value(_: Request, error: ValueError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(error)})

    async def require_auth(request: Request) -> None:
        if not authorized(request.headers.get("authorization"), api_keys):
            raise HTTPException(
                status_code=401, detail="Invalid or missing bearer token"
            )

    async def prepare_upload(file: UploadFile) -> tuple[Path, float]:
        suffix = Path(file.filename or "audio.wav").suffix or ".wav"
        source_path = temporary_path(suffix)
        output_path = temporary_path(".wav")
        try:
            with source_path.open("wb") as source:
                total = 0
                while chunk := await file.read(1024 * 1024):
                    total += len(chunk)
                    if total > MAX_UPLOAD_BYTES:
                        raise HTTPException(
                            status_code=413, detail="Audio upload exceeds 100 MiB"
                        )
                    source.write(chunk)
            duration = await asyncio.to_thread(
                normalize_audio, source_path, output_path
            )
            return output_path, duration
        except Exception:
            output_path.unlink(missing_ok=True)
            raise
        finally:
            source_path.unlink(missing_ok=True)

    @app.get("/healthz")
    async def health() -> dict[str, Any]:
        return {"status": "ok", "model": "omni", "loaded": engine._model is not None}

    @app.get("/v1/models/omni")
    async def model_info(request: Request) -> dict[str, Any]:
        await require_auth(request)
        return {"id": "omni", "object": "model", "created": 0, "owned_by": "omni-audio"}

    @app.post("/v1/chat/completions")
    async def chat(payload: ChatRequest, request: Request) -> dict[str, Any]:
        await require_auth(request)
        if payload.model != "omni":
            raise HTTPException(
                status_code=400, detail="Only model 'omni' is available"
            )
        text = await limiter.run(lambda: engine.chat(payload))
        return {
            "id": f"chatcmpl-{uuid.uuid4().hex}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": "omni",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": text},
                    "finish_reason": "stop",
                }
            ],
        }

    @app.post("/v1/audio/transcriptions")
    async def transcribe(
        request: Request,
        file: UploadFile = File(...),
        language: str | None = Form(None),
        prompt: str | None = Form(None),
        max_tokens: int = Form(512),
    ) -> dict[str, Any]:
        await require_auth(request)
        if not 0 < max_tokens <= 2048:
            raise HTTPException(
                status_code=400, detail="max_tokens must be between 1 and 2048"
            )
        audio_path, duration = await prepare_upload(file)
        try:
            text = await limiter.run(
                lambda: engine.transcribe(audio_path, language, prompt, max_tokens)
            )
            return {"text": text, "duration": duration}
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        finally:
            audio_path.unlink(missing_ok=True)

    @app.post("/v1/audio/speech")
    async def speech(payload: SpeechRequest, request: Request) -> Response:
        await require_auth(request)
        if payload.model != "omni":
            raise HTTPException(
                status_code=400, detail="Only model 'omni' is available"
            )
        if payload.response_format != "wav":
            raise HTTPException(
                status_code=400, detail="Only response_format='wav' is supported"
            )
        try:
            wav, _ = await limiter.run(
                lambda: engine.synthesize(
                    payload.input, payload.voice, payload.max_tokens
                )
            )
            return Response(content=wav, media_type="audio/wav")
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.post("/v1/audio/conversation")
    async def conversation(
        request: Request,
        file: UploadFile = File(...),
        voice: str | None = Form(None),
        language: str | None = Form("auto"),
        max_tokens: int = Form(512),
    ) -> dict[str, Any]:
        await require_auth(request)
        if not 0 < max_tokens <= 2048:
            raise HTTPException(
                status_code=400, detail="max_tokens must be between 1 and 2048"
            )
        audio_path, _ = await prepare_upload(file)
        try:
            text, wav, sample_rate = await limiter.run(
                lambda: engine.conversation(audio_path, language, voice, max_tokens)
            )
            return {
                "text": text,
                "audio": base64.b64encode(wav).decode("ascii"),
                "format": "wav",
                "sample_rate": sample_rate,
            }
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        finally:
            audio_path.unlink(missing_ok=True)

    @app.websocket("/v1/audio/realtime")
    async def realtime(websocket: WebSocket) -> None:
        await websocket.accept()
        response_task: asyncio.Task | None = None
        audio_buffer = bytearray()

        async def send_error(message: str) -> None:
            await websocket.send_json({"type": "error", "error": {"message": message}})

        async def run_response(
            payload: bytes, voice: str | None, language: str | None
        ) -> None:
            audio_path = temporary_path(".wav")
            try:
                pcm16_to_wav(payload, audio_path)
                text, wav, sample_rate = await limiter.run(
                    lambda: engine.conversation(audio_path, language, voice, 512)
                )
                await websocket.send_json({"type": "response.created", "model": "omni"})
                await websocket.send_json(
                    {"type": "response.text.delta", "delta": text}
                )
                pcm = wav_to_pcm16(wav)
                for offset in range(0, len(pcm), 8192):
                    chunk = base64.b64encode(pcm[offset : offset + 8192]).decode(
                        "ascii"
                    )
                    await websocket.send_json(
                        {
                            "type": "response.audio.delta",
                            "sample_rate": sample_rate,
                            "delta": chunk,
                        }
                    )
                await websocket.send_json({"type": "response.done"})
            except asyncio.CancelledError:
                await websocket.send_json({"type": "response.cancelled"})
                raise
            except Exception as error:
                await send_error(str(error))
            finally:
                audio_path.unlink(missing_ok=True)

        try:
            start = await websocket.receive_json()
            authenticated = authorized(
                websocket.headers.get("authorization"), api_keys
            ) or key_matches(str(start.get("api_key", "")), api_keys)
            if start.get("type") != "start" or not authenticated:
                await send_error("Invalid or missing API key")
                await websocket.close(code=4401)
                return
            voice = start.get("voice")
            language = start.get("language", "auto")
            engine._voice_path(voice)
            await websocket.send_json(
                {
                    "type": "session.created",
                    "model": "omni",
                    "input_sample_rate": INPUT_SAMPLE_RATE,
                    "input_format": "pcm16",
                }
            )
            while True:
                message = await websocket.receive_json()
                message_type = message.get("type")
                if message_type == "input_audio_buffer.append":
                    try:
                        chunk = base64.b64decode(
                            message.get("audio", ""), validate=True
                        )
                    except (binascii.Error, ValueError):
                        await send_error("Audio must be valid base64 PCM16")
                        continue
                    if (
                        len(chunk) % 2
                        or len(audio_buffer) + len(chunk) > MAX_REALTIME_BYTES
                    ):
                        await send_error(
                            "Realtime buffer exceeds the ten-minute PCM16 limit"
                        )
                        continue
                    audio_buffer.extend(chunk)
                elif message_type == "input_audio_buffer.commit":
                    if not audio_buffer:
                        await send_error("Cannot commit an empty audio buffer")
                        continue
                    if response_task is not None and not response_task.done():
                        await send_error(
                            "Cancel the active response before committing another turn"
                        )
                        continue
                    payload = bytes(audio_buffer)
                    audio_buffer.clear()
                    response_task = asyncio.create_task(
                        run_response(payload, voice, language)
                    )
                elif message_type == "response.cancel":
                    audio_buffer.clear()
                    if response_task is not None and not response_task.done():
                        response_task.cancel()
                elif message_type == "ping":
                    await websocket.send_json({"type": "pong"})
                elif message_type == "close":
                    break
                else:
                    await send_error(f"Unsupported message type: {message_type}")
        except WebSocketDisconnect:
            pass
        except (ValueError, binascii.Error) as error:
            await send_error(str(error))
        finally:
            if response_task is not None and not response_task.done():
                response_task.cancel()
            if response_task is not None:
                try:
                    await response_task
                except (asyncio.CancelledError, Exception):
                    pass

    return app
