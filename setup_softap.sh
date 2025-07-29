#!/bin/bash
set -e

echo "[1] Installing required packages..."
sudo apt update
sudo apt install -y hostapd dnsmasq net-tools

echo "[2] Stopping NetworkManager (optional)..."
sudo systemctl stop NetworkManager || true

echo "[3] Bringing down wlan0 and assigning static IP..."
sudo ip link set wlan0 down
sudo ip addr flush dev wlan0
sudo ip addr add 192.168.4.1/24 dev wlan0
sudo ip link set wlan0 up

echo "[4] Creating hostapd configuration..."
sudo tee /etc/hostapd/hostapd.conf > /dev/null <<EOF
interface=wlan0
driver=nl80211
ssid=JetsonAP
hw_mode=g
channel=6
auth_algs=1
wmm_enabled=0
EOF

echo 'DAEMON_CONF="/etc/hostapd/hostapd.conf"' | sudo tee /etc/default/hostapd

echo "[5] Creating dnsmasq configuration..."
sudo mv /etc/dnsmasq.conf /etc/dnsmasq.conf.orig 2>/dev/null || true
sudo tee /etc/dnsmasq.conf > /dev/null <<EOF
interface=wlan0
dhcp-range=192.168.4.10,192.168.4.50,255.255.255.0,24h
EOF

echo "[6] Enabling and restarting services..."
sudo systemctl unmask hostapd
sudo systemctl enable hostapd
sudo systemctl enable dnsmasq
sudo systemctl restart hostapd
sudo systemctl restart dnsmasq

echo ""
echo "[✅] SoftAP successfully configured using hostapd (no NetworkManager, no nmcli)"
echo "👉 SSID: JetsonAP (Open network)"
echo "📱 Connect from your smartphone and access: http://192.168.4.1:5000"

