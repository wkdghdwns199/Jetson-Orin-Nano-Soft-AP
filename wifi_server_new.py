from flask import Flask, request, jsonify, render_template_string, abort
import subprocess
import shlex
import re
import time
import ipaddress

# ====== CONFIG: update if your interfaces/subnet differ ======
AP_IF = "wlxa047d7115a68"        # SoftAP interface (hostapd/dnsmasq running)
STA_IF = "wlP1p1s0"              # Wi-Fi client interface (NetworkManager)
AP_IP = "192.168.4.1"
AP_SUBNET = ipaddress.ip_network("192.168.4.0/24")
# =============================================================

app = Flask(__name__)

# ---------------- Helpers ----------------
def run(cmd, timeout=15):
    """Run shell command, return (code, stdout, stderr)."""
    if isinstance(cmd, str):
        cmd = shlex.split(cmd)
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return p.returncode, p.stdout.strip(), p.stderr.strip()

def ensure_roles():
    """Make sure AP iface is unmanaged by NM, STA iface is managed."""
    run(["nmcli", "device", "set", AP_IF, "managed", "no"])
    run(["nmcli", "device", "set", STA_IF, "managed", "yes"])
    # Keep AP IP (AP service should already do this)
    run(["ip", "addr", "add", f"{AP_IP}/24", "dev", AP_IF])
    run(["ip", "link", "set", AP_IF, "up"])

def client_has_private_ip():
    """Check if STA_IF has a private IPv4 address."""
    code, out, _ = run(["nmcli", "-t", "-f", "IP4.ADDRESS", "device", "show", STA_IF])
    if code != 0:
        return False
    for line in out.splitlines():
        if not line:
            continue
        # line format: IP4.ADDRESS:192.168.1.23/24
        ip = line.split(":")[-1].split("/")[0]
        try:
            ipaddr = ipaddress.ip_address(ip)
            if ipaddr.is_private:
                return True
        except ValueError:
            pass
    return False

def only_from_softap():
    """Allow access only when the caller is in the AP subnet."""
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    try:
        if ipaddress.ip_address(ip) in AP_SUBNET:
            return
    except Exception:
        pass
    abort(403, "This page is only available from the SoftAP network")

@app.before_request
def _gate():
    # Allow only SoftAP clients (and localhost for debugging on the device)
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    if ip not in ("127.0.0.1", "::1"):
        only_from_softap()

# ---------------- Wi-Fi Scan (STA_IF) ----------------
def scan_wifi():
    # make sure roles are correct; AP keeps running; STA scans
    ensure_roles()

    # Ask NM to rescan and list (more reliable than iwlist parsing)
    run(["nmcli", "dev", "set", STA_IF, "managed", "yes"])
    run(["nmcli", "radio", "wifi", "on"])
    run(["nmcli", "device", "wifi", "rescan", "ifname", STA_IF])

    code, out, err = run([
        "nmcli",
        "-f", "SSID,SIGNAL,SECURITY",
        "device", "wifi", "list",
        "ifname", STA_IF
    ], timeout=20)

    if code != 0:
        print(f"[scan] nmcli error: {err}")
        return []

    # Parse nmcli table
    lines = [l for l in out.splitlines() if l.strip()]
    # Drop header if present
    if lines and "SSID" in lines[0]:
        lines = lines[1:]

    networks = []
    seen = set()
    for line in lines:
        # Columns are space-aligned; safer to split by 2+ spaces
        parts = re.split(r"\s{2,}", line.strip())
        if not parts:
            continue
        ssid = parts[0].strip()
        signal = parts[1].strip() if len(parts) > 1 else "?"
        security = parts[2].strip() if len(parts) > 2 else ""
        if ssid and ssid != "--" and ssid not in seen:
            seen.add(ssid)
            # normalize signal to int if possible
            try:
                signal = int(signal)
            except Exception:
                pass
            networks.append({"ssid": ssid, "signal": signal, "security": security})
    return networks

