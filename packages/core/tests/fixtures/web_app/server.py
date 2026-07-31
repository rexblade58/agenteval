"""Fixture: minimal web app for browser verification tests.

Serves a page with known text and no console errors. Simulates what a
starter web app fixture would provide.
"""

import http.server
import socketserver

PAGE = """<!DOCTYPE html>
<html>
<head><title>Fixture Shop</title></head>
<body>
  <h1 id="checkout-title">Checkout</h1>
  <p>Total: $54.00</p>
</body>
</html>
"""


class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/", "/checkout"):
            body = PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_error(404)


def main():
    with socketserver.TCPServer(("127.0.0.1", 8765), Handler) as httpd:
        print("serving on 127.0.0.1:8765", flush=True)
        httpd.serve_forever()


if __name__ == "__main__":
    main()
