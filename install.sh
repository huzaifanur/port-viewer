#!/bin/sh
set -eu

PORT_VIEWER_SOURCE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PORT_VIEWER_DATA=${XDG_DATA_HOME:-"$HOME/.local/share"}
PORT_VIEWER_BIN=${XDG_BIN_HOME:-"$HOME/.local/bin"}
PORT_VIEWER_APP_DIR="$PORT_VIEWER_DATA/port-viewer"

mkdir -p "$PORT_VIEWER_APP_DIR/port_viewer" "$PORT_VIEWER_BIN"
cp -R "$PORT_VIEWER_SOURCE/port_viewer/." "$PORT_VIEWER_APP_DIR/port_viewer/"
install -Dm755 "$PORT_VIEWER_SOURCE/bin/port-viewer" "$PORT_VIEWER_BIN/port-viewer"
mkdir -p "$PORT_VIEWER_DATA/applications"
desktop-file-install \
  --dir="$PORT_VIEWER_DATA/applications" \
  --set-key=Exec \
  --set-value="$PORT_VIEWER_BIN/port-viewer" \
  "$PORT_VIEWER_SOURCE/io.github.portviewer.PortViewer.desktop"
install -Dm644 \
  "$PORT_VIEWER_SOURCE/port_viewer/icons/io.github.portviewer.PortViewer.svg" \
  "$PORT_VIEWER_DATA/icons/hicolor/scalable/apps/io.github.portviewer.PortViewer.svg"

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$PORT_VIEWER_DATA/applications"
fi

printf 'Port Viewer installed. Launch it from your application menu.\n'
