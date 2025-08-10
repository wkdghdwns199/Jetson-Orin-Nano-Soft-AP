#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from flask import Flask, request, jsonify, render_template_string, abort
import subprocess
import shlex
import re
import time
import ipaddress

# ========= CONFIGURE THESE IF NEEDED =========
AP_IF = "wlxa047d7115a68"                # SoftAP interface (hostapd/dnsmasq running)
STA_IF = "wlP1p1s0"                      # Wi-Fi client interface (managed by NetworkManager)
AP_GATEWAY_IP = "192.168.4.1"
AP_NETWORK = ipaddress.ip_network("192.168.4.0/24")
# ============================================

app = Flask(__name__)

# ---------------- Utilities ----------------
def run(cmd, timeout=30):
    """Run a shell command and return (rc, stdout, stderr)."""
    if isinstance(cmd, str):
        cmd = shlex.split(cmd)
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return p.returncode, p.stdout.strip(), p.stderr.strip()

def ensure_roles():
    """Ensure AP_IF is unmanaged by NM and has AP IP; STA_IF is managed by NM."""
    run(["nmcli", "device", "set", AP_IF, "managed", "no"])
    run(["nmcli", "device", "set", STA_IF, "managed", "yes"])
    # Make sure AP IP exists
    run(["ip", "addr", "add", f"{AP_GATEWAY_IP}/24", "dev", AP_IF])
    run(["ip", "link", "set", AP_IF, "up"])
    # Ensure Wi-Fi radio is on for scanning/connecting
    run(["nmcli", "radio", "wifi", "on"])

def client_has_private_ip():
    """Check if STA_IF currently has a private IPv4 address."""
    rc, out, _ = run(["nmcli", "-t", "-f", "IP4.ADDRESS", "device", "show", STA_IF])
    if rc != 0:
        return False
    for line in out.splitlines():
        if not line:
            continue
        ip = line.split(":")[-1].split("/")[0]
        try:
            if ipaddress.ip_address(ip).is_private:
                return True
        except ValueError:
            pass
    return False

def only_from_softap():
    """Allow access only when the caller is in the AP subnet (or localhost)."""
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    if ip in ("127.0.0.1", "::1"):
        return
    try:
        if ipaddress.ip_address(ip) in AP_NETWORK:
            return
    except Exception:
        pass
    abort(403, "This page is only available from the SoftAP network")

@app.before_request
def _gate():
    only_from_softap()

# --------------- NetworkManager log helpers ---------------
WRONG_PW_PATTERNS = [
    "pre-shared key may be incorrect",
    "invalid secrets",
    "wrong password",
    "no secrets were provided",
    "agent reported error",
    "auth failed",
    "wpa: 4-way handshake failed",
    "wpa: authentication failed",
]
SSID_NOT_FOUND_PATTERNS = [
    "no network with ssid",
    "ssid not found",
    "the network could not be found",
]
TIMEOUT_PATTERNS = [
    "association took too long",
    "activation timed out",
]

def get_nm_logs_since(epoch_secs: float, lines=300):
    since = f"@{int(epoch_secs)}"
    rc, out, err = run(["journalctl", "-u", "NetworkManager", "-b", "--since", since, "--no-pager", f"-n{lines}"])
    return out if rc == 0 else (err or "")

def classify_failure(nmcli_stderr: str, nm_logs: str):
    text = f"{nmcli_stderr}\n{nm_logs}".lower()
    if any(p in text for p in WRONG_PW_PATTERNS):
        return "wrong_password"
    if any(p in text for p in SSID_NOT_FOUND_PATTERNS):
        return "ssid_not_found"
    if any(p in text for p in TIMEOUT_PATTERNS):
        return "timeout"
    return "unknown"

