from flask import Flask, request, jsonify, render_template_string
import subprocess
import re

app = Flask(__name__)

def scan_wifi():
    try:
        output = subprocess.check_output(["sudo", "iwlist", "wlan0", "scan"], stderr=subprocess.DEVNULL).decode()
        cells = re.split(r'Cell \d+ - Address: ', output)[1:]
        networks = []

        for cell in cells:
            ssid_match = re.search(r'ESSID:"(.*?)"', cell)
            signal_match = re.search(r'Signal level=(-?\d+)', cell)

            ssid = ssid_match.group(1) if ssid_match else "<hidden>"
            signal = int(signal_match.group(1)) if signal_match else None

            if ssid and ssid != "<hidden>":
                networks.append({"ssid": ssid, "signal": signal})

        return networks
    except Exception as e:
        return []

def stop_softap():
    subprocess.call(["sudo", "systemctl", "stop", "hostapd"])
    subprocess.call(["sudo", "systemctl", "stop", "dnsmasq"])
    subprocess.call(["sudo", "systemctl", "disable", "hostapd"])
    subprocess.call(["sudo", "systemctl", "disable", "dnsmasq"])
    subprocess.call(["sudo", "ip", "addr", "flush", "dev", "wlan0"])
    subprocess.call(["sudo", "ip", "link", "set", "wlan0", "down"])
    subprocess.call(["sudo", "ip", "link", "set", "wlan0", "up"])

@app.route("/wifi")
def wifi_page():
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
  <title>Jetson Wi-Fi Connect</title>
  <script>
    async function loadWifiList() {
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

    try:
        # Start NetworkManager (required for nmcli)
        subprocess.call(["sudo", "systemctl", "start", "NetworkManager"])
        subprocess.call(["sudo", "systemctl", "enable", "NetworkManager"])

        # Connect using nmcli
        cmd = ["nmcli", "dev", "wifi", "connect", ssid]
        if password:
            cmd += ["password", password]
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT)

        # ✅ Only if successful, stop SoftAP
        stop_softap()

        return jsonify({"status": "success", "message": f"✅ Connected to {ssid}. SoftAP is now off."})
    except subprocess.CalledProcessError as e:
        return jsonify({"status": "error", "message": f"❌ Failed to connect to {ssid}: {e.output.decode()}"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

