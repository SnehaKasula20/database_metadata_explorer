import sys
import uvicorn
from database_metadata_explorer import DatabaseMetadataExplorer


def start_web_server(port: int = 8000):
    print("\n" + "=" * 60)
    print(f"   STARTING DATABASE METADATA EXPLORER WEB SERVER")
    print(f"   URL: http://localhost:{port}")
    print("=" * 60 + "\n")
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)


def main():
    if len(sys.argv) > 1 and sys.argv[1].lower() in {"--web", "-w", "web"}:
        start_web_server()
        return

    print("\n========================================")
    print("     DATABASE METADATA EXPLORER")
    print("========================================")
    print("1. Launch Web User Interface (http://localhost:8000)")
    print("2. Run Command-Line Interface (CLI)")
    print()

    choice = input("Select mode [1-2] (default: 1): ").strip()

    if choice in {"2", "cli"}:
        explorer = DatabaseMetadataExplorer()
        explorer.run()
    else:
        start_web_server()


if __name__ == "__main__":
    main()