from flask import Flask, request, jsonify, render_template_string
import subprocess
import re
import os
import time

app = Flask(__name__)

# ---------------- Wi-Fi Interface Utilities ----------------
def get_wireless_interface(retries=3, delay=1):
    for _ in range(retries):
        try:
            output = subprocess.check_output(["iw", "dev"]).decode()
            match = re.search(r"Interface\s+(\w+)", output)
            if match:
                return match.group(1)
        except Exception:
            pass
        time.sleep(delay)
    return None

# ---------------- Mode Switch ----------------
def stop_softap_and_prepare_client_mode(iface):
    print("[🔁] Switching to client mode...")
    subprocess.run(["sudo", "systemctl", "stop", "hostapd"], check=False)
    subprocess.run(["sudo", "systemctl", "stop", "dnsmasq"], check=False)
    subprocess.run(["sudo", "systemctl", "disable", "hostapd"], check=False)
    subprocess.run(["sudo", "systemctl", "disable", "dnsmasq"], check=False)

    subprocess.run(["sudo", "ip", "addr", "flush", "dev", iface])
    subprocess.run(["sudo", "ip", "link", "set", iface, "down"])
    subprocess.run(["sudo", "ip", "link", "set", iface, "up"])

    subprocess.run(["sudo", "rm", "-f", "/etc/hostapd/hostapd.conf"])
    subprocess.run(["sudo", "rm", "-f", "/etc/default/hostapd"])
    subprocess.run(["sudo", "rm", "-f", "/etc/dnsmasq.d/softap.conf"])

    subprocess.run(["sudo", "systemctl", "unmask", "NetworkManager"], check=False)
    subprocess.run(["sudo", "systemctl", "enable", "NetworkManager"], check=False)
    subprocess.run(["sudo", "systemctl", "restart", "NetworkManager"], check=False)

    subprocess.run(["sudo", "systemctl", "unmask", "systemd-resolved.service"], check=False)
    subprocess.run(["sudo", "rm", "-f", "/etc/resolv.conf"])
    subprocess.run(["sudo", "ln", "-s", "/run/systemd/resolve/stub-resolv.conf", "/etc/resolv.conf"])
    subprocess.run(["sudo", "systemctl", "enable", "systemd-resolved"], check=False)
    subprocess.run(["sudo", "systemctl", "restart", "systemd-resolved"], check=False)

    print("[⏳] Waiting for interface to switch modes...")
    time.sleep(3)

def start_softap(iface):
    print("[📡] Re-enabling SoftAP...")

    subprocess.run(["sudo", "ip", "link", "set", iface, "down"])
    subprocess.run(["sudo", "ip", "addr", "flush", "dev", iface])
    subprocess.run(["sudo", "ip", "addr", "add", "192.168.4.1/24", "dev", iface])
    subprocess.run(["sudo", "ip", "link", "set", iface, "up"])

    subprocess.run(["sudo", "bash", "-c", f"cat > /etc/hostapd/hostapd.conf <<EOF\ninterface={iface}\ndriver=nl80211\nssid=JetsonAP\nhw_mode=g\nchannel=6\nauth_algs=1\nwmm_enabled=0\nEOF"])
    subprocess.run(["sudo", "bash", "-c", "echo 'DAEMON_CONF=\"/etc/hostapd/hostapd.conf\"' > /etc/default/hostapd"])

    subprocess.run(["sudo", "mkdir", "-p", "/etc/dnsmasq.d"])
    subprocess.run(["sudo", "bash", "-c", f"cat > /etc/dnsmasq.d/softap.conf <<EOF\ninterface={iface}\nbind-interfaces\nlisten-address=192.168.4.1\ndhcp-range=192.168.4.10,192.168.4.100,12h\nEOF"])

    subprocess.run(["sudo", "systemctl", "unmask", "hostapd"])
    subprocess.run(["sudo", "systemctl", "enable", "hostapd"])
    subprocess.run(["sudo", "systemctl", "enable", "dnsmasq"])

    time.sleep(2)
    subprocess.run(["sudo", "systemctl", "restart", "dnsmasq"])
    subprocess.run(["sudo", "systemctl", "restart", "hostapd"])

    print("[✅] SoftAP restarted.")
    print("[⏳] Waiting for SoftAP to stabilize...")
    time.sleep(3)

