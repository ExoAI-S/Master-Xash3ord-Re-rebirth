"""Local Xash3D query/RCON helper. Never sends credentials beyond loopback."""
import argparse
import json
from pathlib import Path
import re
import socket
import struct

PREFIX = b'\xff\xff\xff\xff'


def info(port, timeout=3):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(timeout)
        sock.connect(('127.0.0.1', port))
        query = PREFIX + b'TSource Engine Query\x00'
        sock.send(query)
        data = sock.recv(65535)
        if data[:5] == PREFIX + b'A':
            sock.send(query + data[5:9])
            data = sock.recv(65535)
        if data[:5] != PREFIX + b'I':
            raise ValueError('Unexpected A2S_INFO reply: ' + repr(data[:30]))
        offset = 6

        def string():
            nonlocal offset
            end = data.index(b'\0', offset)
            value = data[offset:end].decode('utf-8', errors='replace')
            offset = end + 1
            return value

        result = dict(name=string(), map=string(), folder=string(), game=string())
        result['appid'] = struct.unpack_from('<H', data, offset)[0]
        result['players'], result['maxplayers'], result['bots'] = data[offset+2:offset+5]
        result['password_required'] = bool(data[offset+7])
        offset += 9
        result['version'] = string()
        return result


def rcon(port, password, command):
    if any(c in password for c in '\r\n"') or any(c in command for c in '\r\n'):
        raise ValueError('Invalid RCON input')
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(3)
        sock.connect(('127.0.0.1', port))
        packet = b'rcon "' + password.encode('ascii') + b'" ' + command.encode('utf-8') + b'\n'
        sock.send(PREFIX + packet)
        output = []
        sock.settimeout(0.7)
        while True:
            try:
                data = sock.recv(65535)
                output.append(data[4:].removeprefix(b'print\n').rstrip(b'\0').decode('utf-8', errors='replace'))
            except socket.timeout:
                break
        return ''.join(output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['info', 'rcon', 'probe'])
    parser.add_argument('--port', type=int, default=27015)
    parser.add_argument('--settings', type=Path, default=Path(__file__).resolve().parent.parent / 'host-settings.json')
    parser.add_argument('--server-id')
    parser.add_argument('--command', default='status')
    parser.add_argument('--quiet', action='store_true')
    args = parser.parse_args()
    try:
        if args.action == 'info':
            print(json.dumps(info(args.port), indent=2))
        else:
            settings = json.loads(args.settings.read_text(encoding='utf-8-sig'))
            if args.server_id:
                server = next((item for item in settings.get('servers', []) if item.get('id') == args.server_id), None)
                if not server:
                    raise ValueError('Server id not found in settings: ' + args.server_id)
                password = server['rcon_password']
            else:
                password = settings['rcon_password']
            output = rcon(args.port, password, 'status' if args.action == 'probe' else args.command)
            if args.action == 'probe' and not re.search(r'map\s*:\s+\S+', output):
                raise ValueError('Game has not loaded a map or RCON credentials are incorrect')
            if not args.quiet:
                print(output)
    except (OSError, ValueError) as exc:
        if not args.quiet:
            print(str(exc))
        raise SystemExit(1) from exc
