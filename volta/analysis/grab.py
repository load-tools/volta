from __future__ import print_function
import serial
import json
import argparse
import progressbar
import logging
import time

logger = logging.getLogger(__name__)


class Grabber(object):
    def __init__(self):
        self.samplerate = 10000

    def grab_binary_10k(self, args):
        with serial.Serial(args['device'], 230400, timeout=1) as ser:
            logger.info("Waiting for synchronization line...")
            while ser.readline() != "VOLTAHELLO\n":
                pass
            params = json.loads(ser.readline())
            self.samplerate = params["sps"]
            logger.info("Synchronization successful. Sample rate: %d", self.samplerate)

            logger.info(
                "Collecting %d seconds of data (%d samples) to '%s'." % (
                    args['seconds'], args['seconds'] * self.samplerate, args['output']))
            while ser.readline() != "DATASTART\n":
                pass
            with open(args['output'], "wb") as out:
                with progressbar.ProgressBar(max_value=args['seconds']) as bar:
                    for i in range(args['seconds']):
                        bar.update(i)
                        out.write(ser.read(self.samplerate * 2))

def run():
    parser = argparse.ArgumentParser(description='Grab data from measurement device.')
    parser.add_argument(
        '-i', '--device',
        default="/dev/cu.wchusbserial1410",
        help='Arduino device serial port')
    parser.add_argument(
        '-s', '--seconds',
        default=60,
        type=int,
        help='number of seconds to collect')
    parser.add_argument(
        '-o', '--output',
        default="output.bin",
        help='file to store the results')
    parser.add_argument(
        '-d', '--debug',
        help='enable debug logging',
        action='store_true')
    args = vars(parser.parse_args())
    main(args)


def main(args):
    logging.basicConfig(
        level="DEBUG" if args.get('debug') else "INFO",
        format='%(asctime)s [%(levelname)s] [grabber] %(filename)s:%(lineno)d %(message)s')
    logger.info("Volta data grabber.")
    grabber = Grabber()
    grabber.grab_binary_10k(args)
    return grabber


if __name__ == '__main__':
    run()
