"""Feasibility probe v3: GitHub-hosted Windows runner + MT5 terminal + Python API. Never prints secrets. DEMO only."""
import os, sys, time, base64, glob, subprocess
import MetaTrader5 as mt5

EXE = r"C:\Program Files\MetaTrader 5\terminal64.exe"
LOGIN, SERVER = 20057324, "PurpleTrading-Demo"
APPDATA = os.environ.get("APPDATA", "")
mode = os.environ.get("MODE", "probe"); pw = os.environ.get("MT5_PASSWORD", "")

def ps(cmd):
    return subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True).stdout.strip()

def step(name, fn):
    t = time.time()
    try: r = fn()
    except Exception as e: r = f"EXC {type(e).__name__}: {e}"
    print(f"[{time.time() - t:6.1f}s] {name}: {r} | last_error={mt5.last_error()}", flush=True)
    return r

def shot(name):
    os.makedirs("shots", exist_ok=True)
    print(ps("Add-Type -AssemblyName System.Windows.Forms,System.Drawing;$b=[System.Windows.Forms.Screen]::PrimaryScreen.Bounds;"
             "$i=New-Object System.Drawing.Bitmap $b.Width,$b.Height;$g=[System.Drawing.Graphics]::FromImage($i);"
             f"$g.CopyFromScreen($b.Location,[System.Drawing.Point]::Empty,$b.Size);$i.Save('shots\\{name}.png');'shot {name}'"))

def version():
    return ps(f"(Get-Item '{EXE}').VersionInfo.FileVersion")

def windows():
    return ps("Get-Process | ? { $_.MainWindowTitle } | % { $_.ProcessName + ': ' + $_.MainWindowTitle }")

def term_log(n=25):
    out = []
    for d in glob.glob(os.path.join(APPDATA, "MetaQuotes", "Terminal", "*", "logs", "*.log")):
        try: txt = open(d, encoding="utf-16", errors="replace").read()
        except Exception: continue
        out += [l for l in txt.splitlines() if any(k in l.lower() for k in ("author", "login", "network", "build", "connect", "account", "liveupdate", "terminal"))]
    return "\n".join(out[-n:])

def press(title, key):
    return ps(f"$w=New-Object -ComObject WScript.Shell; if($w.AppActivate('{title}')){{Start-Sleep -m 500; $w.SendKeys('{key}'); 'sent {key} to {title}'}} else {{'no window {title}'}}")

print("terminal file version (installed):", version())
servers = base64.b64decode(os.environ.get("MT5_SERVERS_1", "") + os.environ.get("MT5_SERVERS_2", ""))
dirs = glob.glob(os.path.join(APPDATA, "MetaQuotes", "Terminal", "*", "config"))
print("data dirs before launch:", len(dirs))
for d in dirs:
    if servers: open(os.path.join(d, "servers.dat"), "wb").write(servers)

args = [EXE]; ini = os.path.join(os.environ.get("RUNNER_TEMP", "."), "start.ini")
if mode == "login" and pw:
    open(ini, "w", encoding="utf-16").write(f"[Common]\nLogin={LOGIN}\nPassword={pw}\nServer={SERVER}\nKeepPrivate=1\nNewsEnable=0\n[Experts]\nAllowLiveTrading=1\nEnabled=1\n")
    args.append("/config:" + ini)
subprocess.Popen(args)

# accept LiveUpdate (moves the beta build the installer delivers to the stable build the Python API matches)
restarted = False
for i in range(30):
    time.sleep(10)
    w = windows()
    if "LiveUpdate" in w:
        print(f"t+{10*(i+1)}s windows: {w}")
        shot("1_liveupdate")
        print(press("LiveUpdate", "{ENTER}"))
        restarted = True
        time.sleep(60)
        break
print("after LiveUpdate: version", version(), "| restarted", restarted)
print("windows:", windows())
if mode == "login" and pw and restarted:   # the restarted terminal does not keep /config -> start it again with the ini
    if "terminal64" not in ps("(Get-Process terminal64 -EA 0).ProcessName"):
        subprocess.Popen(args); time.sleep(40)
time.sleep(20)
shot("2_before_init")
print("terminal log:\n" + term_log())
if mode == "login" and pw:
    ok = step("initialize with login", lambda: mt5.initialize(path=EXE, login=LOGIN, password=pw, server=SERVER, timeout=120000))
else:
    ok = step("initialize attach", lambda: mt5.initialize(path=EXE, timeout=120000))
try: os.remove(ini)
except OSError: pass
if ok is True:
    ti = mt5.terminal_info(); print("terminal:", {k: getattr(ti, k) for k in ("build", "connected", "trade_allowed")})
    a = mt5.account_info()
    if a: print("account:", {"login_ok": a.login == LOGIN, "trade_mode": a.trade_mode, "currency": a.currency, "server": a.server, "equity": round(a.equity)})
    for s in ("XAUUSD_ecn", "US500_ecn", "US100_ecn", "USDCZK_ecn"):
        mt5.symbol_select(s, True); time.sleep(1); t = mt5.symbol_info_tick(s)
        print(s, "tick", None if t is None else {"bid": t.bid, "ask": t.ask, "time": t.time})
    pos = mt5.positions_get(); print("open positions visible:", None if pos is None else [(p.symbol, p.volume, p.magic) for p in pos])
else:
    print("terminal log after init:\n" + term_log(15))
shot("3_end")
mt5.shutdown()
print("PROBE DONE")
