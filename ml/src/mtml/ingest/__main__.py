import argparse
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from mtml.ingest.pipeline import ingest_file, process_inbox, refresh_status
from mtml.ingest.settings import IngestSettings
from mtml.storage import Volume

log = logging.getLogger("mtml.ingest")


def moscow_now():
    # все времена в данных — московские без смещения, а часы контейнера могут быть в UTC
    return datetime.now(ZoneInfo("Europe/Moscow")).replace(tzinfo=None, microsecond=0)


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
    log.info("Том %s", volume.root)

    if args.command == "load":
        records = [ingest_file(path, volume, settings, moscow_now()) for path in args.files]
        mark = refresh_status(volume, settings, moscow_now())
        log.info("Водяной знак: %s", mark)
        sys.exit(1 if any(r.status == "failed" for r in records) else 0)
    if args.command == "once":
        process_inbox(volume, settings, moscow_now())
        return
    while True:
        process_inbox(volume, settings, moscow_now())
        time.sleep(settings.poll_sec)


if __name__ == "__main__":
    main()
