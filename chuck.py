#!/usr/bin/python3
import http.server
import os
import os.path
import socketserver
import argparse
import socket
import sys
import threading

from http import HTTPStatus
from netifaces import interfaces, ifaddresses, AF_INET

from zipfile import ZipFile
from io import BytesIO
from contextlib import suppress


# conts
MAGIC_GREETING = b'hello chuckers'
UDP_PORT = 37101

# globals
shared_data = None
shared_data_filename = None
done_running = False

class Handler(http.server.BaseHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        self.directory = os.path.abspath(os.path.dirname(os.path.realpath(__file__)) + '/../')
        super().__init__(*args, **kwargs)

    def do_GET(self):
        global shared_data

        self.send_response(HTTPStatus.OK)
        self.send_header('Content-type', 'binary/octet-stream')
        self.send_header('Content-Disposition', f'attachment; filename="{shared_data_filename}"')
        self.end_headers()

        self.wfile.write(shared_data)

def get_data_to_serve(path):
    if os.path.isfile(path):
        return os.path.basename(path), open(path, 'rb').read()

    path = os.path.abspath(path)
    basename = os.path.basename(path)
    attachment_name = basename + '.zip'
 
    in_memory = BytesIO()
    zf = ZipFile(in_memory, mode="w")

    for dir_path, subdirs, files in os.walk(path, topdown=False):
        for fname in files:
            zippath = f'{dir_path}/{fname}'
            fullpath = os.path.join(path, zippath)

            # dont expose system path in zip file
            assert zippath.startswith(path)
            zippath = zippath[len(path):]
            assert zippath.startswith('/')
            zippath = basename + zippath

            zf.writestr(zippath, open(fullpath, 'rb').read())

    zf.close()

    in_memory.seek(0)
    return attachment_name, in_memory.read()


def listen_broadcast(name, http_port):
    global done_running

    serv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # UDP
    serv.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    serv.bind(('', UDP_PORT))
    serv.settimeout(0.1)

    while not done_running:
        with suppress(socket.timeout):
            data, (client_ip, client_port) = serv.recvfrom(1024)
            if data == MAGIC_GREETING:
                msg = f'{http_port} {name}'.encode('utf8')
                serv.sendto(msg, (client_ip, client_port))
                print(f'replied to UDP discover {client_ip}:{client_port}')


def discover_others():
    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    client.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    client.sendto(MAGIC_GREETING, ('<broadcast>', UDP_PORT))
    client.settimeout(0.2)

    results = set()

    with suppress(socket.timeout):
        while True:
            data, (client_ip, client_port) = client.recvfrom(1024)
            port, fname = data.decode('utf8').split(' ', 1)
            results.add((fname, f'http://{client_ip}:{port}'))

    results = sorted([x for x in results])
    for name, url in results:
        print(f'{name} - {url}')


def main():
    global shared_data, shared_data_filename, done_running
    parser = argparse.ArgumentParser(description='shares files (or directories) over http')
    parser.add_argument('-l', '--list', action='store_true', help='discover chuckers on the local network')
    parser.add_argument('--port', default=9999, type=int, help='port to share on')
    parser.add_argument('path', nargs='?', help='path to share')

    args = parser.parse_args()
    if args.list:
        return discover_others()

    if args.path is None:
        print('missing path argument')
        sys.exit(1)

    shared_data_filename, shared_data = get_data_to_serve(args.path)

    ip_addresses = filter_ip_addresses(ip4_addresses())

    udp_listener = threading.Thread(target = listen_broadcast, args = (shared_data_filename, args.port))
    udp_listener.start()

    with suppress(KeyboardInterrupt):
        socketserver.TCPServer.allow_reuse_address = True
        with socketserver.TCPServer(('', args.port), Handler) as httpd:
            if ip_addresses:
                for addr in ip_addresses:
                    print(f'serving on http://{addr}:{args.port}')
            else:
                print(f'serving on port {args.port} (failed to guess IP)')
            httpd.serve_forever()

    done_running = True
    udp_listener.join()

def ip4_addresses():
    ip_list = []
    for interface in interfaces():
        ifs = ifaddresses(interface)
        for link in ifs.get(AF_INET, []):
            ip_list.append(link['addr'])
    return ip_list

def filter_ip_addresses(ip_list):
    def ignored(x):
        if x.startswith('127.'):
            return True
        if x.startswith('172.'):
            return True
        return False
    return [x for x in ip_list if not ignored(x)]

if __name__ == '__main__':
    main()
