#!/usr/bin/python3
import http.server
import os
import os.path
import socketserver
import argparse

from http import HTTPStatus
from netifaces import interfaces, ifaddresses, AF_INET

from zipfile import ZipFile
from io import BytesIO

# globals
shared_data = None
shared_data_filename = None

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
    

def main():
    global shared_data, shared_data_filename
    parser = argparse.ArgumentParser(description='shares files (or directories) over http')
    parser.add_argument('--port', default=9999, help='port to share on')
    parser.add_argument('path', nargs=1, help='path to share')
    
    args = parser.parse_args()
    assert len(args.path) == 1
    path = args.path[0]
    shared_data_filename, shared_data = get_data_to_serve(path)

    ip_addresses = filter_ip_addresses(ip4_addresses())

    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(('', args.port), Handler) as httpd:
        if ip_addresses:
            for addr in ip_addresses:
                print(f'serving on http://{addr}:{args.port}')
        else:
            print(f'serving on port {args.port} (failed to guess IP)')
        httpd.serve_forever()

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
