#!/usr/bin/env python3
"""
Lightweight Mock n8n Webhook Receiver
Simulates n8n webhook endpoint behavior for local end-to-end verification.
"""
import http.server
import json
import socketserver
import sys

PORT = 8088

class MockN8nHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length)

        print("\n" + "=" * 60)
        print(f" [MOCK n8n] Captured Webhook Request on: {self.path}")
        print("=" * 60)
        print("--- HTTP Headers ---")
        for key, value in self.headers.items():
            if key.startswith("X-") or key == "Content-Type":
                print(f"  {key}: {value}")

        print("\n--- Payload JSON ---")
        try:
            parsed = json.loads(post_data.decode("utf-8"))
            print(json.dumps(parsed, indent=2))
        except Exception as exc:
            print(f"Failed to parse JSON ({exc}): {post_data}")

        # Simulate status codes based on path
        if "fail404" in self.path:
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "error", "message": "Workflow disabled or not found"}')
            print("\n [MOCK n8n] Responded with HTTP 404 (Workflow disabled or not found)\n")
        elif "fail500" in self.path:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "error", "message": "Internal Server Error"}')
            print("\n [MOCK n8n] Responded with HTTP 500\n")
        else:
            # Standard n8n success response
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            response_body = json.dumps({
                "accepted": True,
                "message": "Event accepted for notification dispatch."
            }).encode("utf-8")
            self.wfile.write(response_body)
            print("\n [MOCK n8n] Responded with HTTP 200 OK (Webhook captured successfully)\n")

    def log_message(self, format, *args):
        # Suppress standard logging to keep output clean
        pass

def run():
    with socketserver.TCPServer(("127.0.0.1", PORT), MockN8nHandler) as httpd:
        print(f"Mock n8n Webhook server listening on http://127.0.0.1:{PORT} ...")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down Mock n8n server.")

if __name__ == "__main__":
    run()
