#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export MACOSX_DEPLOYMENT_TARGET="${MACOSX_DEPLOYMENT_TARGET:-12.0}"
APP_VERSION="1.0.2"

python3 -m pip install --upgrade pip
python3 -m pip install -r requirements-build.txt
python3 packaging/create_icons.py
python3 -m PyInstaller packaging/LegalMask.spec --clean --noconfirm

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
