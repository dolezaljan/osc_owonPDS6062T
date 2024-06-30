import os
import sys

import numpy as np
import matplotlib
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from units import scale_to_float, float_to_scale
from live_dump import DataProcessor

class Plotter():
    def __init__(self):
        self.head_objs = []

        # Define number of squares in each direction
        self.num_x = 15.2
        self.num_y = 10

        # Define number of minor ticks per square (including center)
        self.minor_ticks = 5

        # Define conversion ratio between unit of oscilloscope reported offset and displayed division
        self.offset_to_div_conv=0.02

    def init_plot(self, channels_colors: list):
        self.channels_colors = channels_colors

        # Create the figure
        self.fig_ax = plt.subplots(figsize=(self.num_x, self.num_y))  # Adjust figsize for better visualization
        fig, ax = self.fig_ax
        self.ax2 = ax.twinx()

        # Set x and y limits considering minor ticks (adjusted for spacing)
        x_max = self.num_x / 2
        x_min = -x_max
        y_max = self.num_y / 2
        y_min = -y_max

        # Set limits for the axes
        ax.set_xlim(x_min, x_max)
        ax.set_ylim(y_min, y_max)
        self.ax2.set_ylim(y_min, y_max)

        # Set minor ticks on axes only (using locators)
        ax.set_xticks(np.arange(x_min, x_max + (self.minor_ticks - 1) / (self.num_x * 2), (x_max - x_min) / (self.num_x * self.minor_ticks)), minor=True)
        ax.set_yticks(np.arange(y_min, y_max + (self.minor_ticks - 1) / (self.num_y * 2), (y_max - y_min) / (self.num_y * self.minor_ticks)), minor=True)
        ax.tick_params(which='both', top=True, right=True, labelbottom=False)
        self.ax2.tick_params(axis="y", colors=self.channels_colors[1])
        ax.tick_params(axis="y", colors=self.channels_colors[0])

        # Draw grid lines based on major ticks
        ax.grid(which='major', linestyle='-', linewidth=0.5, color='gray')

        return self.fig_ax

    def apply_head(self, head_json):
        for o in self.head_objs:
            o.remove()
        self.head_objs = []
        fig, ax = self.fig_ax

        x_min, x_max = ax.get_xlim()
        y_min, y_max = ax.get_ylim()
        # Define major tick positions (every square)
        major_ticks_x = range(int(x_min), int(x_max)+1)
        major_ticks_y = range(int(y_min), int(y_max)+1)
        # Construct bases for channels and trigger
        ch1_offset=self.offset_to_div_conv*int(head_json['CHANNEL'][0]['OFFSET']) if head_json else 0
        ch1_offset_lim=max(min(ch1_offset, y_max+0.005), y_min-0.005)
        ch2_offset=self.offset_to_div_conv*int(head_json['CHANNEL'][1]['OFFSET']) if head_json else 0
        ch2_offset_lim=max(min(ch2_offset, y_max+0.005), y_min-0.005)

        ch1_scale=scale_to_float(head_json['CHANNEL'][0]['SCALE'])*10 if head_json else 0
        ch2_scale=scale_to_float(head_json['CHANNEL'][1]['SCALE'])*10 if head_json else 0

        # Set major ticks
        ax.set_xticks(major_ticks_x)
        ax.set_yticks(major_ticks_y, labels=map(lambda x: "{:.1f}".format((x-ch1_offset)*ch1_scale), major_ticks_y), weight="bold")
        self.ax2.set_yticks(major_ticks_y, labels=map(lambda x: "{:.1f}".format((x-ch2_offset)*ch2_scale), major_ticks_y), weight="bold")

        if head_json:
            # show timebase info
            ti = plt.text(0.70, 1.03, f"Timebase: Scale {head_json['TIMEBASE']['SCALE']}, Offset {head_json['TIMEBASE']['HOFFSET']}", transform=ax.transAxes, fontsize=14,
                    verticalalignment='top')
            self.head_objs.extend([ti])

            if head_json['CHANNEL'][1]['DISPLAY'] == 'ON':
                # Show base of channel 2
                a2 = ax.annotate('', xy=(x_min, ch2_offset_lim), xytext=(-40, 0), verticalalignment="center", textcoords="offset points",
                            arrowprops=dict(facecolor=self.channels_colors[1], width=12, headwidth=12, edgecolor="black" if ch2_offset == ch2_offset_lim else "gray"),
                            )
                t2 = plt.text(x_min-0.5, ch2_offset_lim, '2', verticalalignment='center', fontweight="bold" if ch2_offset == ch2_offset_lim else "normal", fontstyle="normal" if ch2_offset == ch2_offset_lim else "italic", color="black" if ch2_offset == ch2_offset_lim else "gray")

                # Show description of channel 2
                d2 = plt.text(0.08, -0.03, f"2:\n{float_to_scale(ch2_scale)}", transform=ax.transAxes, fontsize=14,
                        verticalalignment='top', bbox=dict(color=self.channels_colors[1]))
                self.head_objs.extend([a2, t2, d2])

            if head_json['CHANNEL'][0]['DISPLAY'] == 'ON':
                # Show base of channel 1
                a1 = ax.annotate('', xy=(x_min, ch1_offset_lim), xytext=(-20, 0), verticalalignment="center", textcoords="offset points",
                            arrowprops=dict(facecolor=self.channels_colors[0], width=12, headwidth=12, edgecolor="black" if ch1_offset == ch1_offset_lim else "gray"),
                            )
                t1 = plt.text(x_min-0.3, ch1_offset_lim, '1', verticalalignment='center', fontweight="bold" if ch1_offset == ch1_offset_lim else "normal", fontstyle="normal" if ch1_offset == ch1_offset_lim else "italic", color="black" if ch1_offset == ch1_offset_lim else "gray")

                # Show description of channel 1
                d1 = plt.text(0.00, -0.03, f"1:\n{float_to_scale(ch1_scale)}", transform=ax.transAxes, fontsize=14,
                        verticalalignment='top', bbox=dict(color=self.channels_colors[0]))
                self.head_objs.extend([a1, t1, d1])

            if head_json['Trig']['Sweep'] != 'AUTO':
                # show triggers
                tr=head_json['Trig']
                trig_ch=tr['Items']['Channel']
                trig_off = ch1_offset_lim if trig_ch == 'CH1' else ch2_offset_lim + scale_to_float(tr['Items']['Level']) / (ch1_scale if trig_ch == 'CH1' else ch2_scale)

                style = matplotlib.patches.ArrowStyle('Fancy', head_length=2, head_width=1.5, tail_width=0.0001)
                #style = matplotlib.patches.ArrowStyle('Wedge', tail_width=1.5, shrink_factor=0.5)
                at = ax.annotate('', xy=(x_max, trig_off), xytext=(40, 0), textcoords="offset points", va="center",
                            arrowprops=dict(facecolor=self.channels_colors[0] if trig_ch == 'CH1' else self.channels_colors[1], arrowstyle=style, linewidth=0.2),
                            )
                # Show description of the trigger
                tt = plt.text(0.85, -0.03, f"{trig_ch}:{tr['Items']['Coupling']}:{tr['Items']['Edge']} {tr['Items']['Level']}", transform=ax.transAxes, fontsize=14,
                        verticalalignment='top', bbox=dict(edgecolor=self.channels_colors[1], facecolor='none'))

                self.head_objs.extend([at, tt])

    def get_x_pts_range(self, ):
        x_min, x_max = self.fig_ax[1].get_xlim()
        return list(map(lambda x: x/100, range(int(x_min*100), int(x_max*100))))

