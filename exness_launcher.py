import subprocess
import time
import os
import sys
import psutil
import signal

try:
    from colorama import init, Fore, Style
    init(autoreset=True)
    COLORAMA_AVAILABLE = True
except ImportError:
    COLORAMA_AVAILABLE = False

# Path to your Exness MT5 terminal (portable mode)
MT5_PATHS = [
    os.path.join(os.getcwd(), "MetaTrader 5 EXNESS", "terminal64.exe"),
    os.path.join(os.getcwd(), "MetaTrader 5 EXNESS", "terminal.exe"),
    r"C:\Program Files\MetaTrader 5 EXNESS\terminal64.exe",
    r"C:\Program Files\MetaTrader 5 EXNESS\terminal.exe"
]

LOGFILE = "exness_launcher.log"
def log(msg, level="info"):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(LOGFILE, "a") as f:
        f.write(f"[{timestamp}] {msg}\n")
    if COLORAMA_AVAILABLE:
        if level == "error":
            print(Fore.RED + msg)
        elif level == "success":
            print(Fore.GREEN + msg)
        elif level == "warn":
            print(Fore.YELLOW + msg)
        else:
            print(msg)
    else:
        print(msg)

# Allow config via environment variables
MT5_PATH = os.environ.get("EXNESS_MT5_PATH", None)
STRATEGY_SCRIPT = os.environ.get("EXNESS_STRATEGY_SCRIPT", "exness_crt_trader.py")
if not MT5_PATH:
    for path in MT5_PATHS:
        if os.path.exists(path):
            MT5_PATH = path
            break
if MT5_PATH is None:
    log("Could not find Exness MT5 terminal (terminal64.exe or terminal.exe). Please check the path.", level="error")
    sys.exit(1)
MT5_WORKDIR = os.path.dirname(MT5_PATH)

def start_mt5():
    # Check if MT5 is already running from this folder
    try:
        for proc in psutil.process_iter(['name', 'cwd']):
            if proc.info['name'] and 'terminal64.exe' in proc.info['name'].lower():
                if proc.info['cwd'] and os.path.normcase(proc.info['cwd']) == os.path.normcase(MT5_WORKDIR):
                    log("Exness MT5 already running in portable mode.", level="success")
                    return
    except ImportError:
        log("psutil not installed, skipping process check.", level="warn")
    log(f"Starting Exness MT5 terminal from {MT5_PATH} ...")
    subprocess.Popen([MT5_PATH, "/portable"], cwd=MT5_WORKDIR)
    time.sleep(10)  # Wait for terminal to initialize
    # Verify MT5 started
    mt5_found = False
    for proc in psutil.process_iter(['name', 'cwd']):
        if proc.info['name'] and 'terminal64.exe' in proc.info['name'].lower():
            if proc.info['cwd'] and os.path.normcase(proc.info['cwd']) == os.path.normcase(MT5_WORKDIR):
                mt5_found = True
                break
    if not mt5_found:
        log("ERROR: Exness MT5 terminal did not start correctly. Please check your installation.", level="error")
        sys.exit(2)

def run_strategy():
    log("Running Exness CRT strategy...")
    max_restarts = 5
    restart_delay = 30  # seconds
    restarts = 0
    while True:
        result = subprocess.run([sys.executable, STRATEGY_SCRIPT])
        if result.returncode == 0:
            log("Strategy script completed successfully.", level="success")
            break
        else:
            log(f"ERROR: Strategy script exited with code {result.returncode}", level="error")
            restarts += 1
            if restarts > max_restarts:
                log(f"Max restarts ({max_restarts}) reached. Exiting.", level="error")
                break
            log(f"Restarting strategy in {restart_delay} seconds... (attempt {restarts}/{max_restarts})", level="warn")
            time.sleep(restart_delay)

def handle_exit(signum, frame):
    log(f"Received signal {signum}. Shutting down gracefully...", level="warn")
    # Optionally, terminate MT5 process if started by this script
    # (Not implemented here for safety)
    sys.exit(0)

signal.signal(signal.SIGINT, handle_exit)
signal.signal(signal.SIGTERM, handle_exit)

if __name__ == "__main__":
    try:
        start_mt5()
        run_strategy()
    except Exception as e:
        log(f"Launcher error: {e}", level="error")
        sys.exit(3)
