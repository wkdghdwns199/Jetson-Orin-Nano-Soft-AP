#!/bin/bash
set -e

echo "[1] Installing required packages..."
sudo apt update
sudo apt install -y hostapd dnsmasq net-tools wireless-tools

echo "[2] Detecting wireless interface..."
# Use iw dev to detect the wireless interface
WIFI_IFACE=$(iw dev | awk '$1=="Interface"{print $2}' | head -n 1)

if [ -z "$WIFI_IFACE" ]; then
  echo "❌ No wireless interface found. Please check your Wi-Fi hardware."
  exit 1
fi

echo "✅ Wireless interface detected: $WIFI_IFACE"

echo "[3] Stopping NetworkManager (optional)..."
sudo systemctl stop NetworkManager || true

echo "[4] Bringing down $WIFI_IFACE and assigning static IP..."
sudo ip link set "$WIFI_IFACE" down
sudo ip addr flush dev "$WIFI_IFACE"
sudo ip addr add 192.168.4.1/24 dev "$WIFI_IFACE"
sudo ip link set "$WIFI_IFACE" up

echo "[5] Creating hostapd configuration..."
sudo tee /etc/hostapd/hostapd.conf > /dev/null <<EOF
interface=$WIFI_IFACE
driver=nl80211
ssid=JetsonAP
hw_mode=g
channel=6
auth_algs=1
wmm_enabled=0
EOF

echo 'DAEMON_CONF="/etc/hostapd/hostapd.conf"' | sudo tee /etc/default/hostapd

echo "[6] Creating dnsmasq configuration..."
sudo mv /etc/dnsmasq.conf /etc/dnsmasq.conf.orig 2>/dev/null || true
sudo tee /etc/dnsmasq.conf > /dev/null <<EOF
interface=$WIFI_IFACE
dhcp-range=192.168.4.10,192.168.4.50,255.255.255.0,24h
EOF

echo "[7] Enabling and restarting services..."
sudo systemctl unmask hostapd
sudo systemctl enable hostapd
sudo systemctl enable dnsmasq
sudo systemctl restart hostapd
sudo systemctl restart dnsmasq

echo ""
echo "[✅] SoftAP successfully configured using interface: $WIFI_IFACE"
echo "👉 SSID: JetsonAP (Open network)"
echo "📱 Connect from your smartphone and access: http://192.168.4.1:5000"

