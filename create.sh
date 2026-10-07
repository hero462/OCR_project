#!/usr/bin/env bash
# build_both.sh — лежит в КОРНЕ проекта.
# Собирает ровно два файла для раздачи:
#   release/HandwriteCollector      (Linux)
#   release/HandwriteCollector.exe  (Windows)
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$PWD"

# ---------- 1) ищем исходник ----------
SRC=""
for cand in "collect_dataset/volunteer_collector.py" "volunteer_collector.py"; do
    [ -f "$cand" ] && SRC="$cand" && break
done
[ -n "$SRC" ] || { echo "❌ Не нашёл volunteer_collector.py (искал в collect_dataset/ и в корне)"; exit 1; }
echo "📄 Исходник: $SRC"
mkdir -p release

# ---------- 2) Linux-файл ----------
echo ""
echo "🐧 Собираю исполняемый файл под Linux..."
VENV=""
for v in "collect_dataset/.build_linux" ".build_linux"; do
    [ -x "$v/bin/activate" ] && VENV="$v" && break
done
if [ -z "$VENV" ]; then
    python3 -c "import tkinter" 2>/dev/null || {
        echo "❌ Нет tkinter: sudo apt install python3-tk python3-venv"; exit 1; }
    python3 -m venv .build_linux
    VENV=".build_linux"
fi
source "$VENV/bin/activate"
pip install -q --upgrade pip
pip install -q pillow pyinstaller
pyinstaller --noconfirm --clean --onefile \
    --name HandwriteCollector \
    --distpath "$ROOT/release" \
    --workpath "$ROOT/build_linux" \
    --specpath "$ROOT/build_linux" \
    "$SRC"
deactivate 2>/dev/null || true
chmod +x release/HandwriteCollector
echo "✅ Готово: release/HandwriteCollector"

# ---------- 3) Windows .exe через Wine ----------
echo ""
echo "🍷 Собираю .exe под Windows..."
command -v wine >/dev/null 2>&1 || { echo "❌ Нет Wine: sudo apt install wine64"; exit 1; }

WPREF=".wine_win"
for w in "collect_dataset/.wine_win" ".wine_win"; do
    [ -d "$w" ] && WPREF="$w" && break
done
export WINEPREFIX="$ROOT/$WPREF"
export WINEDEBUG=-all

PYVER="3.12.7"
INST="python-${PYVER}-amd64.exe"
INST_PATH=""
for p in "collect_dataset/$INST" "$INST"; do
    [ -f "$p" ] && INST_PATH="$p" && break
done

wineboot -u >/dev/null 2>&1 || true
LOCALAPP="$(wine cmd /c 'echo %LOCALAPPDATA%' 2>/dev/null | tr -d '\r')"
PYWIN="${LOCALAPP}\\Programs\\Python\\Python312\\python.exe"
if [ -z "$LOCALAPP" ] || ! wine "$PYWIN" --version >/dev/null 2>&1; then
    if [ -z "$INST_PATH" ]; then
        echo "⬇ Скачиваю установщик Windows Python..."
        wget -q "https://www.python.org/ftp/python/${PYVER}/${INST}" \
          || curl -sO "https://www.python.org/ftp/python/${PYVER}/${INST}"
        INST_PATH="$INST"
    fi
    echo "Устанавливаю Windows Python в Wine..."
    wine "$ROOT/$INST_PATH" /quiet InstallAllUsers=0 Include_pip=1 Include_test=0 >/dev/null 2>&1 || true
    LOCALAPP="$(wine cmd /c 'echo %LOCALAPPDATA%' 2>/dev/null | tr -d '\r')"
    PYWIN="${LOCALAPP}\\Programs\\Python\\Python312\\python.exe"
fi
[ -n "$LOCALAPP" ] || { echo "Не нашёл Python внутри Wine"; exit 1; }

echo " Pillow/PyInstaller внутри Wine..."
wine "$PYWIN" -m pip install -q pillow pyinstaller

echo "_PACKAGING .exe (пара минут)..."
wine "$PYWIN" -m PyInstaller --noconfirm --clean --onefile --windowed \
    --name HandwriteCollector \
    --distpath "$ROOT/release" \
    --workpath "$ROOT/build_windows" \
    --specpath "$ROOT/build_windows" \
    "$SRC"

[ -f release/HandwriteCollector.exe ] || { echo "exe не создан"; exit 1; }
echo "✅ Готово: release/HandwriteCollector.exe"

echo ""
echo "Готово. Два файла для волонтёров:"
ls -lh release/HandwriteCollector release/HandwriteCollector.exe