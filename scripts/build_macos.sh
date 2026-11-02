#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export MACOSX_DEPLOYMENT_TARGET="${MACOSX_DEPLOYMENT_TARGET:-12.0}"
APP_VERSION="1.0.8"

python3 -m pip install --upgrade pip
python3 -m pip install -r requirements-build.txt
# numpy 2.x ships macosx_14_0 wheels that link the new Accelerate (they crash on macOS < 14)
# and macosx_11_0_arm64 / macosx_10_13_x86_64 wheels that bundle OpenBLAS. pip on a macOS 15
# runner picks the first kind, so force the OpenBLAS wheel to keep macOS 12 support.
case "$(uname -m)" in
  arm64) NUMPY_PLATFORM="macosx_11_0_arm64" ;;
  x86_64) NUMPY_PLATFORM="macosx_10_13_x86_64" ;;
  *) echo "Unsupported arch $(uname -m)" >&2; exit 1 ;;
esac
NUMPY_VERSION="$(python3 -c 'import numpy; print(numpy.__version__)')"
PY_TAG="$(python3 -c 'import sys; print(f"{sys.version_info.major}{sys.version_info.minor}")')"
WHEEL_DIR="$(mktemp -d)"
python3 -m pip download "numpy==$NUMPY_VERSION" --no-deps --only-binary=:all: --python-version "$PY_TAG" --platform "$NUMPY_PLATFORM" -d "$WHEEL_DIR"
python3 -m pip install --force-reinstall --no-deps "$WHEEL_DIR"/numpy-*.whl
python3 packaging/create_icons.py
python3 -m PyInstaller packaging/LegalMask.spec --clean --noconfirm
# Guard: fail the build if the bundled numpy needs the macOS 14+ Accelerate symbols.
NUMPY_SOS="$(find "$ROOT/dist/LegalMask.app" -name '_multiarray_umath*.so')"
NUMPY_SO="${NUMPY_SOS%%$'\n'*}"
test -n "$NUMPY_SO"
nm -u "$NUMPY_SO" > "$WHEEL_DIR/numpy_syms.txt"
if grep -q 'NEWLAPACK' "$WHEEL_DIR/numpy_syms.txt"; then
  echo "Bundled numpy needs the macOS 14+ Accelerate; refusing to build for macOS 12." >&2
  exit 1
fi

APP="$ROOT/dist/LegalMask.app"
codesign --force --deep --sign - "$APP"
codesign --verify --deep --strict "$APP"

plutil -extract LSMinimumSystemVersion raw "$APP/Contents/Info.plist" |
  grep -qx "$MACOSX_DEPLOYMENT_TARGET"
plutil -extract CFBundleShortVersionString raw "$APP/Contents/Info.plist" |
  grep -qx "$APP_VERSION"
plutil -extract NSAppTransportSecurity.NSAllowsLocalNetworking raw "$APP/Contents/Info.plist" |
  grep -qx "true"
"$APP/Contents/MacOS/LegalMask" --smoke-test

case "$(uname -m)" in
  arm64) ARCH="AppleSilicon" ;;
  x86_64) ARCH="Intel" ;;
  *) ARCH="$(uname -m)" ;;
esac

ZIP="$ROOT/dist/LegalMask-macOS-${ARCH}.zip"
rm -f "$ZIP"
ditto -c -k --sequesterRsrc --keepParent "$APP" "$ZIP"

echo "Built $ZIP with minimum macOS $MACOSX_DEPLOYMENT_TARGET"
