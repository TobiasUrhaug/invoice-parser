from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.core.config import get_settings
from app.services.llm_extractor import init_model


def test_init_model_downloads_when_file_absent(tmp_path: Path) -> None:
    mock_llama = MagicMock()
    with (
        patch("app.services.llm_extractor.hf_hub_download") as mock_download,
        patch("app.services.llm_extractor.Llama", return_value=mock_llama),
    ):
        mock_download.return_value = str(tmp_path / "model.gguf")
        init_model(
            model_dir=tmp_path,
            repo_id="org/repo",
            filename="model.gguf",
        )
    mock_download.assert_called_once_with(
        repo_id="org/repo",
        filename="model.gguf",
        local_dir=tmp_path,
    )


def test_init_model_skips_download_when_file_present(tmp_path: Path) -> None:
    model_file = tmp_path / "model.gguf"
    model_file.write_bytes(b"fake model data")
    mock_llama = MagicMock()
    with (
        patch("app.services.llm_extractor.hf_hub_download") as mock_download,
        patch("app.services.llm_extractor.Llama", return_value=mock_llama),
    ):
        init_model(
            model_dir=tmp_path,
            repo_id="org/repo",
            filename="model.gguf",
        )
    mock_download.assert_not_called()


def test_init_model_loads_with_correct_params(tmp_path: Path) -> None:
    model_file = tmp_path / "model.gguf"
    model_file.write_bytes(b"fake model data")
    mock_llama_cls = MagicMock()
    with (
        patch("app.services.llm_extractor.hf_hub_download"),
        patch("app.services.llm_extractor.Llama", mock_llama_cls),
    ):
        init_model(
            model_dir=tmp_path,
            repo_id="org/repo",
            filename="model.gguf",
        )
    mock_llama_cls.assert_called_once_with(
        model_path=str(model_file),
        n_ctx=4096,
        n_gpu_layers=0,
        verbose=False,
    )


def test_init_model_passes_custom_n_ctx_and_n_gpu_layers(tmp_path: Path) -> None:
    model_file = tmp_path / "model.gguf"
    model_file.write_bytes(b"fake model data")
    mock_llama_cls = MagicMock()
    with (
        patch("app.services.llm_extractor.hf_hub_download"),
        patch("app.services.llm_extractor.Llama", mock_llama_cls),
    ):
        init_model(
            model_dir=tmp_path,
            repo_id="org/repo",
            filename="model.gguf",
            n_ctx=2048,
            n_gpu_layers=32,
        )
    mock_llama_cls.assert_called_once_with(
        model_path=str(model_file),
        n_ctx=2048,
        n_gpu_layers=32,
        verbose=False,
    )


def test_init_model_uses_download_path_for_llama(tmp_path: Path) -> None:
    download_path = tmp_path / "cache" / "model.gguf"
    mock_llama_cls = MagicMock()
    with (
        patch("app.services.llm_extractor.hf_hub_download") as mock_download,
        patch("app.services.llm_extractor.Llama", mock_llama_cls),
    ):
        mock_download.return_value = str(download_path)
        init_model(
            model_dir=tmp_path,
            repo_id="org/repo",
            filename="model.gguf",
        )
    mock_llama_cls.assert_called_once_with(
        model_path=str(download_path),
        n_ctx=4096,
        n_gpu_layers=0,
        verbose=False,
    )


def test_init_model_returns_llama_instance(tmp_path: Path) -> None:
    model_file = tmp_path / "model.gguf"
    model_file.write_bytes(b"fake model data")
    mock_llama = MagicMock()
    with (
        patch("app.services.llm_extractor.hf_hub_download"),
        patch("app.services.llm_extractor.Llama", return_value=mock_llama),
    ):
        result = init_model(
            model_dir=tmp_path,
            repo_id="org/repo",
            filename="model.gguf",
        )
    assert result is mock_llama


async def test_lifespan_stores_pipeline_in_app_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.main import app, lifespan
    from app.services.pipeline import Pipeline

    monkeypatch.setenv("API_KEY", "test-key")
    get_settings.cache_clear()
    try:
        mock_llama = MagicMock()
        with (
            patch("app.main.init_model", return_value=mock_llama),
            patch("app.main.configure_logging"),
        ):
            async with lifespan(app):
                assert isinstance(app.state.pipeline, Pipeline)
                assert app.state.model_loaded is True
    finally:
        get_settings.cache_clear()
