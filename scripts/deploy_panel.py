"""Deploy the local panel to the Raspberry Pi and enable its port-80 service.

The script uses the existing SSH key in ~/.ssh/ruview_pi_lab unless --key is
provided. It does not touch the ASUS router.
"""
import argparse
from pathlib import Path
import shlex
import subprocess
import tarfile
import tempfile


ROOT = Path(__file__).resolve().parents[1]
FILES = [
    ROOT / "src" / "decoder.py",
    ROOT / "src" / "motion.py",
    ROOT / "src" / "recorder.py",
    ROOT / "src" / "web_panel.py",
    ROOT / "maps" / "home" / "floorplan.json",
    ROOT / "maps" / "home" / "devices.json",
    ROOT / "maps" / "home" / "floorplan-furnished.png",
    ROOT / "web" / "index.html",
    ROOT / "docs" / "API.openapi.json",
    ROOT / "deploy" / "ruview-lab-panel.service",
]


def run(command):
    return subprocess.run(command, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="192.168.50.100")
    parser.add_argument("--user", default="pi")
    parser.add_argument("--key", type=Path, default=Path.home() / ".ssh" / "ruview_pi_lab")
    parser.add_argument("--known-hosts", type=Path,
                        default=Path.home() / ".ssh" / "ruview_known_hosts")
    parser.add_argument("--remote-dir", default="/home/pi/ruview-lab")
    args = parser.parse_args()
    if any(not path.is_file() for path in FILES):
        missing = [str(path) for path in FILES if not path.is_file()]
        raise SystemExit("Missing deployment file(s): " + ", ".join(missing))
    with tempfile.TemporaryDirectory() as temp:
        archive = Path(temp) / "ruview-lab-panel.tar.gz"
        with tarfile.open(archive, "w:gz") as tar:
            for path in FILES:
                if path.name == "index.html":
                    name = "web/index.html"
                elif path.name.endswith(".service"):
                    name = "deploy/ruview-lab-panel.service"
                elif "maps" in path.parts:
                    name = "maps/home/" + path.name
                elif "docs" in path.parts:
                    name = "docs/" + path.name
                else:
                    name = path.name
                tar.add(path, arcname=name)
        target = f"{args.user}@{args.host}:/tmp/ruview-lab-panel.tar.gz"
        run(["scp", "-i", str(args.key), "-o", "StrictHostKeyChecking=yes",
             "-o", f"UserKnownHostsFile={args.known_hosts}",
             str(archive), target])
    remote = (
        f"set -eu; mkdir -p {shlex.quote(args.remote_dir)}; "
        f"tar -xzf /tmp/ruview-lab-panel.tar.gz -C {shlex.quote(args.remote_dir)}; "
        f"sudo install -m 0644 {shlex.quote(args.remote_dir)}/deploy/ruview-lab-panel.service "
        "/etc/systemd/system/ruview-lab-panel.service; "
        "sudo systemctl daemon-reload; "
        "sudo systemctl enable ruview-lab-panel.service; "
        "sudo systemctl restart ruview-lab-panel.service; "
        "sudo systemctl --no-pager --full status ruview-lab-panel.service"
    )
    run(["ssh", "-i", str(args.key), "-o", "StrictHostKeyChecking=yes",
         "-o", f"UserKnownHostsFile={args.known_hosts}",
         f"{args.user}@{args.host}", remote])
    print(f"Panel deployed: http://{args.host}/")


if __name__ == "__main__":
    main()
