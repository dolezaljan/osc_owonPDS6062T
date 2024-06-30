# tested on Owon TAO3122 Oscilloscope
# https://files.owon.com.cn/software/Application/XDS3000_and_XDS2000_Dual-Channel_Series_Oscilloscopes_SCPI_Protocol.pdf
import usb.core
import usb.util

import json
import array

class OwonPDS6062T:
    sample_bits = 8

    def __init__(self):
        self._dev = usb.core.find(idVendor=0x5345, idProduct=0x1234) # set PC mode on oscilloscope # Owon PDS6062T Oscilloscope

        if self._dev is None:
            raise ValueError('Device not found')
        else:
            #print(self._dev)
            self._dev.set_configuration()

    def _flush_Bulk_IN(self):
        result = array.array('B')
        try:
            while True:
                result.extend(self._dev.read(0x81,2000000,50))
        except usb.core.USBTimeoutError:
            return result

    def _send(self, cmd):
        self._flush_Bulk_IN() # << XXX this might actually not be necessary, but in case the response to query was not read fully, the code might crash (because of reading stale data)
        # address taken from results of print(dev):   ENDPOINT 0x3: Bulk OUT
        self._dev.write(3,cmd)
        if (type(cmd) is str and cmd[-1] != '?') or (type(cmd) is bytes and cmd[-1] != b'?'[0]):
            return
        # address taken from results of print(dev):   ENDPOINT 0x81: Bulk IN
        result = (self._dev.read(0x81,2000000,3000))
        if (not self._query_begins_with_4B_msg_length(str(cmd)) or
                (type(cmd) is str and cmd[0] == '*') or
                (type(cmd) is bytes and cmd[0] == b'*'[0])):
            return result
        expected_data_len=int.from_bytes(result[:4], 'little', signed=False)
        try:
            while len(result)-4 < expected_data_len:
                result.extend(self._dev.read(0x81,2000000,3000))
        except usb.core.USBTimeoutError as err:
            print(err)
        if len(result)-4 != expected_data_len:
            print(f'ERROR: received {len(result)-4}, expected {expected_data_len}; flushing Bulk IN')
            print(f'flushed {len(self._flush_Bulk_IN())}')
            raise Exception(f"data lengths mismatch: expected {expected_data_len} received {len(result)-4}")
        return result

    def _query_begins_with_4B_msg_length(self, request: str):
        '''
        defines which of the queries include at the beginning of their response length field

        message response:
        [ length | 4B 'little endian' ]
        [ body   | size defined by length field ]
        '''
        return (request.startswith(":DATA:WAVE:") or
                request.startswith(":MEASUrement:CH") or
                request == ":MEASUrement:ALL?")
    
    def query(self, request: str):
        '''
        query command

        Parameters
        ----------
        request : str
            query command to be executed by the oscilloscope

        Returns
        -------
        str response
        '''
        return self._send(request).tobytes().decode('utf-8')
    
    def write(self, cmd: str):
        '''
        execute command

        Parameters
        ----------
        cmd : str
            command to be executed by the oscilloscope
        '''
        self._dev.write(3,cmd)
    
    def get_id(self, ):
        return self.query('*IDN?')

    @classmethod
    def raw_sample_buffer_to_ints(cls, rawsamples: array.array):
        '''
        rawsamples as returned by ':DATA:WAVE:SCREen:CHx' without the length header
        '''
        # data are 8 bit only contrary to the docs that states 12 bit - take only every other byte from the rawsamples
        # convert unsigned 8-bit int to signed one
        return map(lambda x: int.from_bytes([x], signed=True), rawsamples[1::2])
    
    def get_data(self, ch: int):
        '''
        samples as signed integers in given bit range OwonPDS6062T.sample_bits
        cf. osc_plot pt_to_screen() to convert data to the screen points for osci curves reconstruction
        use get_header() in order to interpret data relative to channel's OFFSET and SCALE

        Parameters
        ----------
        ch : int
            get data for this channel

        Returns
        -------
        array[float] signed int data in bit range OwonPDS6062T.sample_bits
        '''
        try:
            rawdata = self._send(':DATA:WAVE:SCREen:CH{}?'.format(ch))
        except Exception as ex:
            print(f"get_data: {ex}; retrying ...")
            rawdata = self._send(':DATA:WAVE:SCREen:CH{}?'.format(ch))
        data = []

        return self.raw_sample_buffer_to_ints(rawdata[4:])
    
    def get_bmp(self, file_name = None):
        '''
        note this call can take quite some time to complete (~3s)

        Parameters
        ----------
        file_name : str
            path to file where to store the bitmap

        Returns
        -------
        raw binary bitmap data
        '''
        try:
            rawdata = self._send(':DATA:WAVE:SCREen:BMP?')
        except Exception as ex:
            print(f"get_bmp: {ex}; retrying ...")
            rawdata = self._send(':DATA:WAVE:SCREen:BMP?')
        if file_name:
            with open(file_name,'wb') as f:
                f.write(rawdata[4:])
        # first 4 bytes indicate the number of data bytes following
        return rawdata[4:]
    
    def get_header(self, ):
        '''
        Returns
        -------
        json with currently set parameters in the oscilloscope
        '''
        try:
            header = self._send(':DATA:WAVE:SCREen:HEAD?')
        except Exception as ex:
            print(f"get_header: {ex}; retrying ...")
            header = self._send(':DATA:WAVE:SCREen:HEAD?')
        # first 4 bytes indicate the number of data bytes following
        header = header[4:].tobytes().decode('utf-8')
        return json.loads(header)
    
    def save_data(self, file_name, data):
        with open(file_name, 'w') as f:
            f.write('\n'.join(map(str, data)))
