#!/usr/bin/env python3
"""Run the package transport/state smoke test in an isolated firmware VM.
Requires the existing TeslaMCU initramfs with its optional `fuzz` test entry.
All guest writes are in RAM. The firmware and base initramfs remain read-only.
"""
import argparse
import gzip
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def cpio_entry(name, data, mode, ino):
    name_bytes = name.encode() + b'\0'
    fields = [ino, mode, 0, 0, 1, 0, len(data), 0, 0, 0, 0, len(name_bytes), 0]
    out = b'070701' + b''.join(('%08x' % x).encode() for x in fields) + name_bytes
    out += b'\0' * (-len(out) % 4)
    out += data + b'\0' * (-len(data) % 4)
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--kernel', type=Path, required=True)
    p.add_argument('--initrd', type=Path, required=True)
    p.add_argument('--firmware', type=Path, required=True)
    p.add_argument('--qemu', default='qemu-system-x86_64')
    p.add_argument('--log', type=Path)
    p.add_argument('--suite', choices=['smoke', 'service', 'firmware'], default='smoke')
    args = p.parse_args()
    for path in [args.kernel, args.initrd, args.firmware]:
        if not path.is_file():
            p.error('Missing file: ' + str(path))
    runtime = (ROOT / 'packages/welcome-light/lib/runtime.sh').read_text()
    block = "cat > /tmp/runtime.sh <<'RUNTIME_END'\n" + runtime + 'RUNTIME_END'
    script = (ROOT / 'tests/target-transport.sh.in').read_text().replace('@@RUNTIME@@', block)
    if args.suite == 'service':
        blocks = []
        for rel in ['lib/runtime.sh', 'hooks/apply.sh', 'hooks/remove.sh', 'hooks/service.sh']:
            content = (ROOT / 'packages/welcome-light' / rel).read_text()
            blocks.append("cat > /tmp/pkg/" + rel + " <<'PACKAGE_FILE_END'\n" + content + 'PACKAGE_FILE_END')
        script = (ROOT / 'tests/target-service.sh.in').read_text().replace('@@PACKAGE@@', '\n'.join(blocks))
    if args.suite == 'firmware':
        script = (ROOT / 'tests/target-firmware.sh.in').read_text()
    extra = cpio_entry('fuzz.sh', script.encode(), 0o100755, 9001)
    extra += cpio_entry('TRAILER!!!', b'', 0, 9002)
    with tempfile.TemporaryDirectory(prefix='welcome-vm-') as work:
        initrd = Path(work) / 'test-initrd.gz'
        initrd.write_bytes(args.initrd.read_bytes() + gzip.compress(extra, mtime=0))
        result = subprocess.run([
            args.qemu, '-machine', 'q35', '-accel', 'tcg', '-cpu', 'max',
            '-m', '2048', '-smp', '2', '-kernel', str(args.kernel.resolve()),
            '-initrd', str(initrd), '-append', 'console=ttyS0 fuzz panic=1 loglevel=4',
            '-drive', 'if=virtio,format=raw,file=' + str(args.firmware.resolve()) + ',readonly=on',
            '-nic', 'none', '-display', 'none', '-serial', 'stdio', '-monitor', 'none',
            '-no-reboot'], capture_output=True, text=True, timeout=180)
    output = result.stdout + result.stderr
    if args.log:
        args.log.write_text(output)
    for line in output.splitlines():
        if 'WELCOME_' in line:
            print(line)
    expected = ['WELCOME_TARGET_TRANSPORT_PASS', 'WELCOME_TARGET_STATE_PASS', 'WELCOME_TARGET_DONE']
    if args.suite == 'service':
        expected = ['WELCOME_SERVICE_' + name + '_PASS' for name in
                    ['TIMEOUT', 'gear', 'occupancy', 'disabled', 'telemetry', 'TERM',
                     'HTTP_FAILURE', 'AUTH', 'HOOKS']] + ['WELCOME_SERVICE_DONE']
    if args.suite == 'firmware':
        expected = ['WELCOME_FIRMWARE_DONE', 'string "com.tesla.Debug"']
        write_result = output.split('WELCOME_FIRMWARE_WRITE_BEGIN')[-1].split('WELCOME_FIRMWARE_WRITE_END')[0]
        restore_result = output.split('WELCOME_FIRMWARE_RESTORE_BEGIN')[-1].split('WELCOME_FIRMWARE_RESTORE_END')[0]
        if 'string "ParkingLights"' not in write_result or 'string "<invalid>"' not in restore_result:
            print(output[-10000:])
            raise SystemExit('Native Debug write/restore was not verified')
        print(output[output.find('WELCOME_FIRMWARE_BUS_NAMES_BEGIN'):])
    if result.returncode or '_FAIL ' in output or 'WELCOME_TARGET_TRANSPORT_FAIL' in output or 'WELCOME_TARGET_STATE_FAIL' in output or any(x not in output for x in expected) or 'Kernel panic' in output:
        print(output[-6000:])
        raise SystemExit('Target VM smoke test failed')
    print('Target VM exited cleanly; this does not verify an SDK daemon or physical lamps.')


if __name__ == '__main__':
    main()