def to_screen(ch_data, bits, screen_major_divisions_count=10):
    return list(map(lambda pt: DataProcessor.map_screen_data_point_to_range(pt, screen_major_divisions_count, bits), ch_data))

def construct_pyplot(head_json: object, ch1_data: [float] = None, ch2_data: [float] = None, title: str = None) -> plt:
    '''
    Example of usage with OwonPDS6062T:
        from owonPDS6062T import OwonPDS6062T
        from osc_plot import construct_pyplot, to_screen
        o=OwonPDS6062T()

        plt = construct_pyplot(o.get_header(), to_screen(o.get_data(1), o.sample_bits), to_screen(o.get_data(2), o.sample_bits))

        # save to file
        plt.savefig('out.jpg')

        # display plot
        plt.show()
    '''
    ch1_color="#eed807"
    ch2_color="#67c7ff"
    plotter = Plotter()
    fig, ax = plotter.init_plot([ch1_color, ch2_color])

    # Set title (optional)
    if title:
        ax.set_title(title)

    plotter.apply_head(head_json)

    x_data_pts_range = plotter.get_x_pts_range()
    if ch1_data:
        plt.plot(x_data_pts_range, ch1_data, color=ch1_color)
    if ch2_data:
        plt.plot(x_data_pts_range, ch2_data, color=ch2_color)

    return plt
