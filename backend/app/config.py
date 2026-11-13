from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    mock_sarvam: bool = True
    sarvam_api_key: str = ""
    sarvam_base_url: str = "https://api.sarvam.ai"
    data_dir: Path = Path(__file__).resolve().parent.parent / "data"
    sounds_dir: Path = Path(__file__).resolve().parent.parent / "sounds"

    llm_model: str = "sarvam-105b"
    reasoning_effort: str = "low"  # analyse + critique
    writing_reasoning_effort: str = "none"  # write + rewrite: "low" burned ~4.7k tokens per slot
    llm_temperature: float = 0.5
    llm_max_tokens: int = 6000  # reasoning tokens share this budget
    tts_model: str = "bulbul:v3"
    tts_speaker: str = "shubh"
    tts_sample_rate: int = 24000
    overrun_threshold: float = 0.2
    mix_disable: str = ""  # comma list of layers to leave out: drone,scene,pulse,bells

    request_timeout_sec: float = 120.0
    max_retries: int = 3
    retry_delay_sec: float = 1.0

    @property
    def performances_dir(self) -> Path:
        return self.data_dir / "runtime" / "performances"

    def snapshot(self) -> dict:
        """Settings recorded in meta.json. Never includes the API key."""
        return {
            "llm_model": self.llm_model,
            "reasoning_effort": self.reasoning_effort,
            "writing_reasoning_effort": self.writing_reasoning_effort,
            "tts_model": self.tts_model,
            "tts_speaker": self.tts_speaker,
            "tts_sample_rate": self.tts_sample_rate,
            "overrun_threshold": self.overrun_threshold,
            "mock": self.mock_sarvam,
        }


settings = Settings()
