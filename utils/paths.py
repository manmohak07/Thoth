from pathlib import Path


def resolve_path(base: str | Path, path: str | Path):
    path = Path(path)
    if path.is_absolute():
        # True if the path has both a root and, if applicable,a drive.
        return path.resolve() # <- resolves all symlinks on the way and also normalizes it
    
    # e.g.
    # cwd -> users/abc/Desktop/project (this is the base path)
    # path -> utils/trial.py (this is the location of the concerned file)
    # resolution -> users/abc/Desktop/project/utils/trial.py (can also work with files outside the base path)

    return Path(base).resolve() / path

def is_binary_file(path: str | Path) -> bool:
    try:
        with open(path, 'rb') as f:
            chunk = f.read(8192) # <- Read first 8 KBs
            return f'\x00' in chunk # <- Check for null bytes

    except(OSError, IOError):
        return False