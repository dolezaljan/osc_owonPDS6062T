#!/usr/bin/env python3
import os
import sys
import argparse
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from live_dump import DataProcessor
import matplotlib.pyplot as plt
from osc_plot import Plotter, to_screen

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
        help="Display matplotlib instead of writing out corresponding jpg file. Arrow keys allow to navigate to neighboring files.",
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

    # init plot
    plotter = Plotter()
    ch1_color = "#eed807"
    ch2_color = "#67c7ff"
    fig_ax = plotter.init_plot([ch1_color, ch2_color])
    fig, ax = fig_ax

    ln1, = plt.plot([], [], color=ch1_color)
    ln2, = plt.plot([], [], color=ch2_color)
    lines = [ln1, ln2]

    def plot_file(f: str):
        with open(f, 'rb') as dat_file:
            data=dat_file.read()
        proc.load_dump_obj(data)

        ax.set_title(f[:-4], y=1.04)

        head_json = json.loads(proc.head[5:])
        ch1_data = to_screen(DataProcessor.samples_to_ints(proc.ch1_data[5:]), 8)
        ch2_data = to_screen(DataProcessor.samples_to_ints(proc.ch2_data[5:]), 8)

        plotter.apply_head(head_json)

        x_data_pts_range = plotter.get_x_pts_range()
        if ch1_data:
            lines[0].set_data(x_data_pts_range, ch1_data) if ch1_data else None
        if ch2_data:
            lines[1].set_data(x_data_pts_range, ch2_data) if ch2_data else None

    for f in files_to_process:
        plot_file(f)

        if pargs.view:
            all_files = files_to_process
            next_f = f
            def nav(event):
                global next_f
                if event.key == 'right':
                    next_f = all_files[(all_files.index(next_f) + 1)%len(all_files)]
                elif event.key == 'left':
                    next_f = all_files[(all_files.index(next_f) - 1)%len(all_files)]
                else:
                    return
                plot_file(next_f)
                plt.show()
            fig.canvas.mpl_connect('key_press_event', nav)
            if not os.path.isdir(pargs.file):
                print("loading all neighboring files: use left <- and right -> arrow keys to navigate")
                f_dir = os.path.dirname(f)
                all_files = sorted(map(lambda p: f_dir+'/'+p, os.listdir(f_dir)))
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
