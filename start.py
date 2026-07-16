import os
import socket
import webbrowser
import threading
import time
import sys

def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

def main():
    if getattr(sys, 'frozen', False):
        os.chdir(os.path.dirname(sys.executable))
    else:
        os.chdir(os.path.dirname(os.path.abspath(__file__)))

    if is_port_in_use(8080):
        print("[WARNING] Port 8080 is already in use.")
        print("          Please close the previous NPE window (Ctrl+C) and try again.")
        print()
        input("Press Enter to exit...")
        sys.exit(1)

    from app import app, init_db
    init_db()

    def open_browser():
        time.sleep(1.5)
        webbrowser.open('http://localhost:8080')

    threading.Thread(target=open_browser, daemon=True).start()
    print("Server running at http://localhost:8080")
    app.run(host='0.0.0.0', port=8080, debug=False)

if __name__ == '__main__':
    main()