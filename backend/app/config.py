from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    mock_sarvam: bool = True
    sarvam_api_key: str = ""
    data_dir: Path = Path(__file__).resolve().parent.parent / "data"

    llm_model: str = "sarvam-105b"
    reasoning_effort: str = "low"
    tts_model: str = "bulbul:v3"
    tts_speaker: str = "shubh"
    tts_sample_rate: int = 24000
    overrun_threshold: float = 0.2

    @property
    def performances_dir(self) -> Path:
        return self.data_dir / "runtime" / "performances"

    def snapshot(self) -> dict:
        """Settings recorded in meta.json. Never includes the API key."""
        return {
            "llm_model": self.llm_model,
            "reasoning_effort": self.reasoning_effort,
            "tts_model": self.tts_model,
            "tts_speaker": self.tts_speaker,
            "tts_sample_rate": self.tts_sample_rate,
            "overrun_threshold": self.overrun_threshold,
            "mock": self.mock_sarvam,
        }


settings = Settings()
