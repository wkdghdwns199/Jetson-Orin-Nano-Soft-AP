#!/bin/bash

# Usage: ./wifi_check.sh <SSID> <PASSWORD> <INTERFACE>
# Example: ./wifi_check.sh MyWiFi mypassword wlan0

SSID="$1"
PASSWORD="$2"
IFACE="$3"

if [ -z "$SSID" ] || [ -z "$PASSWORD" ] || [ -z "$IFACE" ]; then
    echo "Usage: $0 <SSID> <PASSWORD> <INTERFACE>"
    exit 1
fi

TMP_CONF="/tmp/wpa_test.conf"

# Generate temporary wpa_supplicant config
cat > "$TMP_CONF" <<EOF
ctrl_interface=/var/run/wpa_supplicant
network={
    ssid="$SSID"
    psk="$PASSWORD"
    key_mgmt=WPA-PSK
}
EOF

# Bring the interface up
sudo ip link set "$IFACE" up

# Try connecting
echo "Testing connection to $SSID..."
sudo timeout 10s wpa_supplicant -i "$IFACE" -c "$TMP_CONF" -d > /tmp/wifi_check.log 2>&1

if grep -q "WPA: Key negotiation completed" /tmp/wifi_check.log; then
    echo "PASS: Password is correct."
else
    echo "FAIL: Password is incorrect."
fi

# Kill any running wpa_supplicant process on this interface
sudo pkill -f "wpa_supplicant.*$IFACE" 2>/dev/null

