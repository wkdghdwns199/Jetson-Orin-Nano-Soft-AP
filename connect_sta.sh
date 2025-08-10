#!/bin/bash

# === CONFIGURATION ===
STA_INTERFACE="wlP1p1s0"
SSID="$1"
PASSWORD="$2"

if [[ -z "$SSID" || -z "$PASSWORD" ]]; then
    echo "Usage: $0 <SSID> <PASSWORD>"
    exit 1
fi

echo "[🔍] Connecting to SSID: $SSID using $STA_INTERFACE..."

# Disconnect and remove old connection (if any)
nmcli con delete "$SSID" 2>/dev/null

# Try to connect
nmcli device wifi connect "$SSID" password "$PASSWORD" ifname "$STA_INTERFACE"

if [[ $? -eq 0 ]]; then
    echo "[✅] Successfully connected to $SSID"
    exit 0
else
    echo "[❌] Failed to connect. Check password or SSID."
    exit 1
fi

