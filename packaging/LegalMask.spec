from pathlib import Path

from PyInstaller.utils.hooks import collect_all, copy_metadata, collect_data_files
from PyInstaller.compat import is_darwin, is_win


ROOT = Path(SPECPATH).resolve().parent

datas = [
    (str(ROOT / "app.py"), "."),
    (str(ROOT / "core"), "core"),
    (str(ROOT / ".streamlit"), ".streamlit"),
    (str(ROOT / "assets" / "icon.png"), "assets"),
    (str(ROOT / "assets" / "icon.ico"), "assets"),
]

# Explicitly include RapidOCR model files
try:
    import rapidocr_onnxruntime
    import os
    rapidocr_pkg_dir = os.path.dirname(rapidocr_onnxruntime.__file__)
    rapidocr_models_dir = os.path.join(rapidocr_pkg_dir, "models")
    if os.path.exists(rapidocr_models_dir):
        for model_file in os.listdir(rapidocr_models_dir):
            if model_file.endswith(".onnx"):
                model_path = os.path.join(rapidocr_models_dir, model_file)
                datas.append((model_path, "rapidocr_onnxruntime/models"))
except ImportError:
    pass
binaries = []
hiddenimports = [
    "core",
    "core.processor",
    "core.temp_workspace",
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan.on",
    "watchdog.observers.polling",
]

for package in (
    "streamlit",
    "rapidocr_onnxruntime",
    "onnxruntime",
    "pymupdf",
    "webview",
    "docx",
):
    package_datas, package_binaries, package_hiddenimports = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hiddenimports

for distribution in (
    "streamlit",
    "rapidocr-onnxruntime",
    "pymupdf",
    "python-docx",
    "pywebview",
):
    datas += copy_metadata(distribution)

if is_win:
    hiddenimports += [
        "clr",
        "pythonnet",
        "clr_loader",
        "webview.platforms.edgechromium",
        "webview.platforms.winforms",
    ]
elif is_darwin:
    hiddenimports += [
        "webview.platforms.cocoa",
        "objc",
        "Foundation",
        "AppKit",
        "WebKit",
    ]

hiddenimports = sorted(set(hiddenimports))
custom_icon = ROOT / ("assets/icon.ico" if is_win else "assets/icon.icns")

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe_options = {}
if is_win:
    version_file = ROOT / "packaging" / "windows" / "version_info.txt"
    if version_file.exists():
        exe_options["version"] = str(version_file)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="LegalMask",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(custom_icon) if custom_icon.exists() else None,
    **exe_options,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="LegalMask",
)

if is_darwin:
    app = BUNDLE(
        coll,
        name="LegalMask.app",
        icon=str(custom_icon) if custom_icon.exists() else None,
        bundle_identifier="com.guoba371.legalmask",
        info_plist={
            "CFBundleDisplayName": "LegalMask",
            "CFBundleName": "LegalMask",
            "CFBundleShortVersionString": "1.0.8",
            "CFBundleVersion": "1",
            "LSMinimumSystemVersion": "12.0",
            "NSHighResolutionCapable": True,
            "NSAppTransportSecurity": {
                "NSAllowsLocalNetworking": True,
            },
            "NSDocumentsFolderUsageDescription": "LegalMask 需要读取您选择的文书文件。",
            "NSDownloadsFolderUsageDescription": "LegalMask 需要保存脱敏后的文书文件。",
        },
    )

