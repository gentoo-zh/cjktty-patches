"""Drive the system test over the serial console.

Waits for the configured init system to reach a login, exercises the console
paths the patch touches -- font reload, VT switch, rotation and the fbcon
release path -- then shuts the machine down. Every step is asserted from what
the guest prints, not from a human looking at the screen; the screenshots are
artifacts for review.

Usage: drive-system.py <output-directory> <timeout-seconds>
       [--bootloader <kernel-release> | --install <kernel-release>]
"""

from __future__ import annotations

import os
import re
import shlex
import socket
import subprocess
import sys
import time
from pathlib import Path

ANSI = re.compile(rb"\x1b\[[0-9;?]*[a-zA-Z]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b[()][B0]|\x1b[=>]")

PROMPT = r"#|cjk> "
KERNEL_FINDING = re.compile(
    # systemd writes its own messages to /dev/kmsg and some carry the word
    # "warning", so match the kernel's own WARN_ON format rather than the word.
    rb"(?:\boops\b|\bBUG:|\bcall trace\b|WARNING: (?:CPU|at )|\bWARN_ON\b)",
    re.IGNORECASE
)


class Failed(Exception):
    pass


class Console:
    def __init__(self, path: Path, log: Path, deadline: float) -> None:
        self.log = log.open("wb")
        self.buffer = b""
        while time.monotonic() < deadline:
            self.sock = socket.socket(socket.AF_UNIX)
            try:
                self.sock.connect(str(path))
            except OSError:
                self.sock.close()
                time.sleep(0.5)
                continue
            self.sock.settimeout(1.0)
            return
        raise Failed(f"{path} never accepted a connection")

    def expect(self, pattern: str, timeout: float) -> bytes:
        matcher = re.compile(pattern.encode())
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            clean = ANSI.sub(b"", self.buffer)
            found = matcher.search(clean)
            if found is not None:
                self.buffer = clean[found.end() :]
                return clean[: found.end()]
            try:
                chunk = self.sock.recv(4096)
            except TimeoutError:
                continue
            if not chunk:
                raise Failed("the guest closed the console")
            self.log.write(chunk)
            self.log.flush()
            self.buffer += chunk
        raise Failed(f"never saw {pattern!r}; last output was {ANSI.sub(b'', self.buffer)[-400:]!r}")

    def send(self, line: str) -> None:
        self.sock.sendall(line.encode() + b"\n")

    def run(self, command: str, timeout: float = 60.0) -> bytes:
        token = f"MARK{int(time.monotonic() * 1000) % 100000}"
        self.send(f"{command}; echo {token}_$?")
        output = self.expect(rf"{token}_\d+\b", timeout)
        match = re.search(rf"{token}_(\d+)\b".encode(), output)
        if match is None:
            raise Failed(f"{command!r} returned no status marker")
        status = int(match.group(1))
        if status:
            raise Failed(f"{command!r} exited with status {status}")
        return output


def screenshot(monitor: Path, target: Path) -> None:
    sock = socket.socket(socket.AF_UNIX)
    sock.connect(str(monitor))
    time.sleep(0.5)
    sock.sendall(b"screendump " + str(target).encode() + b"\n")
    time.sleep(3)
    sock.close()


def check_rotated(screenshot_path: Path) -> None:
    checker = Path(__file__).with_name("check-console.py")
    result = subprocess.run(
        [sys.executable, str(checker), "--rotated", str(screenshot_path)],
        check=False,
    )
    if result.returncode:
        raise Failed(
            f"{screenshot_path.name} did not match the rotated built-in CJK glyphs"
        )


def socket_path(out: Path, environment: str, filename: str) -> Path:
    override = os.environ.get(environment)
    return Path(override) if override else out / filename


def login(console: Console, timeout: float) -> None:
    console.expect(r"login:|# ", timeout=timeout)
    console.send("")
    console.expect(PROMPT, timeout=60.0)

    # The stage3 shell emits OSC 133 sequences around every prompt, and a
    # digit inside one of those would be read back as command output.
    console.send("unset PROMPT_COMMAND; PS1='cjk> '")
    console.expect(r"cjk> ", timeout=30.0)


