import os
from pathlib import Path

from app.infrastructure.config import settings as settings_module


def test_get_settings_loads_dotenv_for_external_sdks(tmp_path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "OPENAI_API_KEY=test-key",
                "LANGSMITH_TRACING=true",
                "LANGSMITH_PROJECT=teachmewow-local",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(settings_module, "ENV_FILE_PATH", Path(env_file))
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
    monkeypatch.delenv("LANGSMITH_PROJECT", raising=False)
    settings_module.get_settings.cache_clear()

    _ = settings_module.get_settings()

    assert os.environ.get("LANGSMITH_TRACING") == "true"
    assert os.environ.get("LANGSMITH_PROJECT") == "teachmewow-local"
