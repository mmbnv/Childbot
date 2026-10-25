"""HTTP service exposing a fly-brain decision endpoint.

Run it where the heavy model lives (a GPU box, or next to an installed
fly-brain checkout) and point Childbot at it with ``CHILDBOT_FLYBRAIN_URL``:

    python -m childbot.service --host 0.0.0.0 --port 8077

Endpoints
---------
``GET  /health``  -> ``{"status": "ok", "engine": "...", "neurons": N}``
``POST /decide``  -> body ``{"situation": "...", "intensity": 1.0, "duration_ms": 100}``
                     returns the :class:`~childbot.brain.BrainReading` as JSON.

The service uses only the standard library, so it runs in the same environment
as the model without adding a web framework dependency.
"""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from childbot.config import BrainConfig


class _Handler(BaseHTTPRequestHandler):
    engine = None  # set by serve()

    def log_message(self, *args):  # keep the console quiet
        pass

    def _send(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 (http.server API)
        if self.path == "/health":
            self._send(
                200,
                {
                    "status": "ok",
                    "engine": type(self.engine).__name__,
                    "neurons": getattr(self.engine, "n_neurons", None),
                },
            )
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/decide":
            self._send(404, {"error": "not found"})
            return
        length = int(self.headers.get("Content-Length", 0))
        try:
            request = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._send(400, {"error": "invalid JSON"})
            return

        try:
            reading = self.engine.decide(
                request.get("situation", ""),
                intensity=float(request.get("intensity", 1.0)),
                duration_ms=float(request.get("duration_ms", 100.0)),
            )
        except Exception as exc:  # surface engine errors to the caller
            self._send(500, {"error": str(exc)})
            return

        self._send(
            200,
            {
                "decision": reading.decision,
                "confidence": reading.confidence,
                "simulated_ms": reading.simulated_ms,
                "note": reading.note,
                "channels": {
                    name: {"rate_hz": ch.rate_hz, "spikes": ch.spikes}
                    for name, ch in reading.channels.items()
                },
            },
        )


def build_engine(args):
    """Pick the engine for the service based on CLI flags and the environment."""
    if args.flybrain_home:
        from childbot.bridge import FlyBrainBridge

        return FlyBrainBridge(home=args.flybrain_home, config=BrainConfig())
    from childbot.brain import FlyBrain

    config = BrainConfig()
    if args.subset_size:
        config = config.with_(subset_size=args.subset_size)
    return FlyBrain(config, download=not args.no_download)


def serve(host: str, port: int, engine) -> None:
    _Handler.engine = engine
    server = ThreadingHTTPServer((host, port), _Handler)
    print(f"childbot fly-brain service on http://{host}:{port} ({type(engine).__name__})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Childbot fly-brain HTTP service")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8077)
    parser.add_argument("--subset-size", type=int, default=None,
                        help="Use only the N most-connected neurons (fast runs)")
    parser.add_argument("--no-download", action="store_true",
                        help="Require connectome data to already be present")
    parser.add_argument("--flybrain-home", default=None,
                        help="Serve an installed fly-brain checkout instead of the local engine")
    args = parser.parse_args(argv)

    engine = build_engine(args)
    serve(args.host, args.port, engine)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
