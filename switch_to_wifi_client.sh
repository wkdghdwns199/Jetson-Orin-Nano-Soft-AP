#!/bin/bash
set -e

echo "[1] Stopping SoftAP services (hostapd, dnsmasq)..."
sudo systemctl stop hostapd || true
sudo systemctl stop dnsmasq || true
sudo systemctl disable hostapd || true
sudo systemctl disable dnsmasq || true

echo "[2] Cleaning up wlan0 interface..."
sudo ip addr flush dev wlan0
sudo ip link set wlan0 down
sudo ip link set wlan0 up

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
nmcli dev wifi list

echo ""
echo "[✅] Jetson is now back in Wi-Fi client mode."
echo "👉 Use the following command to connect to a Wi-Fi network:"
echo ""
echo "   nmcli dev wifi connect \"<SSID>\" password \"<PASSWORD>\""
echo ""
echo "📶 Example:"
echo "   nmcli dev wifi connect \"MyHomeWiFi\" password \"12345678\""

