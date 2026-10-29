import argparse
from .gateway import run_gateway_server

def main():
    parser = argparse.ArgumentParser(description="AdaptiveAgentRouter OpenAI-Compatible Reverse Proxy Server")
    parser.add_argument("--host", default="0.0.0.0", help="Binding host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on (default: 8000)")
    args = parser.parse_args()

    run_gateway_server(host=args.host, port=args.port)

if __name__ == "__main__":
    main()
