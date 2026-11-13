import base64
import io
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient

from omni_audio import (
    INPUT_SAMPLE_RATE,
    create_app,
    normalize_audio,
    pcm16_to_wav,
    write_chat_media,
)


def make_wav(sample_rate: int = 24000, duration: float = 0.05) -> bytes:
    samples = np.sin(np.linspace(0, 2 * np.pi, int(sample_rate * duration))).astype(
        np.float32
    )
    buffer = io.BytesIO()
    sf.write(buffer, samples, sample_rate, subtype="PCM_16", format="WAV")
    return buffer.getvalue()


class FakeEngine:
    def __init__(self):
        self._model = None
        self.started = False

    def start(self):
        self.started = True
        self._model = {"loaded": True}

    def transcribe(self, audio_path, language, prompt, max_tokens):
        assert Path(audio_path).is_file()
        return "fixed transcript"

    def chat(self, payload):
        assert payload.messages
        return "fixed chat response"

    def synthesize(self, text, voice, max_tokens):
        self._voice_path(voice)
        return make_wav(), 24000

    def conversation(self, audio_path, language, voice, max_tokens):
        assert Path(audio_path).is_file()
        self._voice_path(voice)
        return "fixed spoken response", make_wav(), 24000

    def _voice_path(self, voice):
        if voice not in (None, "known"):
            raise ValueError(f"Unknown voice: {voice}")
        return None


@pytest.fixture
def client():
    engine = FakeEngine()
    with TestClient(create_app(engine=engine, api_key="test-key")) as test_client:
        test_client.engine = engine
        yield test_client


def auth_headers():
    return {"Authorization": "Bearer test-key"}


def test_audio_normalization_to_16khz_mono(tmp_path):
    source = tmp_path / "stereo.wav"
    output = tmp_path / "normalized.wav"
    samples = np.ones((800, 2), dtype=np.float32)
    sf.write(source, samples, 8000, subtype="PCM_16")

    duration = normalize_audio(source, output)
    normalized, sample_rate = sf.read(output, always_2d=True)

    assert sample_rate == INPUT_SAMPLE_RATE
    assert normalized.shape[1] == 1
    assert duration == pytest.approx(0.1)


def test_transcription_requires_auth_and_returns_text(client):
    payload = {"file": ("sample.wav", make_wav(8000), "audio/wav")}

    assert client.post("/v1/audio/transcriptions", files=payload).status_code == 401
    response = client.post(
        "/v1/audio/transcriptions", files=payload, headers=auth_headers()
    )

    assert response.status_code == 200
    assert response.json()["text"] == "fixed transcript"
    assert response.json()["duration"] == pytest.approx(0.05)


def test_conversation_returns_text_and_valid_wav(client):
    response = client.post(
        "/v1/audio/conversation",
        files={"file": ("sample.wav", make_wav(), "audio/wav")},
        headers=auth_headers(),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["text"] == "fixed spoken response"
    assert payload["format"] == "wav"
    samples, sample_rate = sf.read(io.BytesIO(base64.b64decode(payload["audio"])))
    assert sample_rate == 24000
    assert len(samples) > 0


def test_unknown_voice_is_rejected(client):
    response = client.post(
        "/v1/audio/speech",
        json={
            "model": "omni",
            "input": "hello",
            "voice": "missing",
            "response_format": "wav",
        },
        headers=auth_headers(),
    )

    assert response.status_code == 400
    assert "Unknown voice" in response.json()["detail"]


def test_realtime_pcm_conversation(client):
    pcm = (np.sin(np.linspace(0, 2 * np.pi, 1600)) * 1000).astype(np.int16).tobytes()

    with client.websocket_connect("/v1/audio/realtime") as websocket:
        websocket.send_json(
            {"type": "start", "api_key": "test-key", "language": "auto"}
        )
        assert websocket.receive_json()["type"] == "session.created"
        websocket.send_json(
            {
                "type": "input_audio_buffer.append",
                "audio": base64.b64encode(pcm).decode(),
            }
        )
        websocket.send_json({"type": "input_audio_buffer.commit"})

        text = ""
        audio = bytearray()
        while True:
            event = websocket.receive_json()
            assert event["type"] != "error"
            if event["type"] == "response.text.delta":
                text += event["delta"]
            elif event["type"] == "response.audio.delta":
                assert event["sample_rate"] == 24000
                audio.extend(base64.b64decode(event["delta"]))
            elif event["type"] == "response.done":
                break

    assert text == "fixed spoken response"
    assert len(audio) > 0


def test_realtime_rejects_invalid_key(client):
    with client.websocket_connect("/v1/audio/realtime") as websocket:
        websocket.send_json({"type": "start", "api_key": "wrong"})
        assert websocket.receive_json()["type"] == "error"


def test_pcm16_rejects_odd_byte_count(tmp_path):
    with pytest.raises(ValueError, match="odd byte length"):
        pcm16_to_wav(b"\x00", tmp_path / "invalid.wav")


def test_model_discovery_requires_auth(client):
    assert client.get("/v1/models/omni").status_code == 401
    response = client.get("/v1/models/omni", headers=auth_headers())
    assert response.status_code == 200
    assert response.json() == {
        "id": "omni",
        "object": "model",
        "created": 0,
        "owned_by": "omni-audio",
    }


def test_chat_completions_returns_openai_response(client):
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "omni",
            "messages": [{"role": "user", "content": "Hello"}],
        },
        headers=auth_headers(),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["object"] == "chat.completion"
    assert payload["model"] == "omni"
    assert payload["choices"][0]["message"] == {
        "role": "assistant",
        "content": "fixed chat response",
    }


def test_chat_media_decodes_inline_audio_and_image(tmp_path):
    audio = base64.b64encode(make_wav()).decode()
    image = base64.b64encode(b"png-test").decode()
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Inspect both inputs"},
                {
                    "type": "input_audio",
                    "input_audio": {"data": audio, "format": "wav"},
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{image}"},
                },
            ],
        }
    ]

    image_paths, audio_paths = write_chat_media(messages, tmp_path)

    assert len(audio_paths) == 1
    assert len(image_paths) == 1
    assert Path(audio_paths[0]).read_bytes() == make_wav()
    assert Path(image_paths[0]).read_bytes() == b"png-test"
    assert messages[0]["content"][1]["input_audio"]["data"] == audio


def test_chat_rejects_remote_images(tmp_path):
    with pytest.raises(ValueError, match="inline data:image"):
        write_chat_media(
            [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": "https://example.com/a.png"},
                        }
                    ],
                }
            ],
            tmp_path,
        )
