#!/usr/bin/env python3
import os
import sys
import argparse
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from live_dump import DataProcessor
from osc_plot import construct_pyplot, to_screen

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Relay updates from oscilloscope and commands to it over network. Allows to have multiple clients connected to single osci.")
    parser.add_argument(
        "file",
        help="Dump file to be reconstructed as oscilloscope screen data. If dir is passed all the relevant data in the dir are converted to image.",
        type=str,
    )
    parser.add_argument(
        "-o",
        "--out_dir",
        help="Set output directory. When not specified, the same dir as source will be used.",
        type=str,
        nargs="?",
        default=None,
    )
    parser.add_argument(
        "-v",
        "--view",
        help="Display matplotlib instead of writing out corresponding jpg file.",
        action="store_true"
    )
    return parser

if __name__ == "__main__":
    parser = build_parser()
    pargs = parser.parse_args(sys.argv[1:])

    proc = DataProcessor()
    files_to_process = []
    if os.path.isdir(pargs.file):
        for root, dir_, files in os.walk(pargs.file):
            files_to_process.extend(map(lambda f: root+f, filter(lambda f: f.endswith('.dat'), files)))
    else:
        files_to_process.append(pargs.file)

    for f in files_to_process:
        with open(f, 'rb') as dat_file:
            data=dat_file.read()
        proc.load_dump_obj(data)

        plt = construct_pyplot(
                json.loads(proc.head[5:]),
                to_screen(DataProcessor.samples_to_ints(proc.ch1_data[5:]), 8),
                to_screen(DataProcessor.samples_to_ints(proc.ch2_data[5:]), 8),
                f[:-4],
                )

        if pargs.view:
            plt.show()
        else:
            target_file = f[:-3]+'jpg'
            if pargs.out_dir:
                try:
                    os.mkdir(pargs.out_dir)
                except Exception:
                    pass
                target_file = pargs.out_dir + '/' + target_file.split('/')[-1]
            print(f"Storing to {target_file}")
            plt.savefig(target_file)
