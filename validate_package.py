import subprocess
import sys
import os

REPORT_FILE = "validation_report.txt"

COMMANDS = [
    ("Test import package", [sys.executable, "-c", "import brvm_package as bv; print(bv.list_assets())"]),
    ("Test CLI version", [sys.executable, "-m", "brvm_package.cli.main", "--help"]),
    ("Test CLI richbourse", [sys.executable, "-m", "brvm_package.cli.main", "richbourse"]),
    ("Test CLI sikafinance", [sys.executable, "-m", "brvm_package.cli.main", "sikafinance", "SNTS"]),
    ("Test CLI sync", [sys.executable, "-m", "brvm_package.cli.main", "sync", "--symbol", "SNTS", "--start", "2026-04-01", "--end", "2026-04-20"]),
    ("Test pytest", [sys.executable, "-m", "pytest", "-q", "--tb=short"]),
]

def run_and_capture(cmd):
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        return 1, '', str(e)

def main():
    with open(REPORT_FILE, "w") as f:
        f.write("# Rapport de validation BRVM Package\n\n")
        for label, cmd in COMMANDS:
            f.write(f"## {label}\n")
            f.write(f"$ {' '.join(cmd)}\n")
            code, out, err = run_and_capture(cmd)
            f.write(f"Exit code: {code}\n")
            if out:
                f.write(f"--- stdout ---\n{out}\n")
            if err:
                f.write(f"--- stderr ---\n{err}\n")
            f.write("\n\n")
    print(f"Rapport généré dans {REPORT_FILE}")

if __name__ == "__main__":
    main()