def install_kernel(out: Path, timeout: float, kernel_release: str) -> int:
    deadline = time.monotonic() + timeout
    release = shlex.quote(kernel_release)
    try:
        console = Console(
            socket_path(out, "CJKTTY_SERIAL_SOCKET", "monitor-serial.sock"),
            out / "serial.log",
            deadline,
        )
        login(console, timeout)
        console.run("mkdir -p /mnt/cjktty && mount /dev/vdb /mnt/cjktty")
        console.run(
            f"mkdir -p /lib/modules && "
            f"cp -a /mnt/cjktty/lib/modules/{release} /lib/modules/ && "
            f"test -d /lib/modules/{release}",
            timeout=300.0,
        )
        console.run(
            f"SYSTEMD_KERNEL_INSTALL=0 installkernel -v {release} "
            "/mnt/cjktty/kernel/bzImage /mnt/cjktty/kernel/System.map /boot",
            timeout=300.0,
        )
        console.run(f"test -s /boot/vmlinuz-{release}")
        console.run(f"test -s /boot/initramfs-{release}.img")
        console.run(f"grep -Fq vmlinuz-{release} /boot/grub/grub.cfg")
        console.run(f"grep -Fq initramfs-{release}.img /boot/grub/grub.cfg")
        console.run("sync")
        console.send("systemctl poweroff")
        console.expect(
            r"Reached target .*(Power Off|Shutdown)|reboot: Power down",
            timeout=120.0,
        )
    except Failed as error:
        print(f"kernel install: {error}", file=sys.stderr)
        return 1
    print(
        f"kernel install: installkernel installed {kernel_release} "
        "with a dracut initramfs"
    )
    return 0


