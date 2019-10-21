#!/usr/bin/python3
import http.server
import os
import os.path
import socketserver
import argparse

from http import HTTPStatus

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

def main():
    global shared_data, shared_data_filename
    parser = argparse.ArgumentParser(description='shares files (or directories) over http')
    parser.add_argument('--port', default=8394, help='port to share on')
    parser.add_argument('path', nargs=1, help='path to share')
    
    args = parser.parse_args()
    path = args.path[0]
    shared_data = open(path, 'rb').read()
    shared_data_filename = os.path.basename(path)

    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(('', args.port), Handler) as httpd:
        print(f'serving on port {args.port}')
        httpd.serve_forever()

if __name__ == '__main__':
    main()
