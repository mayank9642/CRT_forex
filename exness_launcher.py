import subprocess
import time
import os
import sys
import psutil

# Path to your Exness MT5 terminal (portable mode)
MT5_PATHS = [
    os.path.join(os.getcwd(), "MetaTrader 5 EXNESS", "terminal64.exe"),
    os.path.join(os.getcwd(), "MetaTrader 5 EXNESS", "terminal.exe"),
    r"C:\Program Files\MetaTrader 5 EXNESS\terminal64.exe",
    r"C:\Program Files\MetaTrader 5 EXNESS\terminal.exe"
]
MT5_PATH = None
for path in MT5_PATHS:
    if os.path.exists(path):
        MT5_PATH = path
        break
if MT5_PATH is None:
    print("Could not find Exness MT5 terminal (terminal64.exe or terminal.exe). Please check the path.")
    sys.exit(1)
MT5_WORKDIR = os.path.dirname(MT5_PATH)
STRATEGY_SCRIPT = "exness_crt_trader.py"  # Your Exness strategy script

def start_mt5():
    # Check if MT5 is already running from this folder
    try:
        for proc in psutil.process_iter(['name', 'cwd']):
            if proc.info['name'] and 'terminal64.exe' in proc.info['name'].lower():
                if proc.info['cwd'] and os.path.normcase(proc.info['cwd']) == os.path.normcase(MT5_WORKDIR):
                    print("Exness MT5 already running in portable mode.")
                    return
    except ImportError:
        print("psutil not installed, skipping process check.")
    print(f"Starting Exness MT5 terminal from {MT5_PATH} ...")
    subprocess.Popen([MT5_PATH, "/portable"], cwd=MT5_WORKDIR)
    time.sleep(10)  # Wait for terminal to initialize

def run_strategy():
    print("Running Exness CRT strategy...")
    subprocess.run([sys.executable, STRATEGY_SCRIPT])

if __name__ == "__main__":
    # Removed conflicting MT5 check; always use Exness terminal for CRT strategy
    start_mt5()
    run_strategy()
