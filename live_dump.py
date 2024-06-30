#!/usr/bin/env python3
import os
import sys
import argparse
import signal
import json
from datetime import datetime

from typing import Callable

from websocket import create_connection

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from units import scale_to_float
from relay_srv import WS_TYPES, DEFAULT_PORT
DEFAULT_HOST="localhost"
DEFAULT_DUMP_DIR="dump"

class LiveReceiver:
    def __init__(self, host, port):
        self.host = host
        self.port = port

    def start(self, cb_on_data: Callable[[object], None], should_continue: Callable = lambda: True):
        target = f'ws://{self.host}:{self.port}/updates_ws'
        print(f"connecting to oscilloscope relay on '{target}")
        ws = create_connection(target)
        while should_continue():
            rawdata = ws.recv()
            if not len(rawdata):
                print('ws disconnected ... exiting')
                break
            cb_on_data(rawdata)
        ws.close()

class DataProcessor():
    def __init__(self):
        self.head = None
        self.ch1_data = None
        self.ch2_data = None

    def store_live_data(self, new_data):
        if WS_TYPES(new_data[0]).name == 'HEAD':
            self.head = new_data
        elif WS_TYPES(new_data[0]).name == 'CH1_DATA':
            self.ch1_data = new_data
        elif WS_TYPES(new_data[0]).name == 'CH2_DATA':
            self.ch2_data = new_data

    def make_dump_obj(self, ):
        return self.head+self.ch1_data+self.ch2_data

    def load_dump_obj(self, data):
        while data:
            fld_len = int.from_bytes(data[1:5], 'little', signed=False)+1+4 # 1: type, 4: len
            self.store_live_data(data[:fld_len])
            data = data[fld_len:]

    @staticmethod
    def samples_to_ints(rawsamples: bytes, bytes_per_sample: int = 1, little_endian: bool = False):
        return map(lambda x: int.from_bytes(x, 'little' if little_endian else 'big', signed=True), [rawsamples[i:i+bytes_per_sample] for i in range(0, len(rawsamples), bytes_per_sample)])

    @staticmethod
    def map_screen_data_point_to_range(screen_point: int, target_range: int, point_bits: int = 8):
        '''
        screen_point - python int (not the original byte encoded sample -- cf. samples_to_ints())
        point_bits - what range may screen_point consist of
        target_range - new range: half negative, half poisitive

        Example:
        point_bits: 8
        target_range: 500
            <-128; 128) -> <-250; 250)
        '''
        return (screen_point+2**(point_bits-1))*target_range/2**point_bits - target_range/2

    def get_real_values(self, channel: int):
        '''
        convert rawdata where each point represents height on the screen <-128; 127> to
        the voltage using channel OFFSET within HEAD's CHANNEL desc that states where is
        zero on the screen <-250; 250> or where it is beyond the screen

        50 OFFSET points is one division; tenth of division is stored in SCALE within HEAD's CHANNEL desc
        '''
        if channel not in range(1,3):
            raise Exception('only channels {list(range(1,3)} are allowed')

        head=json.loads(self.head[5:].decode('utf-8'))
        rawdata = self.ch1_data if channel == 1 else self.ch2_data
        chan = head['CHANNEL'][channel-1]

        RANGE_OF_OFFSET_ON_THE_SCREEN=500
        return list(map(lambda x: (DataProcessor.map_screen_data_point_to_range(x, target_range=RANGE_OF_OFFSET_ON_THE_SCREEN, point_bits=8)-chan['OFFSET'])*scale_to_float(chan['SCALE'])/5, DataProcessor.samples_to_ints(rawdata[5:])))

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Display current oscilloscope curves as forwarded by target relay.")
    parser.add_argument(
        "-t",
        "--host",
        help="Host of the oscilloscope relay.",
        type=str,
        nargs='?',
        default=DEFAULT_HOST,
    )
    parser.add_argument(
        "-p",
        "--port",
        help="Port of the oscilloscope relay.",
        type=int,
        nargs='?',
        default=DEFAULT_PORT,
    )
    parser.add_argument(
        "-d",
        "--dir",
        help="Directory where to dump the raw snapshots.",
        type=str,
        nargs='?',
        default=DEFAULT_DUMP_DIR,
    )
    return parser

exit_app = False
if __name__ == "__main__":
    parser = build_parser()
    pargs = parser.parse_args(sys.argv[1:])

    def _sig_exit(signum, frame):
        global exit_app
        print("Exiting ...")
        exit_app = True
    signal.signal(signal.SIGINT, _sig_exit)
    signal.signal(signal.SIGTERM, _sig_exit)
    def should_continue():
        global exit_app
        return not exit_app

    rcvr = LiveReceiver(pargs.host, pargs.port)
    proc = DataProcessor()

    try:
        os.mkdir(pargs.dir)
    except Exception:
        pass

    global dump_count
    dump_count = 0
    def store_data(new_data):
        global dump_count
        proc.store_live_data(new_data)
        # presume each time CH2_DATA comes, all necessary data were received for the dump to be complete
        LAST_MESSAGE = 'CH2_DATA'
        if WS_TYPES(new_data[0]).name == LAST_MESSAGE:
            ts = datetime.now().strftime('%Y-%m-%d_%H-%M-%S.%f)')[:-4]
            with open(f"{pargs.dir}/{dump_count:08}_{ts}.dat", 'wb') as dump_file:
                dmp = proc.make_dump_obj()
                dump_file.write(dmp)
            dump_count += 1

    rcvr.start(store_data, should_continue)
