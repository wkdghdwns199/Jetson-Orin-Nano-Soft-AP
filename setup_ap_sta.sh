#!/usr/bin/env bash
set -euo pipefail

# ================== CONFIG (edit these 4 as needed) ==================
AP_IF="wlxa047d7115a68"       # SoftAP interface
STA_IF="wlP1p1s0"             # Client interface
ROUTER_SSID="YourRouterSSID"  # <- change
ROUTER_PASS="YourRouterPassword"  # <- change

# AP network settings
AP_IP="192.168.4.1/24"
AP_GW="192.168.4.1"
AP_DHCP_START="192.168.4.10"
AP_DHCP_END="192.168.4.100"
AP_SSID="JetsonAP"
AP_PASS="jetsonpass123"       # min 8 chars
AP_CH=6
REG="KR"                      # country code

# ================== Helpers ==================
log(){ echo -e "\n[+] $*"; }
warn(){ echo -e "\n[!] $*"; }
die(){ echo -e "\n[✗] $*" >&2; exit 1; }

require_cmd(){ command -v "$1" >/dev/null 2>&1 || die "Missing command: $1"; }

# ================== Pre-flight ==================
require_cmd nmcli
require_cmd ip
require_cmd sed
require_cmd tee

if ! ip link show "$AP_IF" >/dev/null 2>&1; then
  die "AP interface '$AP_IF' not found. Check 'ip link'."
fi
if ! ip link show "$STA_IF" >/dev/null 2>&1; then
  die "Client interface '$STA_IF' not found. Check 'ip link'."
fi

# ================== Packages ==================
log "Installing packages (hostapd, dnsmasq, netfilter-persistent)"
export DEBIAN_FRONTEND=noninteractive
apt update
apt install -y hostapd dnsmasq iptables-persistent netfilter-persistent || true

# If install scripts failed earlier, fix and reconfigure later once config is in place
apt --fix-broken install -y || true

# ================== NetworkManager roles ==================
log "Let NetworkManager manage ONLY the client (${STA_IF})"
nmcli device set "$AP_IF" managed no || true
nmcli device set "$STA_IF" managed yes || true

# Some images disable NM-ifupdown integration; ensure it's on
mkdir -p /etc/NetworkManager/conf.d
cat >/etc/NetworkManager/conf.d/10-wifi-managed.conf <<EOF
[device]
wifi.scan-rand-mac-address=no
[ifupdown]
managed=true
EOF
systemctl restart NetworkManager || true

# ================== Bring up AP interface with static IP ==================
log "Configuring ${AP_IF} with static IP ${AP_IP}"
ip link set "$AP_IF" down || true
ip addr flush dev "$AP_IF" || true
ip addr add "$AP_IP" dev "$AP_IF"
ip link set "$AP_IF" up

# ================== Regulatory domain ==================
log "Setting regulatory domain: ${REG}"
iw reg set "$REG" || true

# ================== hostapd ==================
log "Writing /etc/hostapd/hostapd.conf"
mkdir -p /etc/hostapd
cat >/etc/hostapd/hostapd.conf <<EOF
interface=$AP_IF
driver=nl80211
ssid=$AP_SSID
country_code=$REG
hw_mode=g
channel=$AP_CH
ieee80211n=1
wmm_enabled=1
auth_algs=1
wpa=2
wpa_passphrase=$AP_PASS
wpa_key_mgmt=WPA-PSK
rsn_pairwise=CCMP
EOF

# Ensure service knows the config path
sed -i 's|^#\?DAEMON_CONF=.*|DAEMON_CONF="/etc/hostapd/hostapd.conf"|' /etc/default/hostapd || true

# hostapd can be masked on some images
systemctl unmask hostapd || true
systemctl enable hostapd || true

# ================== dnsmasq ==================
log "Configuring dnsmasq (drop-in file)"
mkdir -p /etc/dnsmasq.d

# Ensure main file references the drop-in dir only (avoid old bad options)
echo -e "# managed by setup_ap_sta.sh\nconf-dir=/etc/dnsmasq.d,*.conf" > /etc/dnsmasq.conf

cat >/etc/dnsmasq.d/jetson-ap.conf <<EOF
interface=$AP_IF
bind-interfaces
domain-needed
bogus-priv
dhcp-range=$AP_DHCP_START,$AP_DHCP_END,12h
dhcp-option=3,$AP_GW
dhcp-option=6,1.1.1.1,8.8.8.8
EOF

systemctl enable dnsmasq || true

# ================== NAT (AP -> Client internet) ==================
log "Enabling IPv4 forwarding + NAT to ${STA_IF}"
sysctl -w net.ipv4.ip_forward=1 >/dev/null
grep -q '^net.ipv4.ip_forward=1' /etc/sysctl.conf || echo 'net.ipv4.ip_forward=1' >> /etc/sysctl.conf

# Add MASQUERADE if not present
if ! iptables -t nat -C POSTROUTING -o "$STA_IF" -j MASQUERADE 2>/dev/null; then
  iptables -t nat -A POSTROUTING -o "$STA_IF" -j MASQUERADE
fi

# Persist iptables
netfilter-persistent save || true

# ================== Start services ==================
log "Starting hostapd + dnsmasq"
systemctl restart hostapd
systemctl restart dnsmasq

# If hostapd had failed previously during dpkg, finish config now
log "Finalizing dpkg configuration if needed"
dpkg --configure -a || true

# ================== Connect client to router ==================
log "Connecting client ${STA_IF} to ${ROUTER_SSID}"
nmcli dev set "$STA_IF" managed yes || true
nmcli radio wifi on || true
nmcli dev disconnect "$STA_IF" || true
nmcli dev wifi connect "$ROUTER_SSID" password "$ROUTER_PASS" ifname "$STA_IF" || true

# ================== Summary & sanity checks ==================
log "AP status:"
ip addr show "$AP_IF" | sed 's/^/  /'
systemctl --no-pager --full status hostapd | sed -n '1,10p' || true
systemctl --no-pager --full status dnsmasq | sed -n '1,10p' || true

log "Client status on ${STA_IF}:"
nmcli -f GENERAL,IP4 dev show "$STA_IF" | sed 's/^/  /' || true

echo
echo "=========== DONE ==========="
echo "SoftAP:  SSID=${AP_SSID}, PASS=${AP_PASS}, IF=${AP_IF}, IP=${AP_GW}"
echo "Client:  IF=${STA_IF} (managed by NetworkManager)"
echo "Phone:   Connect to ${AP_SSID} then SSH to ${AP_GW}"
echo "==============================================="

