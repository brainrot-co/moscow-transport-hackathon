import argparse
import logging
import sys
import time
from pathlib import Path

from mtml.clock import load_clock, real_now
from mtml.ingest.pipeline import ingest_file, process_inbox, refresh_status
from mtml.ingest.seed import apply_seed, seed_dir
from mtml.ingest.settings import IngestSettings
from mtml.storage import Volume

log = logging.getLogger("mtml.ingest")


def main():
    parser = argparse.ArgumentParser(description="Приём выгрузок валидаций в общий том")
    commands = parser.add_subparsers(dest="command", required=True)
    load = commands.add_parser("load", help="загрузить указанные файлы, не перемещая их")
    load.add_argument("files", nargs="+", type=Path)
    commands.add_parser("once", help="обработать всё, что лежит в inbox/, и завершиться")
    commands.add_parser("run", help="опрашивать inbox/ раз в INGEST_POLL_SEC секунд")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    volume, settings = Volume.from_env(), IngestSettings.from_env()
    volume.inbox.mkdir(parents=True, exist_ok=True)
    clock = load_clock(volume.clock)
    log.info("Том %s, сейчас по часам системы %s", volume.root, clock.now())

    if args.command == "load":
        records = [ingest_file(path, volume, settings, clock.now()) for path in args.files]
        mark = refresh_status(volume, settings, clock.now())
        log.info("Водяной знак: %s", mark)
        sys.exit(1 if any(r.status == "failed" for r in records) else 0)
    if args.command == "once":
        process_inbox(volume, settings, clock.now())
        return
    apply_seed(volume, seed_dir(), settings, clock.now(), real_now())
    while True:
        process_inbox(volume, settings, clock.now())
        time.sleep(settings.poll_sec)


if __name__ == "__main__":
    main()
