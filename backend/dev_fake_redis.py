import traceback
from pathlib import Path

from fakeredis import TcpFakeServer


if __name__ == "__main__":
    log_path = Path(__file__).resolve().parent.parent / ".tmp" / "fake-redis-runtime.log"
    with log_path.open("a", encoding="utf-8") as log_file:
        log_file.write("Starting fake Redis helper\n")
        log_file.flush()
        try:
            server = TcpFakeServer(("127.0.0.1", 6379))
            print("Fake Redis listening on 127.0.0.1:6379", flush=True)
            log_file.write("Fake Redis listening on 127.0.0.1:6379\n")
            log_file.flush()
            server.serve_forever()
        except Exception:
            traceback.print_exc(file=log_file)
            log_file.flush()
            raise
