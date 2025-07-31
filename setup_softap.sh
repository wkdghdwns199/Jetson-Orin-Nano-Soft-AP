#!/bin/bash
set -e

echo "[1] Detecting Wi-Fi interface..."
WIFI_IFACE=$(iw dev | awk '$1=="Interface"{print $2}' | head -n 1)

if [ -z "$WIFI_IFACE" ]; then
  echo "❌ No Wi-Fi interface found. Exiting."
  exit 1
fi
echo "✅ Detected Wi-Fi interface: $WIFI_IFACE"

echo "[2] Installing required packages..."
# sudo apt update
# sudo apt install -y hostapd dnsmasq

echo "[3] Stopping services..."
sudo systemctl stop hostapd || true
sudo systemctl stop dnsmasq || true
sudo systemctl stop NetworkManager || true

echo "[4] Configuring Wi-Fi interface..."
sudo ip link set "$WIFI_IFACE" down
sudo ip addr flush dev "$WIFI_IFACE"
sudo ip addr add 192.168.4.1/24 dev "$WIFI_IFACE"
sudo ip link set "$WIFI_IFACE" up

echo "[5] Writing hostapd config..."
sudo bash -c "cat > /etc/hostapd/hostapd.conf" <<EOF
interface=$WIFI_IFACE
driver=nl80211
ssid=JetsonAP
hw_mode=g
channel=6
auth_algs=1
wmm_enabled=0
EOF

echo 'DAEMON_CONF="/etc/hostapd/hostapd.conf"' | sudo tee /etc/default/hostapd

echo "[6] Writing dnsmasq config..."
sudo mkdir -p /etc/dnsmasq.d
sudo bash -c "cat > /etc/dnsmasq.d/softap.conf" <<EOF
interface=$WIFI_IFACE
bind-interfaces
listen-address=192.168.4.1
dhcp-range=192.168.4.10,192.168.4.100,12h
EOF

echo "[7] Enabling services..."
sudo systemctl unmask hostapd
sudo systemctl enable hostapd
sudo systemctl enable dnsmasq

echo "[8] Waiting for IP to settle..."
sleep 2

echo "[9] Starting services..."
sudo systemctl restart dnsmasq
sudo systemctl restart hostapd

echo ""
echo "✅ SoftAP setup complete!"
echo "📶 SSID: JetsonAP"
echo "🖥️  Interface: $WIFI_IFACE"
echo "🌐 Access Point IP: http://192.168.4.1"

