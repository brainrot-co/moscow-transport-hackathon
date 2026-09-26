import argparse
import logging

from mtml.clock import load_clock
from mtml.storage import Volume
from mtml.worker.settings import WorkerSettings
from mtml.worker.short import run_short

log = logging.getLogger("mtml.worker")


def main():
    parser = argparse.ArgumentParser(description="Прогноз по фактам из общего тома")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("once", help="посчитать краткосрочный прогноз, опубликовать и завершиться")
    parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    volume, settings = Volume.from_env(), WorkerSettings.from_env()
    clock = load_clock(volume.clock)
    log.info("Том %s, сейчас по часам системы %s", volume.root, clock.now())
    run_short(volume, settings, clock.now())


if __name__ == "__main__":
    main()
