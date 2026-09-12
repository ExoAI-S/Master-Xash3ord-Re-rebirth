"""Collect local MSR crash evidence without copying identities, saves or dumps."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSIONS = ('Portable-Package', 'Stable-Base')


def redact(text):
    text = re.sub(r'(?i)(?:setinfo\s+"?_fnid"?\s+|profile_key["\s:=]+)[^\r\n]+', '[player identity omitted]', text)
    text = re.sub(r'(?i)(?:rcon_password|password|secret|token)["\s:=]+[^\r\n]+', '[credential omitted]', text)
    text = re.sub(r'(?i)\b[a-f0-9]{32,}\b', '[long identifier omitted]', text)
    text = text.replace(str(ROOT), '[MSR folder]')
    profile = os.environ.get('USERPROFILE')
    if profile:
        text = re.sub(re.escape(profile), '[Windows user]', text, flags=re.I)
    return text


def event_report():
    command = ['wevtutil.exe', 'qe', 'Application', '/q:*[System[(EventID=1000 or EventID=1001) and TimeCreated[timediff(@SystemTime) <= 86400000]]]', '/rd:true', '/c:100', '/f:xml', '/e:Events']
    result = subprocess.run(command, capture_output=True, timeout=30,
                            creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:
        return 'Windows event query failed: ' + result.stderr.decode('utf-8', errors='replace')
    raw = result.stdout
    text = raw.decode('utf-16' if raw.startswith((b'\xff\xfe', b'\xfe\xff')) or b'\x00' in raw[:100] else 'utf-8-sig', errors='replace')
    root = ET.fromstring(text)
    matches = []
    for event in root:
        serialized = ET.tostring(event, encoding='unicode')
        if re.search(r'(?i)xash3d\.exe|MSR-Launcher\.exe', serialized):
            matches.append(serialized)
    return '\n\n'.join(matches) or 'No matching Application Error / Windows Error Reporting event found in the last 24 hours.'


def main():
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    output_dir = ROOT / 'Diagnostics'
    output_dir.mkdir(exist_ok=True)
    output = output_dir / ('MSR-diagnostics-' + stamp + '.zip')
    details = {'created_utc': stamp, 'windows': platform.platform(), 'binaries': {}, 'errors': [], 'crash_dumps_available': []}
    files = {}
    for version in VERSIONS:
        base = ROOT / version
        for relative in ('game/xash3d.exe', 'game/xash.dll', 'game/msr/cl_dlls/client.dll', 'game/msr/dlls/ms.dll'):
            path = base / relative
            if path.is_file():
                with path.open('rb') as stream:
                    digest = hashlib.file_digest(stream, 'sha256').hexdigest()
                details['binaries'][version + '/' + relative] = {'bytes': path.stat().st_size, 'sha256': digest}
        logs = list((base / 'game').glob('*.log')) + list((base / 'logs').glob('*.log')) + list((base / 'game/msr').glob('*.log'))
        for path in logs:
            try:
                # Keep the last 512 KiB of each recent log. Never read configuration or save files.
                if datetime.now().timestamp() - path.stat().st_mtime > 86400:
                    continue
                with path.open('rb') as stream:
                    stream.seek(max(0, path.stat().st_size - 512 * 1024))
                    tail = stream.read()
                files[path.relative_to(ROOT).as_posix()] = redact(tail.decode('utf-8', errors='replace'))
            except OSError as error:
                details['errors'].append(type(error).__name__ + ': ' + path.name)
    log = ROOT / 'launcher-error.log'
    if log.is_file():
        files['launcher-error.log'] = redact(log.read_text(encoding='utf-8', errors='replace')[-65536:])
    try:
        files['windows-crash-events.xml'] = redact(event_report())
    except (OSError, subprocess.SubprocessError, ET.ParseError) as error:
        details['errors'].append('Windows crash events: ' + type(error).__name__ + ': ' + str(error))
    dump_dir = Path(os.environ.get('LOCALAPPDATA', str(ROOT))) / 'CrashDumps'
    for path in sorted(dump_dir.glob('xash3d.exe.*.dmp'), key=lambda p: p.stat().st_mtime, reverse=True)[:5]:
        details['crash_dumps_available'].append({'name': path.name, 'bytes': path.stat().st_size, 'modified_utc': datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()})
    files['diagnostics.json'] = json.dumps(details, indent=2)
    files['README.txt'] = ('This report contains recent MSR log tails, binary hashes, Windows crash events and a list of available dumps.\n'
                           'It does not include crash dump contents, player-profile.json, FN databases or configuration files.\n'
                           'Review the report before sharing it. Nothing was uploaded.\n')
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, text in files.items():
            archive.writestr(name, text)
    print('Diagnostic report created:\n' + str(output))
    print('Review it before sending it. No files were uploaded.')


if __name__ == '__main__':
    main()
