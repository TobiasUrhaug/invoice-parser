from pathlib import Path

from huggingface_hub import hf_hub_download
from llama_cpp import Llama


def init_model(
    model_dir: Path,
    repo_id: str,
    filename: str,
    n_ctx: int = 4096,
    n_gpu_layers: int = 0,
) -> Llama:
    model_path = model_dir / filename
    if not model_path.exists():
        downloaded = hf_hub_download(
            repo_id=repo_id, filename=filename, local_dir=model_dir
        )
        model_path = Path(downloaded)
    return Llama(
        model_path=str(model_path),
        n_ctx=n_ctx,
        n_gpu_layers=n_gpu_layers,
        verbose=False,
    )
