#!/usr/bin/env bash
set -euo pipefail

# ---- Settings (you can override via env) ----
PROJECT="${PROJECT:-voicenotes}"
RUN_USER="${RUN_USER:-pi}"
RUN_GROUP="${RUN_GROUP:-pi}"

REPO_ROOT="$(pwd)"
SRC_DIR="$REPO_ROOT/src"                 # <— all app code here
SYSTEMD_SRC_DIR="$REPO_ROOT/systemd"     # unit files here
UDEV_RULE_SRC="$SYSTEMD_SRC_DIR/99-usb-wav.rules"

OPT_DIR="/opt/$PROJECT"
VAR_DIR="/var/lib/$PROJECT"
SYSTEMD_DIR="/etc/systemd/system"
UDEV_DIR="/etc/udev/rules.d"

MAIN_SERVICE="${PROJECT}.service"
TIMER_SERVICE="${PROJECT}.timer"

echo "[*] Installing $PROJECT"
echo "    SRC_DIR=$SRC_DIR"
echo "    OPT_DIR=$OPT_DIR"
echo "    VAR_DIR=$VAR_DIR"
echo "    RUN_USER=$RUN_USER RUN_GROUP=$RUN_GROUP"

# ---- Sanity checks ----
if [[ ! -d "$SRC_DIR" ]]; then
  echo "[-] Expected application code at $SRC_DIR but it doesn't exist." >&2
  exit 1
fi
if [[ ! -d "$SYSTEMD_SRC_DIR" ]]; then
  echo "[-] Expected systemd unit files at $SYSTEMD_SRC_DIR but it doesn't exist." >&2
  exit 1
fi

# ---- Create target dirs ----
sudo mkdir -p "$OPT_DIR" "$VAR_DIR" "$UDEV_DIR"

# ---- Copy application code (from ./src only) ----
echo "[*] Copying application code to $OPT_DIR"
# rsync preserves perms, removes stale files in target
sudo rsync -a --delete "$SRC_DIR/" "$OPT_DIR/"

# ---- Default config (src/config.yaml -> /var/lib/voicenotes/config.yaml) ----
if [[ -f "$SRC_DIR/config.yaml" && ! -f "$VAR_DIR/config.yaml" ]]; then
  echo "[*] Installing default config.yaml to $VAR_DIR"
  sudo cp "$SRC_DIR/config.yaml" "$VAR_DIR/config.yaml"
fi

# ---- Ownership for runtime dirs (optional but recommended) ----
sudo chown -R "$RUN_USER:$RUN_GROUP" "$OPT_DIR" "$VAR_DIR"

# ---- Install systemd units (must already be renamed to voicenotes*.service/.timer) ----
echo "[*] Installing systemd units from $SYSTEMD_SRC_DIR"
found_unit=false
for f in "$SYSTEMD_SRC_DIR"/*.service "$SYSTEMD_SRC_DIR"/*.timer; do
  [[ -e "$f" ]] || continue
  found_unit=true
  base="$(basename "$f")"
  sudo cp "$f" "$SYSTEMD_DIR/$base"
done
if [[ "$found_unit" = false ]]; then
  echo "[-] No .service or .timer files found in $SYSTEMD_SRC_DIR" >&2
  exit 1
fi

# ---- Install udev rule (renamed to 99-voicenotes.rules) ----
if [[ -f "$UDEV_RULE_SRC" ]]; then
  echo "[*] Installing udev rule -> $UDEV_DIR/99-${PROJECT}.rules"
  sudo cp "$UDEV_RULE_SRC" "$UDEV_DIR/99-${PROJECT}.rules"
else
  echo "[!] Skipping udev rule: $UDEV_RULE_SRC not found"
fi

# ---- Reload daemons ----
echo "[*] Reloading systemd and udev"
sudo systemctl daemon-reload

# ---- Enable & start services if present ----
if [[ -f "$SYSTEMD_DIR/$MAIN_SERVICE" ]]; then
  echo "[*] Enabling $MAIN_SERVICE"
  sudo systemctl enable --now "$MAIN_SERVICE"
else
  echo "[!] $MAIN_SERVICE not found in $SYSTEMD_DIR; skipping enable/start"
fi

if [[ -f "$SYSTEMD_DIR/$TIMER_SERVICE" ]]; then
  echo "[*] Enabling $TIMER_SERVICE"
  sudo systemctl enable --now "$TIMER_SERVICE"
else
  echo "[!] $TIMER_SERVICE not found in $SYSTEMD_DIR; skipping enable/start"
fi

echo "[✓] $PROJECT installation complete."
echo "    Web UI should be on port 8080 once ${MAIN_SERVICE} is active."
echo "    Override runtime user/group by: RUN_USER=foobar RUN_GROUP=foobar ./install.sh"