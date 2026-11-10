# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['game_pygame.py'],
    pathex=[],
    binaries=[],
    datas=[('models', 'models'), ('assets', 'assets')],
    hiddenimports=['pygame', 'vosk', 'sounddevice', 'edge_tts', 'pyttsx3', 'asyncio'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='LogopedicFishing',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
