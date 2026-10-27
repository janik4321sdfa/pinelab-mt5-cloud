"""Feasibility probe v2: can a GitHub-hosted Windows runner run the MT5 terminal + Python API?
Never prints secrets. DEMO account only."""
import os, sys, time, base64, glob, subprocess, json
import MetaTrader5 as mt5

EXE = r"C:\Program Files\MetaTrader 5\terminal64.exe"
LOGIN, SERVER = 20057324, "PurpleTrading-Demo"
APPDATA = os.environ.get("APPDATA", "")

def step(name, fn):
    t = time.time()
    try: r = fn()
    except Exception as e: r = f"EXC {type(e).__name__}: {e}"
    print(f"[{time.time() - t:6.1f}s] {name}: {r} | last_error={mt5.last_error()}", flush=True)
    return r

def shot(name):
    ps = ("Add-Type -AssemblyName System.Windows.Forms,System.Drawing;$b=[System.Windows.Forms.Screen]::PrimaryScreen.Bounds;"
          "$i=New-Object System.Drawing.Bitmap $b.Width,$b.Height;$g=[System.Drawing.Graphics]::FromImage($i);"
          f"$g.CopyFromScreen($b.Location,[System.Drawing.Point]::Empty,$b.Size);$i.Save('shots\\{name}.png');'shot '+$b.Width+'x'+$b.Height")
    os.makedirs("shots", exist_ok=True)
    print(subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True).stdout.strip() or "shot failed")

def procs():
    out = subprocess.run(["tasklist"], capture_output=True, text=True).stdout
    return [l.split()[0] for l in out.splitlines() if any(k in l.lower() for k in ("terminal", "mt5", "metaq"))]

servers = base64.b64decode(os.environ.get("MT5_SERVERS_1", "") + os.environ.get("MT5_SERVERS_2", ""))
print("session:", subprocess.run(["query", "session"], capture_output=True, text=True).stdout.strip()[:400])
print("procs before:", procs())
shot("0_before")

mode = os.environ.get("MODE", "probe")
# A) launch terminal ourselves (non-portable), let it create its data dir, then put servers.dat there
p = subprocess.Popen([EXE])
time.sleep(70)
print("procs after launch:", procs())
esc = "$w=New-Object -ComObject WScript.Shell; $ok=$w.AppActivate('MetaTrader 5'); Start-Sleep 1; $w.SendKeys('{ESC}'); Start-Sleep 2; 'appactivate '+$ok"
print(subprocess.run(["powershell", "-NoProfile", "-Command", esc], capture_output=True, text=True).stdout.strip())
time.sleep(5)
shot("1_after_launch")
dirs = glob.glob(os.path.join(APPDATA, "MetaQuotes", "Terminal", "*", "config"))
print("data dirs:", dirs)
if servers and dirs:
    for d in dirs: open(os.path.join(d, "servers.dat"), "wb").write(servers)
    print("servers.dat written to", len(dirs), "dirs")
ok = step("initialize attach (no login)", lambda: mt5.initialize(path=EXE, timeout=120000))
if ok is True:
    ti = mt5.terminal_info()
    print("terminal:", {k: getattr(ti, k) for k in ("build", "connected", "path", "data_path")})
pw = os.environ.get("MT5_PASSWORD", "")
if ok is True:
    if mode == "login" and pw:
        r = step("login real", lambda: mt5.login(LOGIN, password=pw, server=SERVER, timeout=120000))
    else:
        r = step("login dummy (connectivity only)", lambda: mt5.login(LOGIN, password="probe-not-a-password", server=SERVER, timeout=60000))
    if r is True:
        a = mt5.account_info()
        print("account:", {"login_ok": a.login == LOGIN, "trade_mode": a.trade_mode, "currency": a.currency, "server": a.server})
        for s in ("XAUUSD_ecn", "US500_ecn", "US100_ecn", "USDCZK_ecn"):
            mt5.symbol_select(s, True); time.sleep(1); t = mt5.symbol_info_tick(s)
            print(s, "tick", None if t is None else {"bid": t.bid, "ask": t.ask, "time": t.time})
    ti = mt5.terminal_info(); print("connected:", None if ti is None else ti.connected)
shot("2_end")
mt5.shutdown()
print("PROBE DONE")
