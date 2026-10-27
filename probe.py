"""Feasibility probe: can a GitHub-hosted Windows runner run the MT5 terminal and reach PurpleTrading-Demo?
Never prints secrets. DEMO account only."""
import os, sys, time, base64, shutil, json
import MetaTrader5 as mt5

EXE = r"C:\Program Files\MetaTrader 5\terminal64.exe"
CFG = os.path.join(os.path.dirname(EXE), "Config")
LOGIN, SERVER = 20057324, "PurpleTrading-Demo"

def step(name, fn):
    t = time.time()
    try:
        r = fn()
    except Exception as e:
        r = f"EXC {type(e).__name__}: {e}"
    print(f"[{time.time() - t:6.1f}s] {name}: {r} | last_error={mt5.last_error()}", flush=True)
    return r

s1, s2 = os.environ.get("MT5_SERVERS_1", ""), os.environ.get("MT5_SERVERS_2", "")
if s1:
    os.makedirs(CFG, exist_ok=True)
    data = base64.b64decode(s1 + s2)
    open(os.path.join(CFG, "servers.dat"), "wb").write(data)
    print("servers.dat written", len(data), "bytes")
else:
    print("no servers.dat secret")

ok = step("initialize (no login, portable)", lambda: mt5.initialize(path=EXE, portable=True, timeout=180000))
if ok is True:
    ti = mt5.terminal_info()
    print("terminal:", {k: getattr(ti, k) for k in ("build", "connected", "community_account", "path", "data_path")})
    print("version:", mt5.version())
pw = os.environ.get("MT5_PASSWORD", "")
if os.environ.get("MODE") == "login" and pw:
    r = step("login real", lambda: mt5.login(LOGIN, password=pw, server=SERVER, timeout=120000))
    if r is True:
        a = mt5.account_info()
        print("account:", {"login_ok": a.login == LOGIN, "trade_mode": a.trade_mode, "currency": a.currency, "server": a.server})
        for s in ("XAUUSD_ecn", "US500_ecn", "US100_ecn", "USDCZK_ecn"):
            mt5.symbol_select(s, True); time.sleep(1)
            t = mt5.symbol_info_tick(s)
            print(s, "tick", None if t is None else {"bid": t.bid, "ask": t.ask, "time": t.time})
        info = mt5.symbol_info("XAUUSD_ecn"); t = mt5.symbol_info_tick("XAUUSD_ecn")
        if a.trade_mode == 0 and info and t:
            req = dict(action=mt5.TRADE_ACTION_DEAL, symbol="XAUUSD_ecn", volume=0.01, type=mt5.ORDER_TYPE_BUY,
                       price=t.ask, deviation=50, magic=1, type_filling=mt5.ORDER_FILLING_IOC, type_time=mt5.ORDER_TIME_GTC)
            c = mt5.order_check(req)
            print("order_check:", None if c is None else (c.retcode, c.comment))
else:
    step("login dummy (connectivity only)", lambda: mt5.login(LOGIN, password="probe-not-a-password", server=SERVER, timeout=60000))
    ti = mt5.terminal_info()
    print("after dummy: connected", None if ti is None else ti.connected)
mt5.shutdown()
print("PROBE DONE")
