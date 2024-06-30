#!/usr/bin/env python3
import os
import sys
import argparse
import asyncio
import tornado, tornado.websocket
import signal
from enum import Enum
import json

import usb.core
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from owonPDS6062T import OwonPDS6062T

DEFAULT_PORT=7997

class WS_TYPES(Enum):
    HEAD = 0
    CH1_DATA = 1
    CH2_DATA = 2

class RelayServer(tornado.web.Application):
    def __init__(self, osci_instance_getter):
        handlers=[
            (r'/updates_ws', OsciUpdatesWebsocket, {'osci_instance_getter': osci_instance_getter}),
            (r'/query', RestApi, {'osci_instance_getter': osci_instance_getter}),
            (r'/write', RestApi, {'osci_instance_getter': osci_instance_getter}),
        ]
        super().__init__(handlers)

class OsciUpdatesWebsocket(tornado.websocket.WebSocketHandler):
    clients = set()
    new_cli = False
    osci_instance_getter=None
    o=None

    @classmethod
    def enum_osci(cls):
        osci = cls.osci_instance_getter()
        if cls.o != osci:
            cls.o = osci

    def initialize(self, osci_instance_getter):
        if OsciUpdatesWebsocket.osci_instance_getter != osci_instance_getter:
            OsciUpdatesWebsocket.osci_instance_getter = osci_instance_getter
            OsciUpdatesWebsocket.enum_osci()

    async def open(self):
        print(f"> opened WS connection from {self.request.connection.context.address} to {self.request.host}")
        OsciUpdatesWebsocket.clients.add(self)
        await asyncio.sleep(0)
        OsciUpdatesWebsocket.new_cli = True # go through Queue instead to account for each new client?

    def on_message(self, message):
        print(f"> WS msg from {self.request.connection.context.address}: {message}")

    def on_close(self):
        print(f"> closed WS connection from {self.request.connection.context.address} to {self.request.host}")
        OsciUpdatesWebsocket.clients.remove(self)
        if not OsciUpdatesWebsocket.clients:
            print('> waiting for WS clients')

    @classmethod
    async def broadcast_screen_updates(cls, should_exit):
        print('> waiting for WS clients')
        last_header = ""
        while not should_exit():
            clis=cls.clients.copy()
            if not clis:
                await asyncio.sleep(0.5)
                continue
            await asyncio.sleep(0)
            try:
                header=cls.o._send(':DATA:WAVE:SCREen:HEAD?')
                if last_header != header or cls.new_cli:
                    for ws in clis:
                        try:
                            ws.write_message(bytes([WS_TYPES.HEAD.value])+header, binary = True)
                        except tornado.websocket.WebSocketClosedError as err:
                            pass
                    last_header = header
                    cls.decoded_header = json.loads(bytes(last_header[4:]).decode('utf-8').strip())
                    cls.displayed_channels = { int(x['NAME'][-1]) : x['DISPLAY'] for x in cls.decoded_header['CHANNEL'] }
                    cls.new_cli = False
                for ch in range(1,3):
                    if cls.displayed_channels[ch] == 'OFF':
                        continue
                    chan_data=cls.o._send(':DATA:WAVE:SCREen:CH{}?'.format(ch))
                    rawdata = chan_data[4:][1::2] # 8-bit only ... strip away byte that is always 0 within each sample
                    for ws in clis:
                        try:
                            ws.write_message(bytes([WS_TYPES(ch).value])+int(len(rawdata)).to_bytes(4, 'little')+rawdata, binary = True)
                        except tornado.websocket.WebSocketClosedError as err:
                            pass
            except usb.core.USBError as err:
                await asyncio.sleep(1)
                cls.enum_osci()
        for ws in cls.clients.copy():
            ws.close()

class RestApi(tornado.web.RequestHandler):
    osci_instance_getter=None

    def initialize(self, osci_instance_getter):
        self.osci_instance_getter = osci_instance_getter

    def post(self):
        #print(f"POST from {self.request.connection.context.address}: {self.request.body}")
        if self.request.path == '/query':
            if self.request.body[-1] != b'?'[0]:
                self.set_status(400)
                self.finish('{"error":"Query has to end with \'?\'. Did you mean to use \'/write\' path?"}')
                return
            self.write(bytes(self.osci_instance_getter()._send(self.request.body)))
            self.set_header('Content-Type', 'application/octet-stream')
        elif self.request.path == '/write':
            if self.request.body[-1] == b'?'[0]:
                self.set_status(400)
                self.finish('{"error":"Write should not end with \'?\'. Did you mean to use \'/query\' path?"}')
                return
            self.osci_instance_getter().write(self.request.body)

class OsciRelayApp():
    exit_app = False

    def __init__(self):
        self.o = OwonPDS6062T()
        signal.signal(signal.SIGINT, self._sig_exit)
        signal.signal(signal.SIGTERM, self._sig_exit)

    def _sig_exit(self, signum, frame):
        self.exit_app = True

    def should_exit(self):
        return self.exit_app

    def get_osci_instance(self):
        return self.o

    async def osci_reconnector(self):
        while True:
            await asyncio.sleep(1)
            if not usb.core.find(idVendor=self.o._dev.idVendor, idProduct=self.o._dev.idProduct):
                print('> waiting for oscilloscope to be reconnected')
                while True:
                    try:
                        self.o = OwonPDS6062T()
                        print('> oscilloscope reconnected')
                        break
                    except Exception:
                        pass

    async def start(self, port):
        asyncio.create_task(self.osci_reconnector())

        srv = RelayServer(self.get_osci_instance)
        print(f'> listening on port {port}')
        srv.listen(port)

        await OsciUpdatesWebsocket.broadcast_screen_updates(self.should_exit)

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Relay updates from oscilloscope and commands to it over network. Allows to have multiple clients connected to single osci.")
    parser.add_argument(
        "-p",
        "--port",
        help="TCP port where the relay serves requests.",
        type=int,
        nargs='?',
        default=DEFAULT_PORT,
    )
    return parser

if __name__ == "__main__":
    parser = build_parser()
    pargs = parser.parse_args(sys.argv[1:])
    app = OsciRelayApp()
    asyncio.run(app.start(pargs.port))
