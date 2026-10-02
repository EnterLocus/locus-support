"""Serve the real staged site for preview and parallel browser checks."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class PreviewServer(ThreadingHTTPServer):
    # Parallel browsers open several sockets per page. The standard small
    # accept queue can reset module/style requests during simultaneous loads.
    request_queue_size = 128


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=4186)
    parser.add_argument('--directory', type=Path, default=Path(__file__).resolve().parents[1] / '.site')
    args = parser.parse_args()
    handler = partial(SimpleHTTPRequestHandler, directory=str(args.directory))
    with PreviewServer(('127.0.0.1', args.port), handler) as server:
        server.serve_forever()


if __name__ == '__main__':
    main()
