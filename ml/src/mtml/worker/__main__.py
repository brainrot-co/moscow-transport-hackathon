import argparse
import logging

from mtml.clock import load_clock
from mtml.storage import Volume
from mtml.worker.schedule import run_forever
from mtml.worker.settings import WorkerSettings
from mtml.worker.short import run_short
from mtml.worker.year import run_year

log = logging.getLogger("mtml.worker")


def main():
    parser = argparse.ArgumentParser(description="Прогноз по фактам из общего тома")
    commands = parser.add_subparsers(dest="command", required=True)
    once = commands.add_parser("once", help="посчитать прогноз, опубликовать и завершиться")
    once.add_argument("--kind", choices=["short", "year", "all"], default="all")
    commands.add_parser("run", help="цикл: пересчёт при сдвиге водяного знака и ночью")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    volume, settings = Volume.from_env(), WorkerSettings.from_env()
    clock = load_clock(volume.clock)
    log.info("Том %s, сейчас по часам системы %s", volume.root, clock.now())
    if args.command == "run":
        run_forever(volume, settings, clock)
        return
    if args.kind in ("short", "all"):
        run_short(volume, settings, clock.now())
    if args.kind in ("year", "all"):
        run_year(volume, settings, clock.now())


if __name__ == "__main__":
    main()
