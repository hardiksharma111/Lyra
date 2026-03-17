import os

FILES_DIR = os.path.join("memory", "files")
os.makedirs(FILES_DIR, exist_ok=True)


def save_file(filename: str, content: str) -> str:
    """Save content to memory/files/filename"""
    if not filename:
        return "No filename provided."
    filename = os.path.basename(filename)
    if not any(filename.endswith(ext) for ext in ['.txt', '.md', '.json', '.py', '.csv']):
        filename += '.txt'
    path = os.path.join(FILES_DIR, filename)
    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"Saved to {filename} ({len(content)} chars)"
    except Exception as e:
        return f"Save failed: {e}"


def read_file(filename: str) -> str:
    """Read content from memory/files/filename"""
    if not filename:
        return "No filename provided."
    filename = os.path.basename(filename)
    path = os.path.join(FILES_DIR, filename)
    if not os.path.exists(path):
        path_txt = path + '.txt'
        if os.path.exists(path_txt):
            path = path_txt
        else:
            files = list_files()
            return f"File '{filename}' not found. Saved files: {files}"
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        if len(content) > 4000:
            return content[:4000] + f"\n...[truncated, {len(content)} total chars]"
        return content
    except Exception as e:
        return f"Read failed: {e}"


def list_files() -> str:
    """List all files in memory/files/"""
    try:
        files = os.listdir(FILES_DIR)
        if not files:
            return "No saved files yet."
        sizes = []
        for f in sorted(files):
            path = os.path.join(FILES_DIR, f)
            size = os.path.getsize(path)
            sizes.append(f"{f} ({size} bytes)")
        return "\n".join(sizes)
    except Exception as e:
        return f"List failed: {e}"


def delete_file(filename: str) -> str:
    """Delete a file from memory/files/"""
    filename = os.path.basename(filename)
    path = os.path.join(FILES_DIR, filename)
    if not os.path.exists(path):
        return f"File '{filename}' not found."
    try:
        os.remove(path)
        return f"Deleted {filename}"
    except Exception as e:
        return f"Delete failed: {e}"