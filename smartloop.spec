# -*- mode: python ; coding: utf-8 -*-
import sys
import platform
import site
from pathlib import Path
from PyInstaller.utils.hooks import copy_metadata

datas = []
binaries = []

# Include package metadata required at runtime (importlib.metadata lookups)
for pkg in ['docling', 'docling-core', 'docling-ibm-models', 'docling-parse']:
    datas += copy_metadata(pkg)

# Collect tui css files
tui_css_dir = Path('.') / 'tui' / 'css'
if tui_css_dir.exists():
    datas.append((str(tui_css_dir), 'tui/css'))

# Collect llama_cpp shared libraries (libllama, libggml, etc.)
# These are required by the smartloop framework for model inference.
for sp in site.getsitepackages():
    llama_lib_dir = Path(sp) / 'llama_cpp' / 'lib'
    if llama_lib_dir.exists():
        for lib_file in llama_lib_dir.glob('*.so*' if sys.platform != 'win32' else '*.dll'):
            binaries.append((str(lib_file), 'llama_cpp/lib'))
        for lib_file in llama_lib_dir.glob('*.dylib'):
            binaries.append((str(lib_file), 'llama_cpp/lib'))
        break

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=[
        # CLI modules
        'commands',
        'commands.base',
        'commands.console',
        'commands.helpers',
        'commands.init',
        'commands.document',
        'commands.rule',
        'commands.model',
        'commands.run',
        'commands.token',
        'commands.mcp',
        'commands.server',
        'commands.projects',
        # TUI modules
        'tui',
        'tui.chat',
        'tui.constants',
        'tui.events',
        'tui.oauth',
        'tui.theme',
        'tui.commands',
        'tui.commands.attachment',
        'tui.commands.auth',
        'tui.commands.document',
        'tui.commands.mcp',
        'tui.commands.model_info',
        'tui.commands.project',
        'tui.commands.rule',
        'tui.widgets',
        'tui.widgets.chat_log',
        'tui.widgets.command_menu',
        'tui.widgets.prompt_text_area',
        'tui.workers',
        'tui.workers.bootstrap',
        'tui.workers.connection',
        'tui.workers.streaming',
        # SSL certificates
        'certifi',
        # llama_cpp shared library bindings
        'llama_cpp',
        'llama_cpp.llama_cpp',
        'llama_cpp._ctypes_extensions',
        # Document parsing (used by smartloop server for ingestion)
        'docling',
        'docling.document_converter',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        '.venv',
        'venv',
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='slp',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=platform.machine() if sys.platform == 'darwin' else None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=True,
    upx=True,
    upx_exclude=[],
    name='slp',
)
