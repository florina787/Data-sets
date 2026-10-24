# PyInstaller spec: bundles the Python backend as a folder app "veena-backend".
# Build from veena-ai/:  pyinstaller packaging/backend.spec --noconfirm --distpath packaging/backend-dist --workpath packaging/build
# ruff: noqa
import os
import sys

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
sys.path.insert(0, ROOT)

# The backend imports its ML stack lazily (inside functions), which static
# analysis cannot see, so those packages are declared explicitly.
hidden = (
    collect_submodules("backend")
    + collect_submodules("uvicorn")
    + [
        "sqlmodel", "faiss", "pytesseract", "multipart", "python_multipart",
        "sentence_transformers", "torch", "transformers",
        "faster_whisper", "ctranslate2", "onnxruntime",
        "pymupdf", "docx", "markdown_it", "PIL.Image",
    ]
)
datas = (
    collect_data_files("faster_whisper")  # bundled Silero VAD ONNX model
    + collect_data_files("sentence_transformers")
    + collect_data_files("langgraph")
    + collect_data_files("pymupdf")
)

a = Analysis(
    [os.path.join(SPECPATH, "veena_backend_entry.py")],
    pathex=[ROOT],
    hiddenimports=hidden,
    datas=datas,
    # Large optional stacks the backend never imports.
    excludes=["tkinter", "matplotlib", "IPython", "jupyter", "notebook", "pandas.tests", "torch.utils.tensorboard", "triton"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="veena-backend", console=True, upx=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="veena-backend")
