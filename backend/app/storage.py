from .config import STORAGE_DIRECTORIES


def ensure_storage_directories() -> None:
    for directory in STORAGE_DIRECTORIES:
        directory.mkdir(parents=True, exist_ok=True)
