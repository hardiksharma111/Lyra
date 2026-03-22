import subprocess
import tempfile
import os
import re


TIMEOUT = 10  # seconds
BLOCKED = [
    "import os", "import sys", "import subprocess",
    "import shutil", "import socket", "import requests",
    "__import__", "open(", "eval(", "exec(",
    "os.system", "os.remove", "os.rmdir",
]


def run_code(code: str) -> str:
    """
    Execute Python code in a sandboxed subprocess.
    Blocks dangerous imports and operations.
    Returns stdout output or error message.
    """
    for pattern in BLOCKED:
        if pattern in code:
            return f"Blocked: '{pattern}' is not allowed in sandboxed execution."

    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as f:
            f.write(code)
            tmp_path = f.name

        python_cmd = "python" if os.name == "nt" else "python3"

        result = subprocess.run(
            [python_cmd, tmp_path],
            capture_output=True,
            text=True,
            timeout=TIMEOUT
        )

        try:
            os.unlink(tmp_path)
        except Exception:
            pass

        if result.returncode == 0:
            output = result.stdout.strip()
            return output if output else "Code ran successfully (no output)."
        else:
            error = result.stderr.strip()
            lines = error.split("\n")
            clean = [l for l in lines if "NamedTemporaryFile" not in l and "tmp" not in l.lower()]
            return "Error: " + "\n".join(clean).strip()

    except subprocess.TimeoutExpired:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        return f"Timed out after {TIMEOUT} seconds."
    except Exception as e:
        return f"Executor error: {e}"

    # Safety check
    for pattern in BLOCKED:
        if pattern in code:
            return f"Blocked: '{pattern}' is not allowed in sandboxed execution."

    # Write to temp file
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, dir="/tmp"
        ) as f:
            f.write(code)
            tmp_path = f.name

        result = subprocess.run(
            ["python3", tmp_path],
            capture_output=True,
            text=True,
            timeout=TIMEOUT
        )

        os.unlink(tmp_path)

        if result.returncode == 0:
            output = result.stdout.strip()
            return output if output else "Code ran successfully (no output)."
        else:
            error = result.stderr.strip()
            # Clean up traceback noise
            lines = error.split("\n")
            clean = [l for l in lines if not l.strip().startswith("File \"/tmp")]
            return "Error: " + "\n".join(clean).strip()

    except subprocess.TimeoutExpired:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        return f"Timed out after {TIMEOUT} seconds."
    except Exception as e:
        return f"Executor error: {e}"


def extract_and_run(text: str) -> str | None:
    """
    Extract a Python code block from text and run it.
    Returns result or None if no code block found.
    """
    match = re.search(r'```python\n(.*?)```', text, re.DOTALL)
    if not match:
        match = re.search(r'```\n(.*?)```', text, re.DOTALL)
    if not match:
        return None
    return run_code(match.group(1).strip())