def main(
    out: Path, timeout: float, bootloader: bool = False, kernel_release: str = ""
) -> int:
    deadline = time.monotonic() + timeout
    release = shlex.quote(kernel_release)
    init_system = os.environ.get("CJKTTY_INIT_SYSTEM", "systemd")
    if init_system not in ("systemd", "openrc"):
        print(f"system test: unsupported init system: {init_system}", file=sys.stderr)
        return 1
    try:
        console = Console(
            socket_path(out, "CJKTTY_SERIAL_SOCKET", "monitor-serial.sock"),
            out / "serial.log",
            deadline,
        )
        monitor = socket_path(out, "CJKTTY_MONITOR_SOCKET", "monitor.sock")

        if bootloader:
            try:
                console.expect(r"CJKTTY-GRUB-STARTED", timeout=60.0)
            except Failed as error:
                raise Failed(f"GRUB never reached its startup marker: {error}") from error
            try:
                console.expect(r"Linux version ", timeout=60.0)
            except Failed as error:
                raise Failed(f"GRUB started but did not hand off to Linux: {error}") from error

        login(console, timeout)

        if bootloader:
            # QEMU supplies no kernel command line in this mode, so only the
            # GRUB entry can provide this marker.
            console.run("grep -qw cjktty.bootloader=1 /proc/cmdline")
            console.run("dmesg | grep -q 'Unpacking initramfs'")
            console.run(f"test -s /boot/vmlinuz-{release}")
            console.run(f"test -s /boot/initramfs-{release}.img")

        # The init path must have completed its own console font reload before
        # the explicit setfont test below replaces that font.
        if init_system == "systemd":
            console.run(
                "state=$(systemctl is-system-running --wait 2>/dev/null || true); "
                "[ \"$state\" = running ] || [ \"$state\" = degraded ]",
                timeout=180.0,
            )
            console.run(
                "test \"$(systemctl show -p Result --value "
                "systemd-vconsole-setup.service)\" = success"
            )
        else:
            console.run("rc-status --runlevel default")
            console.run('test "$(cat /run/openrc/softlevel)" = default')
            console.run("rc-service consolefont status")

        # tty1 still holds the getty banner at this point: keep it as the picture
        # of a normal login screen under this kernel.
        screenshot(monitor, out / "login.ppm")

        # The init service loads a user font on VT 1. VT 2 still has the
        # kernel-selected 131072-entry CJK font, so exercise that path before
        # this script runs setfont. The CJK line written here is the text under
        # test.
        console.run('chvt 2; sleep 1; test "$(fgconsole)" = 2')
        console.run("echo 1 > /sys/class/graphics/fbcon/rotate_all; sleep 2")
        console.run("printf '\\033[2J\\033[H' > /dev/tty2; "
                    "echo 'rotated:  中文控制台显示测试' > /dev/tty2")
        time.sleep(2)
        built_in_rotated = out / "boot-font-rotated.ppm"
        built_in_rotated.unlink(missing_ok=True)
        screenshot(monitor, built_in_rotated)
        console.run("echo 0 > /sys/class/graphics/fbcon/rotate_all; sleep 2")
        console.run('chvt 1; sleep 1; test "$(fgconsole)" = 1')
        check_rotated(built_in_rotated)

        # The paths the patch changes: font reload, VT switch, and the release
        # path that frees the CJK buffers.
        test_font = os.environ.get("CJKTTY_TEST_FONT")
        if test_font:
            console.run(f"setfont {shlex.quote(test_font)}")
        else:
            console.run("setfont /usr/share/consolefonts/default8x16.psfu.gz || setfont")
        # fgconsole confirms the switch happened; chvt returns 0 either way.
        console.run('chvt 2; sleep 1; test "$(fgconsole)" = 2')
        console.run('chvt 1; sleep 1; test "$(fgconsole)" = 1')

        # fbcon_rotate_font_utf runs only under console rotation, and porting to
        # a new kernel rewrites it more often than any other part of the patch.
        # The CJK line written here is the text under test.
        console.run("echo 1 > /sys/class/graphics/fbcon/rotate_all; sleep 2")
        console.run("printf '\\033[2J\\033[H' > /dev/tty1; "
                    "echo 'rotated:  中文控制台显示测试' > /dev/tty1")
        time.sleep(2)
        screenshot(monitor, out / "rotated.ppm")
        console.run("echo 0 > /sys/class/graphics/fbcon/rotate_all; sleep 2")

        # Unbinding fbcon runs fbcon_release, which is where fontbuffer and
        # fontbuffer_utf are freed. Nothing else in this test reaches it.
        # The trailing test is what makes this an assertion: a loop that matches
        # no console would otherwise succeed and the release path go unrun.
        # Count the writes that took effect, not the ones attempted: a bind that
        # fails leaves the console attached and the test would not notice.
        bind = ("n=0; failed=0; for c in /sys/class/vtconsole/vtcon*; do "
                "grep -q 'frame buffer' $c/name || continue; "
                "echo {0} > $c/bind || failed=1; "
                "[ \"$(cat $c/bind)\" = {0} ] && n=$((n+1)) || failed=1; "
                "done; sleep 2; [ $n -gt 0 ] && [ $failed -eq 0 ]")
        console.run(bind.format(0))
        console.run(bind.format(1))
        console.run("dmesg | grep -q 'switching to colour dummy device'")

        kernel_log = console.run("dmesg")
        findings = [line for line in kernel_log.splitlines() if KERNEL_FINDING.search(line)]
        if findings:
            for line in findings[:40]:
                print(line.decode("utf-8", "replace"), file=sys.stderr)
            raise Failed(f"the kernel log holds {len(findings)} oops or warning lines")

        # check-console.py reads fixed rows, so lay the screen out the way init.c
        # does: clear, a title line, then the label and the CJK text under test.
        console.run("printf '\\033[2J\\033[H' > /dev/tty1; "
                    "echo 'cjktty system test' > /dev/tty1; "
                    "echo 'Simplified:  中文控制台显示测试' > /dev/tty1")
        time.sleep(2)
        screenshot(monitor, out / "console.ppm")

        if init_system == "systemd":
            console.send("systemctl poweroff")
        else:
            console.send("poweroff")
        console.expect(r"Reached target .*(Power Off|Shutdown)|reboot: Power down", timeout=120.0)
    except Failed as error:
        print(f"system test: {error}", file=sys.stderr)
        return 1
    print(f"system test: {init_system} booted, survived setfont, chvt, rotation "
          "and fbcon rebind, powered off clean")
    return 0


if __name__ == "__main__":
    if len(sys.argv) not in (3, 5):
        raise SystemExit(
            "usage: drive-system.py <output-directory> <timeout-seconds> "
            "[--bootloader <kernel-release> | --install <kernel-release>]"
        )
    output = Path(sys.argv[1])
    timeout = float(sys.argv[2])
    if len(sys.argv) == 3:
        raise SystemExit(main(output, timeout))
    if sys.argv[3] == "--bootloader":
        raise SystemExit(main(output, timeout, True, sys.argv[4]))
    if sys.argv[3] == "--install":
        raise SystemExit(install_kernel(output, timeout, sys.argv[4]))
    raise SystemExit("mode must be --bootloader or --install")