# ---------------- Wi-Fi scan (STA_IF) ----------------
def scan_wifi():
    ensure_roles()
    # Request a rescan and list via NM (more robust than parsing iwlist)
    run(["nmcli", "device", "wifi", "rescan", "ifname", STA_IF])

    rc, out, err = run([
        "nmcli",
        "-f", "SSID,SIGNAL,SECURITY",
        "device", "wifi", "list",
        "ifname", STA_IF
    ], timeout=25)

    if rc != 0:
        print(f"[scan] nmcli error: {err}")
        return []

    lines = [l for l in out.splitlines() if l.strip()]
    if lines and lines[0].strip().upper().startswith("SSID"):
        lines = lines[1:]

    nets = []
    seen = set()
    for line in lines:
        parts = re.split(r"\s{2,}", line.strip())
        if not parts:
            continue
        ssid = parts[0].strip()
        if not ssid or ssid == "--":
            continue
        signal = parts[1].strip() if len(parts) > 1 else "?"
        security = parts[2].strip() if len(parts) > 2 else ""
        if ssid in seen:
            continue
        seen.add(ssid)
        try:
            signal = int(signal)
        except Exception:
            pass
        nets.append({"ssid": ssid, "signal": signal, "security": security})
    return nets

# ---------------- Flask routes ----------------
@app.route("/wifi")
def wifi_page():
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Jetson Wi-Fi Connect</title>
  <style>
    body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; max-width: 760px; margin: 24px auto; }
    button { margin: 6px 0; padding: 8px 12px; cursor:pointer; }
    .net { display:flex; justify-content:space-between; align-items:center; border:1px solid #ddd; border-radius:10px; padding:10px 12px; margin:8px 0;}
    .ssid { font-weight: 600; }
    .sig { opacity: .7; font-size: 13px; }
    #connect-form { border:1px solid #ddd; padding:12px; border-radius:10px; margin-top:16px; display:none; }
    input[type=password] { padding:6px 8px; }
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
      setInterval(loadWifiList, 10000);
    };
  </script>
</head>
<body>
  <h2>Nearby Wi-Fi Networks (Client: {{sta}})</h2>
  <div id="wifi-list">Loading...</div>

  <div id="connect-form">
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
    ssid = (data.get("ssid") or "").strip()
    password = data.get("password") or ""

    if not ssid:
        return jsonify({"status": "error", "message": "❌ SSID is required."}), 200

    ensure_roles()

    # Clean any old profiles with same name
    run(["nmcli", "connection", "delete", ssid])
    run(["nmcli", "connection", "delete", "temp-connection"])

    # Record start time to read only relevant logs
    t0 = time.time()

    # Build nmcli connect command for STA_IF
    cmd = ["nmcli", "-w", "25", "dev", "wifi", "connect", ssid, "ifname", STA_IF, "name", "temp-connection"]
    if password:
        cmd += ["password", password]

    code, out, err = run(cmd, timeout=35)

    # Immediate failure: classify via nmcli stderr + NM logs
    if code != 0:
        nm_logs = get_nm_logs_since(t0)
        cause = classify_failure(err, nm_logs)
        if cause == "wrong_password":
            return jsonify({"status": "error", "message": f"❌ Wrong password for '{ssid}'."}), 200
        if cause == "ssid_not_found":
            return jsonify({"status": "error", "message": f"❌ Network '{ssid}' not found."}), 200
        if cause == "timeout":
            return jsonify({"status": "error", "message": f"⌛ Connection to '{ssid}' timed out."}), 200
        # generic fallback with nmcli error text
        return jsonify({"status": "error", "message": f"❌ Failed to connect to '{ssid}': {err or out}"}), 200

    # nmcli returned success — wait briefly for DHCP (private IPv4)
    for _ in range(12):
        if client_has_private_ip():
            return jsonify({"status": "success", "message": f"✅ Connected to '{ssid}' successfully!"}), 200
        time.sleep(1)

    # No IP assigned — check NM logs whether it was actually bad auth
    nm_logs = get_nm_logs_since(t0)
    cause = classify_failure("", nm_logs)
    if cause == "wrong_password":
        return jsonify({"status": "error", "message": f"❌ Wrong password for '{ssid}'."}), 200

    # Otherwise likely DHCP/captive portal
    return jsonify({"status": "error", "message": f"⚠️ Connected to '{ssid}' but no IP assigned (DHCP issue)."}), 200

# ---------------- Main ----------------
if __name__ == "__main__":
    ensure_roles()
    # Bind to all interfaces; access is still restricted to AP subnet by @before_request
    app.run(host="192.168.4.1", port=5000)

