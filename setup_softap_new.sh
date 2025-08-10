#!/bin/bash
set -euo pipefail

AP_IFACE="wlxa047d7115a68"
AP_IP="192.168.4.1"
AP_NET="$AP_IP/24"
SSID="${SSID:-JetsonAP}"
CHANNEL="${CHANNEL:-6}"        # try 1 or 11 if 6 is crowded
HW_MODE="${HW_MODE:-g}"        # g=2.4GHz, a=5GHz
COUNTRY="${COUNTRY:-KR}"       # <-- set your country code
AP_PSK="${AP_PSK:-12345678}"   # <-- hotspot password (8–63 chars)

CLIENT_IFACE="$(iw dev | awk '$1=="Interface"{print $2}' | grep -vx "$AP_IFACE" | head -n1 || true)"
ENABLE_NAT=1

echo "[1] Checking interfaces…"
if ! iw dev | awk '$1=="Interface"{print $2}' | grep -qx "$AP_IFACE"; then
  echo "❌ AP interface $AP_IFACE not found"
  exit 1
fi
if [ -z "$CLIENT_IFACE" ]; then
  echo "❌ No client interface found"
  exit 1
fi
echo "   AP_IFACE=$AP_IFACE, CLIENT_IFACE=$CLIENT_IFACE"

echo "[1.1] Set regulatory domain to ${COUNTRY}…"
sudo iw reg set "$COUNTRY" || true

echo "[2] Stop services that may interfere…"
sudo systemctl stop hostapd || true
sudo systemctl stop dnsmasq || true
# Make sure NM doesn't touch AP iface, but does manage the client
if command -v nmcli >/dev/null; then
  sudo nmcli dev set "$AP_IFACE" managed no || true
  sudo nmcli dev set "$CLIENT_IFACE" managed yes || true
fi
# Kill any wpa_supplicant instance bound to AP iface
sudo systemctl stop "wpa_supplicant@${AP_IFACE}.service" 2>/dev/null || true
sudo pkill -f "wpa_supplicant.*${AP_IFACE}" 2>/dev/null || true

echo "[3] Assign IP to AP interface…"
sudo ip link set "$AP_IFACE" down || true
sudo ip addr flush dev "$AP_IFACE"
sudo ip addr add "$AP_NET" dev "$AP_IFACE"
sudo ip link set "$AP_IFACE" up

echo "[4] Write hostapd config (compat-focused)…"
sudo mkdir -p /etc/hostapd
sudo tee /etc/hostapd/hostapd.conf >/dev/null <<EOF
interface=$AP_IFACE
driver=nl80211
country_code=$COUNTRY
ieee80211d=1
ssid=$SSID
hw_mode=$HW_MODE
channel=$CHANNEL
auth_algs=1

# Max compatibility: some chipsets/phones fail with WMM/HT on ad-hoc USB adapters
wmm_enabled=0
ieee80211n=0

# WPA2-PSK only, AES-CCMP only (no WPA1/TKIP)
wpa=2
wpa_key_mgmt=WPA-PSK
rsn_pairwise=CCMP
wpa_passphrase=$AP_PSK

ignore_broadcast_ssid=0
EOF
echo 'DAEMON_CONF="/etc/hostapd/hostapd.conf"' | sudo tee /etc/default/hostapd >/dev/null

echo "[5] Write dnsmasq config…"
sudo mkdir -p /etc/dnsmasq.d
sudo tee /etc/dnsmasq.d/softap.conf >/dev/null <<EOF
interface=$AP_IFACE
bind-interfaces
listen-address=$AP_IP
dhcp-range=192.168.4.10,192.168.4.100,12h
domain-needed
bogus-priv
EOF

echo "[6] Enable IPv4 forwarding…"
echo "net.ipv4.ip_forward=1" | sudo tee /etc/sysctl.d/99-softap-ipforward.conf >/dev/null
sudo sysctl --system >/dev/null || true

if [ "$ENABLE_NAT" = "1" ]; then
  echo "[7] Configure NAT…"
  sudo modprobe iptable_nat nf_nat nf_conntrack || true
  sudo iptables -t nat -C POSTROUTING -o "$CLIENT_IFACE" -j MASQUERADE 2>/dev/null || \
    sudo iptables -t nat -A POSTROUTING -o "$CLIENT_IFACE" -j MASQUERADE
  sudo iptables -C FORWARD -i "$AP_IFACE" -o "$CLIENT_IFACE" -j ACCEPT 2>/dev/null || \
    sudo iptables -A FORWARD -i "$AP_IFACE" -o "$CLIENT_IFACE" -j ACCEPT
  sudo iptables -C FORWARD -i "$CLIENT_IFACE" -o "$AP_IFACE" -m state --state RELATED,ESTABLISHED -j ACCEPT 2>/dev/null || \
    sudo iptables -A FORWARD -i "$CLIENT_IFACE" -o "$AP_IFACE" -m state --state RELATED,ESTABLISHED -j ACCEPT
fi

echo "[8] Start services…"
sudo systemctl unmask hostapd || true
sudo systemctl enable hostapd dnsmasq
sudo systemctl restart dnsmasq
sudo systemctl restart hostapd

echo "[9] AP status…"
ip addr show "$AP_IFACE"
sudo systemctl status hostapd --no-pager || true
sudo journalctl -u hostapd --since "1 minute ago" | tail -n 40 || true

echo ""
echo "✅ SoftAP broadcasting: $SSID on $AP_IFACE ($AP_IP)"
echo "🔑 Password: $AP_PSK"
echo "ℹ️  If association still fails, try: CHANNEL=1 or CHANNEL=11; or re-enable WMM/11n later."

