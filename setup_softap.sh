#!/bin/bash
set -e

# Set your hotspot interface here
AP_IFACE="wlxa047d7115a68"    # <-- Replace with your real AP interface
AP_IP="192.168.4.1"
SSID="JetsonAP"
CHANNEL=6
AP_PSK="12345678"             # <-- Change to your desired password

echo "[1] Using fixed Wi-Fi interface: $AP_IFACE"

echo "[2] Installing required packages..."
# sudo apt update
# sudo apt install -y hostapd dnsmasq

echo "[3] Stopping services..."
sudo systemctl stop hostapd || true
sudo systemctl stop dnsmasq || true
sudo systemctl stop NetworkManager || true
sudo pkill -f "wpa_supplicant.*${AP_IFACE}" 2>/dev/null || true

echo "[4] Configuring Wi-Fi interface..."
sudo ip link set "$AP_IFACE" down
sudo ip addr flush dev "$AP_IFACE"
sudo ip addr add "$AP_IP/24" dev "$AP_IFACE"
sudo ip link set "$AP_IFACE" up

echo "[5] Writing hostapd config..."
sudo mkdir -p /etc/hostapd
sudo bash -c "cat > /etc/hostapd/hostapd.conf" <<EOF
interface=$AP_IFACE
driver=nl80211
ssid=$SSID
hw_mode=g
channel=$CHANNEL
auth_algs=1
wmm_enabled=0

# WPA2 security
wpa=2
wpa_passphrase=$AP_PSK
wpa_key_mgmt=WPA-PSK
rsn_pairwise=CCMP
EOF

echo 'DAEMON_CONF="/etc/hostapd/hostapd.conf"' | sudo tee /etc/default/hostapd >/dev/null

echo "[6] Writing dnsmasq config..."
sudo mkdir -p /etc/dnsmasq.d
sudo bash -c "cat > /etc/dnsmasq.d/softap.conf" <<EOF
interface=$AP_IFACE
bind-interfaces
listen-address=$AP_IP
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
echo "📶 SSID: $SSID"
echo "🔑 Password: $AP_PSK"
echo "🖥️  Interface: $AP_IFACE"
echo "🌐 Access Point IP: http://$AP_IP"

