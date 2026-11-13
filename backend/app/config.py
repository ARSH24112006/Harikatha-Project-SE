from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    mock_sarvam: bool = True
    sarvam_api_key: str = ""
    data_dir: Path = Path(__file__).resolve().parent.parent / "data"

    @property
    def performances_dir(self) -> Path:
        return self.data_dir / "runtime" / "performances"


settings = Settings()
