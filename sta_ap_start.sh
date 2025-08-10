#!/bin/bash
set -e

# CONFIG
STA_IF="wlP1p1s0"
AP_IF="wlxa047d7115a68"
AP_IP="192.168.50.1"

echo "[1/6] Connecting STA ($STA_IF) to router..."
nmcli dev wifi connect "YourRouterSSID" password "YourRouterPassword" ifname "$STA_IF" || true

echo "[2/6] Setting static IP on AP interface ($AP_IF)..."
nmcli dev set "$AP_IF" managed no || true
ip link set "$AP_IF" down
ip addr flush dev "$AP_IF"
ip addr add "$AP_IP/24" dev "$AP_IF"
ip link set "$AP_IF" up

echo "[3/6] Enabling IP forwarding..."
sysctl -w net.ipv4.ip_forward=1

echo "[4/6] Adding NAT rules..."
iptables -t nat -F
iptables -F
iptables -t nat -A POSTROUTING -o "$STA_IF" -j MASQUERADE
iptables -A FORWARD -i "$STA_IF" -o "$AP_IF" -m state --state RELATED,ESTABLISHED -j ACCEPT
iptables -A FORWARD -i "$AP_IF" -o "$STA_IF" -j ACCEPT

echo "[5/6] Saving NAT rules..."
netfilter-persistent save

echo "[6/6] Starting dnsmasq + hostapd..."
systemctl restart dnsmasq
systemctl restart hostapd

echo "✅ STA+AP mode is now active!"

