#!/bin/bash
set -e

echo "🔧 安装依赖..."
pip3 install -r requirements.txt

echo "📦 PyInstaller打包..."
python3 -m PyInstaller LegalMask.spec --clean

echo "✅ 完成！产物在 dist/LegalMask"
echo "macOS用户：直接双击 dist/LegalMask 运行"
