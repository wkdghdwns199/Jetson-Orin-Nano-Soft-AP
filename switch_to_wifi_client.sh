#!/bin/bash
set -e

# Step 0: Detect wireless interface
WIFI_IFACE=$(iw dev | awk '$1=="Interface"{print $2}' | head -n 1)

if [ -z "$WIFI_IFACE" ]; then
  echo "❌ No wireless interface found. Aborting."
  exit 1
fi

echo "[🛰️ ] Detected wireless interface: $WIFI_IFACE"

echo "[1] Stopping SoftAP services (hostapd, dnsmasq)..."
sudo systemctl stop hostapd || true
sudo systemctl stop dnsmasq || true
sudo systemctl disable hostapd || true
sudo systemctl disable dnsmasq || true

echo "[2] Cleaning up $WIFI_IFACE interface..."
sudo ip addr flush dev "$WIFI_IFACE"
sudo ip link set "$WIFI_IFACE" down
sudo ip link set "$WIFI_IFACE" up

echo "[3] Restoring original dnsmasq config (if exists)..."
[ -f /etc/dnsmasq.conf.orig ] && sudo mv /etc/dnsmasq.conf.orig /etc/dnsmasq.conf

echo "[4] Removing hostapd config files..."
sudo rm -f /etc/hostapd/hostapd.conf
sudo rm -f /etc/default/hostapd

echo "[5] Restarting NetworkManager..."
sudo systemctl unmask NetworkManager || true
sudo systemctl enable NetworkManager
sudo systemctl restart NetworkManager

echo "[6] Scanning available Wi-Fi networks..."
nmcli dev wifi list ifname "$WIFI_IFACE"

echo ""
echo "[✅] Jetson is now back in Wi-Fi client mode using $WIFI_IFACE."
echo "👉 Use the following command to connect to a Wi-Fi network:"
echo ""
echo "   nmcli dev wifi connect \"<SSID>\" password \"<PASSWORD>\" ifname \"$WIFI_IFACE\""
echo ""
echo "📶 Example:"
echo "   nmcli dev wifi connect \"MyHomeWiFi\" password \"12345678\" ifname \"$WIFI_IFACE\""