# ---------------- Flask Routes ----------------
@app.route("/wifi")
def wifi_page():
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Jetson Wi-Fi Connect</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 720px; margin: 24px auto; }
    button { margin: 6px 0; padding: 8px 12px; }
    .net { display:flex; justify-content:space-between; align-items:center; border:1px solid #ddd; border-radius:10px; padding:10px 12px; margin:8px 0;}
    .ssid { font-weight: 600; }
    .sig { opacity: .7; }
    #connect-form { border:1px solid #ddd; padding:12px; border-radius:10px; margin-top:16px; }
  </style>
  <script>
    async function loadWifiList() {
      try {
        const res = await fetch("/wifi-scan");
        if (!res.ok) throw new Error("scan failed");
        const list = await res.json();
        const container = document.getElementById("wifi-list");
        container.innerHTML = "";
        if (list.length === 0) {
          container.textContent = "No networks found. (Try again)";
          return;
        }
        list.forEach(net => {
          const row = document.createElement("div");
          row.className = "net";
          const left = document.createElement("div");
          left.innerHTML = "<div class='ssid'>" + net.ssid + "</div><div class='sig'>Signal: " + net.signal + (typeof net.signal==="number"?"%":"") + " | " + net.security + "</div>";
          const btn = document.createElement("button");
          btn.innerText = "Connect";
          btn.onclick = () => showConnectForm(net.ssid);
          row.appendChild(left); row.appendChild(btn);
          container.appendChild(row);
        });
      } catch (err) {
        console.warn("⚠️ Lost connection. Retrying in 3s...", err);
        setTimeout(loadWifiList, 3000);
      }
    }

    function showConnectForm(ssid) {
      document.getElementById("selected-ssid").value = ssid;
      document.getElementById("selected-ssid-label").innerText = ssid;
      document.getElementById("connect-form").style.display = "block";
      document.getElementById("password").value = "";
      document.getElementById("password").focus();
    }

    async function connectWifi(event) {
      event.preventDefault();
      const ssid = document.getElementById("selected-ssid").value;
      const password = document.getElementById("password").value;
      try {
        const res = await fetch("/connect", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ssid, password })
        });
        const data = await res.json();
        alert(data.message);
      } catch (e) {
        alert("❌ Request failed.");
      }
    }

    window.onload = () => {
      loadWifiList();
      setInterval(loadWifiList, 10000); // refresh every 10s
    };
  </script>
</head>
<body>
  <h2>Nearby Wi-Fi Networks (Client: {{sta}})</h2>
  <div id="wifi-list">Loading...</div>

  <div id="connect-form" style="display:none;">
    <h3>Connect to: <span id="selected-ssid-label"></span></h3>
    <form onsubmit="connectWifi(event)">
      <input type="hidden" id="selected-ssid" name="ssid" />
      <label>Password: </label>
      <input type="password" id="password" required />
      <button type="submit">Connect</button>
    </form>
  </div>
</body>
</html>
""", sta=STA_IF)

@app.route("/wifi-scan")
def wifi_scan_route():
    return jsonify(scan_wifi())

@app.route("/connect", methods=["POST"])
def connect_wifi_route():
    data = request.get_json(force=True, silent=True) or {}
    ssid = data.get("ssid", "").strip()
    password = data.get("password", "")

    if not ssid:
        return jsonify({"status": "error", "message": "❌ SSID is required."}), 400

    ensure_roles()

    # Clean any old connection with same name to avoid conflicts
    run(["nmcli", "connection", "delete", ssid])
    run(["nmcli", "connection", "delete", "temp-connection"])

    # Try connect on STA_IF, do NOT touch SoftAP services
    # If the SSID is open, nmcli works without 'password'
    cmd = ["nmcli", "dev", "wifi", "connect", ssid, "ifname", STA_IF, "name", "temp-connection"]
    if password:
        cmd += ["password", password]

    code, out, err = run(cmd, timeout=30)
    if code != 0:
        # Return nmcli stderr to UI
        msg = err or out or "Failed to connect."
        return jsonify({"status": "error", "message": f"❌ {msg}"}), 200

    # Wait a few seconds for DHCP
    for _ in range(10):
        if client_has_private_ip():
            return jsonify({"status": "success", "message": f"✅ Connected to {ssid} successfully!"}), 200
        time.sleep(1)

    # Connected but no IP
    return jsonify({"status": "error", "message": f"⚠️ Connected to {ssid} but no IP assigned."}), 200

# ---------------- Run ----------------
if __name__ == "__main__":
    # Ensure proper interface roles once at start
    ensure_roles()
    # Bind to AP IP so it’s only reachable over SoftAP
    app.run(host="192.168.4.1", port=5000)