# ---------------- Wi-Fi Scan ----------------
def scan_wifi():
    iface = get_wireless_interface()
    if not iface:
        return []

    print(f"[🔍] Scanning for Wi-Fi on interface {iface}")
    try:
        output = subprocess.check_output(["sudo", "iwlist", iface, "scan"], stderr=subprocess.DEVNULL).decode()
        cells = re.split(r'Cell \d+ - Address: ', output)[1:]
        networks = []
        seen = set()
        for cell in cells:
            ssid_match = re.search(r'ESSID:"(.*?)"', cell)
            signal_match = re.search(r'Signal level=(-?\d+)', cell)
            ssid = ssid_match.group(1) if ssid_match else "<hidden>"
            signal = int(signal_match.group(1)) if signal_match else None
            if ssid and ssid not in seen and ssid != "<hidden>":
                seen.add(ssid)
                networks.append({"ssid": ssid, "signal": signal if signal else "?"})
        return networks
    except Exception as e:
        print(f"[❌] Wi-Fi scan failed: {e}")
        return []

# ---------------- Flask Routes ----------------
@app.route("/wifi")
def wifi_page():
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
  <title>Jetson Wi-Fi Connect</title>
  <script>
    async function loadWifiList() {
      try {
        const res = await fetch("/wifi-scan");
        const list = await res.json();
        const container = document.getElementById("wifi-list");
        container.innerHTML = "";
        list.forEach(net => {
          const btn = document.createElement("button");
          btn.innerText = net.ssid + " (" + net.signal + " dBm)";
          btn.onclick = () => showConnectForm(net.ssid);
          container.appendChild(btn);
          container.appendChild(document.createElement("br"));
        });
      } catch (err) {
        console.warn("⚠️ Lost connection. Retrying in 3s...");
        setTimeout(loadWifiList, 3000);
      }
    }

    function showConnectForm(ssid) {
      document.getElementById("selected-ssid").value = ssid;
      document.getElementById("connect-form").style.display = "block";
    }

    async function connectWifi(event) {
      event.preventDefault();
      const ssid = document.getElementById("selected-ssid").value;
      const password = document.getElementById("password").value;
      const res = await fetch("/connect", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ssid, password })
      });
      const data = await res.json();
      alert(data.message);
    }

    window.onload = loadWifiList;
    setInterval(loadWifiList, 10000);  // Refresh list every 10 seconds
  </script>
</head>
<body>
  <h2>Nearby Wi-Fi Networks</h2>
  <div id="wifi-list">Loading...</div>

  <div id="connect-form" style="display:none;">
    <h3>Connect to selected network</h3>
    <form onsubmit="connectWifi(event)">
      <input type="hidden" id="selected-ssid" name="ssid" />
      <label>Password: </label><input type="password" id="password" required />
      <button type="submit">Connect</button>
    </form>
  </div>
</body>
</html>
""")

@app.route("/wifi-scan")
def wifi_scan():
    return jsonify(scan_wifi())

@app.route("/connect", methods=["POST"])
def connect_wifi():
    data = request.json
    ssid = data.get("ssid")
    password = data.get("password")
    iface = get_wireless_interface()

    if not iface:
        return jsonify({"status": "error", "message": "❌ No wireless interface found."})

    try:
        stop_softap_and_prepare_client_mode(iface)

        subprocess.call(["nmcli", "connection", "delete", ssid], stderr=subprocess.DEVNULL)
        subprocess.call(["nmcli", "connection", "delete", "temp-connection"], stderr=subprocess.DEVNULL)

        result = subprocess.run([
            "nmcli", "dev", "wifi", "connect", ssid,
            "password", password,
            "ifname", iface,
            "name", "temp-connection"
        ], capture_output=True, text=True, timeout=20)

        if result.returncode != 0:
            print(f"[❌] nmcli error: {result.stderr}")
            start_softap(iface)
            return jsonify({
                "status": "error",
                "message": f"❌ Failed to connect to {ssid}. SoftAP restored."
            })

        for _ in range(10):
            ip_output = subprocess.check_output([
                "nmcli", "-t", "-f", "IP4.ADDRESS", "device", "show", iface
            ]).decode()
            if any(line.startswith(("192.", "10.", "172.")) for line in ip_output.splitlines()):
                return jsonify({
                    "status": "success",
                    "message": f"✅ Connected to {ssid} successfully!"
                })
            time.sleep(1)

        print("[⚠️] No IP assigned after connection.")
        start_softap(iface)
        return jsonify({
            "status": "error",
            "message": f"⚠️ Connected to {ssid} but no IP assigned. SoftAP restored."
        })

    except Exception as e:
        start_softap(iface)
        return jsonify({
            "status": "error",
            "message": f"❌ Exception occurred: {str(e)}. SoftAP restored."
        })

# ---------------- Run ----------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
