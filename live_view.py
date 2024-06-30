#!/usr/bin/env python3
import os
import sys
import argparse
import json

import multiprocessing, multiprocessing.connection

from matplotlib.animation import FuncAnimation
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from relay_srv import DEFAULT_PORT, WS_TYPES
from osc_plot import Plotter
from live_dump import LiveReceiver, DataProcessor
DEFAULT_HOST="localhost"

ch1_color="#eed807"
ch2_color="#67c7ff"

head_json = None
ch1_data = []
ch2_data = []
def plot_cont(consumer_conn: multiprocessing.connection.Connection):
    plotter = Plotter()
    fig, ax = plotter.init_plot([ch1_color, ch2_color])

    # Define data ranges
    x_data_pts_range = plotter.get_x_pts_range()

    ln1, = plt.plot([], [], color=ch1_color)
    ln2, = plt.plot([], [], color=ch2_color)
    lines = [ln1, ln2]

    def on_new_head():
        plotter.apply_head(head_json)
        plt.draw()

    def init():
        on_new_head()
        return lines
    def update(frame):
        global ch1_data
        global ch2_data
        global head_json
        #print(f"update {frame}")
        while consumer_conn.poll():
            d=consumer_conn.recv()
            if d['type'] == 'HEAD':
                head_json = d['data']
                on_new_head()
            elif d['channel'] == 1:
                ch1_data = d['data']
            elif d['channel'] == 2:
                ch2_data = d['data']
            else:
                print(f"unknown data received {d['type']} {d['channel']}")
        if not head_json or head_json['CHANNEL'][0]['DISPLAY'] == 'OFF':
            lines[0].set_data([], [])
        else:
            lines[0].set_data(x_data_pts_range, ch1_data) if ch1_data else None
        if not head_json or head_json['CHANNEL'][1]['DISPLAY'] == 'OFF':
            lines[1].set_data([], [])
        else:
            lines[1].set_data(x_data_pts_range, ch2_data) if ch2_data else None
        return lines

    ani = FuncAnimation(fig, update, cache_frame_data=False, interval=30, init_func=init, blit=True)
    plt.show()

def process_data_received(rawdata: bytes):
    if rawdata[0] == 0:
        data=json.loads(rawdata[5:].decode('utf-8'))
    else:
        channel=rawdata[0]
        MAJOR_SCREEN_DIVISION=10
        data=list(map(lambda x: DataProcessor.map_screen_data_point_to_range(x, MAJOR_SCREEN_DIVISION, 8), DataProcessor.samples_to_ints(rawdata[5:])))
    return {'type': WS_TYPES(rawdata[0]).name, 'channel': rawdata[0], 'data': data}

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
    return parser

if __name__ == "__main__":
    parser = build_parser()
    pargs = parser.parse_args(sys.argv[1:])

    producer_conn, consumer_conn = multiprocessing.Pipe()
    p = multiprocessing.Process(target=plot_cont, args=(consumer_conn,))
    p.start()

    def pass_to_consumer(rawdata):
        producer_conn.send(process_data_received(rawdata))
    rcvr = LiveReceiver(pargs.host, pargs.port)
    rcvr.start(pass_to_consumer, p.is_alive)

    p.join()
