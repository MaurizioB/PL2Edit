#!/usr/bin/env python2.7
# *-* coding: utf-8 *-*

import struct
from pyalsa import alsaseq
#import alsaseq
from time import *
from PyQt4 import QtCore


class Const(object):
    pass
INPUT, OUTPUT = [Const() for i in range(2)]

_PortTypeMaskList = sorted(alsaseq._dporttype.values())
_PortCapsMaskList = sorted(alsaseq._dportcap.values())[1:]
_PortTypeStrings = {}
_PortCapsStrings = {}
_ClientTypeStrings = {}

for desc, value in alsaseq.__dict__.items():
    if desc in ['SEQ_USER_CLIENT', 'SEQ_KERNEL_CLIENT']:
        _ClientTypeStrings[int(value)] = desc[4:].replace('_', ' ').capitalize()
    elif desc.startswith('SEQ_PORT_CAP_'):
        _PortCapsStrings[int(value)] = desc[13:].replace('_', ' ').capitalize()
    elif desc.startswith('SEQ_PORT_TYPE_'):
        _PortTypeStrings[int(value)] = desc[14:].replace('_', ' ').capitalize()

def get_port_type(mask):
    t_list = []
    for t in _PortTypeMaskList:
        if t > mask:
            break
        if mask & t == t:
            t_list.append(t)
    return t_list

def get_port_caps(mask):
    if mask == 0:
        return [alsaseq.SEQ_PORT_CAP_NONE]
    c_list = []
    for c in _PortCapsMaskList:
        if c > mask:
            break
        if mask & c == c:
            c_list.append(c)
    return c_list


class NamedFlag(int):
    """
    An integer type where each value has a name attached to it.
    """
    def __new__(cls, value, name):
        return int.__new__(cls, value)
    def __init__(self, value, name):
        self.name = name
    def __getnewargs__(self):
        return (int(self), self.name)
    def __repr__(self):
        return self.name
    def __str__(self):
        return self.name


class NamedBitMask(NamedFlag):
    """
    Like NamedFlag, but bit operations | and ~ are also reflected in the
    resulting value's string representation.
    """
    def __or__(self, other):
        if type(other) is not type(self):
            return NotImplemented
        return type(self)(
            int(self) | int(other),
            '%s|%s' % (self.name, other.name)
        )
    def __invert__(self):
        return type(self)(
            ~int(self) & ((1 << 30) - 1),
            ('~%s' if '|' not in self.name else '~(%s)') % self.name
        )

class _EventType(NamedBitMask):
    pass

_event_types_raw = {
#                       id: (alsa, internal)
                        0: ('NONE', 'NONE'),
                        1: ('NOTEON', 'NOTEON'),
                        2: ('NOTEOFF', 'NOTEOFF'),
                        3: ('NOTE', 'NOTE'),
                        4: ('CONTROLLER', 'CTRL'),
                        8: ('PITCHBEND', 'PITCHBEND'),
                        16: ('CHANPRESS', 'AFTERTOUCH'),
                        32: ('KEYPRESS', 'POLY_AFTERTOUCH'),
                        64: ('PGMCHANGE', 'PROGRAM'),
                        128: ('SYSEX', 'SYSEX'),
                        256: ('QFRAME', 'SYSCM_QFRAME'),
                        512: ('SONGPOS', 'SYSCM_SONGPOS'),
                        1024: ('SONGSEL', 'SYSCM_SONGSEL'),
                        2048: ('TUNE_REQUEST', 'SYSCM_TUNEREQ'),
#                        3840: 'SYSCM',
                        4096: ('CLOCK', 'SYSRT_CLOCK'),
                        8192: ('START', 'SYSRT_START'),
                        16384: ('CONTINUE', 'SYSRT_CONTINUE'),
                        32768: ('STOP', 'SYSRT_STOP'),
                        65536: ('SENSING', 'SYSRT_SENSING'),
                        131072: ('RESET', 'SYSRT_RESET'),
#                        258048: 'SYSRT',
                        262016: ('SYSTEM', 'SYSTEM'),
#                        536870912: 'DUMMY',
                        1073741823: ('USR0', 'ANY'), 
                        }

_event_type_names = {}
_event_type_values = {}
_event_type_alsa = {}
_event_type_toalsa = {}
for v, (alsa_str, name) in _event_types_raw.items():
    _type_obj = _EventType(v, name)
    globals()[name] = _type_obj
    _event_type_names[name] = _type_obj
    _event_type_values[v] = _type_obj
    _alsa_event = getattr(alsaseq, 'SEQ_EVENT_{}'.format(alsa_str))
    _event_type_alsa[int(_alsa_event)] = _type_obj
    _event_type_toalsa[_type_obj] = _alsa_event

_bits_to_event = {
                  0x8: NOTEOFF, 
                  0x9: NOTEON, 
                  0xa: POLY_AFTERTOUCH, 
                  0xb: CTRL, 
                  0xc: PROGRAM, 
                  0xd: AFTERTOUCH, 
                  0xe: PITCHBEND, 
                  0xf: SYSEX, 
                  }

_event_to_bits = {v:k for k, v in _bits_to_event.items()}

_note_names = {0: 'c', 1: 'c#', 2: 'd', 3: 'd#', 4: 'e', 5: 'f', 6: 'f#', 7: 'g', 8: 'g#', 9: 'a', 10: 'a#', 11: 'b',}

WhiteKeys = []
BlackKeys = []
for n in range(128):
    if n%12 in [1, 3, 6, 8, 10]:
        BlackKeys.append(n)
    else:
        WhiteKeys.append(n)

def _make_property(type, data, name=None):
    def getter(self):
        self._check_type_attribute(type, name)
        return getattr(self, data)
    def setter(self, value):
        self._check_type_attribute(type, name)
        setattr(self, data, value)
    return property(getter, setter)

class MidiEvent(object):
    def __init__(self, event_type=None, port=0, channel=0, data1=0, data2=0, sysex=None, event=None):
        if event:
            self._event = event
            self.port = int(event.dest[1])
            self._type = _event_type_alsa[int(event.type)]
            data = event.get_data()
            self.queue = 0
            if self._type in [NOTEON, NOTEOFF, POLY_AFTERTOUCH]:
                self.channel = data['note.channel']
                self.data1 = data['note.note']
                self.data2 = data['note.velocity']
                self._sysex = None
            elif self._type == CTRL:
                self.channel = data['control.channel']
                self.data1 = data['control.param']
                self.data2 = data['control.value']
                self._sysex = None
            elif self._type in [PROGRAM, AFTERTOUCH, PITCHBEND]:
                self.channel = data['control.channel']
                self.data1 = 0
                self.data2 = data['control.value']
                self._sysex = None
            elif self._type == SYSEX:
                self.channel = 0
                self.data1 = self.data2 = 0
                self._sysex = data['ext']
            elif self._type == SYSTEM:
                self.channel = 0
                self.data1 = data['result.event']
                self.data2 = data['result.result']
                self._sysex = None
            elif self._type in [SYSRT_START, SYSRT_CONTINUE, SYSRT_STOP]:
                self.channel = 0
                self.data1 = self.data2 = 0
                self.queue = data['queue.queue']
                self._sysex = None
            else:
                self.channel = 0
                self.data1 = self.data2 = 0
                self._sysex = None
        else:
            if not event_type in _event_type_values.values():
                raise ValueError('There\'s no such event type as {}'.format(event_type))
            self._type = event_type
            self.port = port
            self.channel = channel
            self.data1 = data1
            self.data2 = data2
            self._sysex = sysex
            self.queue = 0
            self._event = None

    def _check_type_attribute(self, type, name):
        if not self.type & type:
            message = ('MidiEvent type \'{ev}\' has no attribute \'{t}\''.format(ev=self.type, t=name))
            raise AttributeError(message)

    __rstr = {
              NOTEON: '{cls}(port={p}, channel={c}, note={d1}, velocity={d2})', 
              NOTEOFF: '{cls}(port={p}, channel={c}, note={d1}, velocity={d2})', 
              CTRL: '{cls}(port={p}, channel={c}, param={d1}, value={d2})', 
              SYSEX: '{cls}(port={p}, channel={c}, sysex={x})', 
              PROGRAM: '{cls}(port={p}, channel={c}, program={d2})', 
              POLY_AFTERTOUCH: '{cls}(port={p}, channel={c}, note={d1}, value={d2})', 
              AFTERTOUCH: '{cls}(port={p}, channel={c}, value={d2})', 
              PITCHBEND: '{cls}(port={p}, channel={c}, value={d2})',  
              SYSCM_QFRAME: '{cls}(port={p}, data={d1})', 
              SYSCM_SONGPOS: '{cls}(port={p}, data={d1})', 
              SYSCM_SONGSEL: '{cls}(port={p}, data={d1})', 
              SYSCM_TUNEREQ: '{cls}(port={p}, data={d1})', 
              SYSRT_RESET: '{cls}(port={p}, data={d1})', 
              SYSRT_SENSING: '{cls}(port={p}, data={d1})', 
              SYSRT_CLOCK: '{cls}(port={p}, data={d1})', 
              SYSRT_START: '{cls}(port={p}, data={d1})', 
              SYSRT_CONTINUE: '{cls}(port={p}, data={d1})', 
              SYSRT_STOP: '{cls}(port={p}, data={d1})', 
              }

    __tstr = {
              NOTEON: 'NoteOnEvent', 
              NOTEOFF: 'NoteOffEvent', 
              CTRL: 'CtrlEvent', 
              SYSEX: 'SysExEvent', 
              PROGRAM: 'ProgramEvent', 
              POLY_AFTERTOUCH: 'PolyAftertouchEvent', 
              AFTERTOUCH: 'AftertouchEvent', 
              PITCHBEND: 'PitchbendEvent', 
              SYSCM_QFRAME: 'SysCmQFrameEvent', 
              SYSCM_SONGPOS: 'SysCmSongPositionEvent', 
              SYSCM_SONGSEL: 'SysCmSongSelectionEvent', 
              SYSCM_TUNEREQ: 'SysCmTuneRequestEvent', 
              SYSRT_RESET: 'SysRtResetEvent', 
              SYSRT_SENSING: 'SysRtSensingEvent', 
              SYSRT_CLOCK: 'SysRtClockEvent', 
              SYSRT_START: 'SysRtStartEvent', 
              SYSRT_CONTINUE: 'SysRtContinueEvent', 
              SYSRT_STOP: 'SysRtStopEvent', 
              }

    @property
    def type(self):
        return self._type

    @type.setter
    def type(self, event_type):
        if event_type not in _event_type_values.values():
            raise ValueError('{} is not a valid MIDI Event Type'.format(event_type))
        self._event = None
        self._type = event_type

    note = _make_property(NOTE | POLY_AFTERTOUCH,
                          'data1', 'note')

    velocity  = _make_property(NOTE, 'data2', 'velocity')

    ctrl = _make_property(CTRL, 'data1', 'ctrl')

    value = _make_property(CTRL | PITCHBEND | AFTERTOUCH | POLY_AFTERTOUCH, 'data2', 'value')

    program = _make_property(PROGRAM, 'data2', 'program')

    @property
    def sysex(self):
        return self._sysex

    @sysex.setter
    def sysex(self, sysex):
        try:
            if isinstance(sysex, str):
                self._sysex = [int(byte, 16) for byte in sysex.split()]
                return
            [hex(byte) for byte in sysex]
            self._sysex = sysex
        except:
            raise ValueError('String {} is not a valid SysEx string'.format(sysex))

    def get_event(self):
        if not self._event:
            self._event = alsaseq.SeqEvent(_event_type_toalsa[self._type])
            if self._type in [NOTEON, NOTEOFF, POLY_AFTERTOUCH]:
                data = {'note.channel': self.channel, 'note.note': self.data1, 'note.velocity': self.data2}
                self._event.set_data(data)
            elif self._type == CTRL:
                data = {'control.channel': self.channel, 'control.param': self.data1, 'control.value': self.data2}
                self._event.set_data(data)
            elif self._type in [PROGRAM, AFTERTOUCH, PITCHBEND]:
                print self.channel
                data = {'control.channel': self.channel, 'control.value': self.data2}
                self._event.set_data(data)
            elif self._type == SYSEX:
                data = {'ext': self._sysex}
                self._event.set_data(data)
            elif self._type == SYSTEM:
                data = {'result.event': self.data1, 'result.result': self.data2}
                self._event.set_data(data)
            elif self._type in [SYSRT_START, SYSRT_CONTINUE, SYSRT_STOP]:
                data = {'queue.queue': self.queue}
                self._event.set_data(data)
        return self._event

    def _get_jack_event_type(self, value):
        found = False
        for bit, event_type in _bits_to_event.items():
            if value >> 4 == bit:
                found = True
                break
        if not found:
            raise Exception('WTF?! value: {}'.format(value))
        return event_type, value & 0xf

    @classmethod
    def from_jack(cls, port, event):
        event = struct.unpack('{}B'.format(len(event)), event)
        event_type, channel = self._get_jack_event_type(event[0])
        if len(event) == 2:
            return cls(event_type, port, channel, data2=event[1])
        elif len(event) == 3:
            return cls(event_type, port, channel, data1=event[1], data2=event[2])
        else:
            return cls(event_type, port, sysex=event)

    @classmethod
    def jack_event(cls, event_type, port, channel=0, data1=0, data2=0, sysex=None):
        return

    @classmethod
    def from_alsa(cls, event):
        #TODO: controlla che non sia meglio usare cls
        return MidiEvent(event=event)    

    @classmethod
    def alsa_event(cls, event_type, port, channel=0, data1=0, data2=0, sysex=None):
        event = alsaseq.SeqEvent(_event_type_toalsa[event_type])
        if event_type in [NOTEON, NOTEOFF, POLY_AFTERTOUCH]:
            data = {'note.channel': channel, 'note.note': data1, 'note.velocity': data2}
            event.set_data(data)
        elif event_type == CTRL:
            data = {'control.channel': channel, 'control.param': data1, 'control.value': data2}
            event.set_data(data)
        elif event_type in [PROGRAM, AFTERTOUCH, PITCHBEND]:
            data = {'control.channel': channel, 'control.value': data2}
            event.set_data(data)
        elif event_type == SYSEX:
            data = {'ext': sysex}
            event.set_data(data)
        elif event_type == SYSTEM:
            data = {'result.event': data1, 'result.result': data2}
            event.set_data(data)
        event.source = (0, port)
        return event

    def __repr__(self):
        return self.__rstr[self.type].format(cls=self.__tstr[self._type],
                                  p=self.port, c=self.channel,
                                  d1=self.data1, d2=self.data2, x=self.sysex)

class NoteOnEvent(MidiEvent):
    def __new__(self, port, channel, note, velocity):
        return MidiEvent(NOTEON, port, channel, note, velocity)

    @classmethod
    def alsa_event(cls, port, channel, note, velocity):
        return MidiEvent.alsa_event(NOTEON, port, channel, note, velocity)

class NoteOffEvent(MidiEvent):
    def __new__(self, port, channel, note, velocity):
        return MidiEvent(NOTEOFF, port, channel, note, velocity)

    @classmethod
    def alsa_event(cls, port, channel, note, velocity):
        return MidiEvent.alsa_event(NOTEOFF, port, channel, note, velocity)

class CtrlEvent(MidiEvent):
    def __new__(self, port, channel, param, value):
        return MidiEvent(CTRL, port, channel, param, value)

    @classmethod
    def alsa_event(cls, port, channel, param, value):
        return MidiEvent.alsa_event(CTRL, port, channel, param, value)

class ProgramEvent(MidiEvent):
    def __new__(self, port, channel, program):
        return MidiEvent(PROGRAM, port, channel, None, program)

    @classmethod
    def alsa_event(cls, port, channel, program):
        return MidiEvent.alsa_event(PROGRAM, port, channel, None, program)

class PitchbendEvent(MidiEvent):
    def __new__(self, port, channel, value):
        return MidiEvent(PITCHBEND, port, channel, None, value)

    @classmethod
    def alsa_event(cls, port, channel, value):
        return MidiEvent.alsa_event(PITCHBEND, port, channel, None, value)

class SysExEvent(MidiEvent):
    def __new__(self, port, sysex):
        return MidiEvent(SYSEX, port, None, None, None, sysex)

    @classmethod
    def alsa_event(cls, port, sysex):
        return MidiEvent.alsa_event(SYSEX, port, None, None, None, sysex)

class SysRtResetEvent(MidiEvent):
    def __new__(self, port):
        return MidiEvent(SYSRT_RESET, port, None, None, None)

    @classmethod
    def alsa_event(cls, port):
        return MidiEvent.alsa_event(SYSRT_RESET, port, None, None, None)

class ConnList(object):
    def __init__(self, port, output=None, input=None):
        self.port = port
        self.input = [] if input is None else input
        self.output = [] if output is None else output

    def __iter__(self):
        for conn in self.input+self.output:
            yield conn

    def __len__(self):
        return len(self.input+self.output)

    def __repr__(self):
        return 'Input: {}\nOutput: {}'.format(self.input, self.output)

    def append(self, conn):
        if self.port.is_duplex:
            if conn.src==conn.dest:
                if not conn in self.input:
                    self.input.append(conn)
                #check for errors
                elif not conn in self.output:
                    self.output.append(conn)
            else:
                if self.port == conn.src and not conn in self.output:
                    self.output.append(conn)
                elif not conn in self.input:
                    self.input.append(conn)
        elif self.port.is_input and not conn in self.input:
            self.input.append(conn)
        elif not conn in self.output:
            self.output.append(conn)

    def remove(self, conn):
        try:
            self.input.remove(conn)
        except:
            try:
                self.output.remove(conn)
            except:
                pass

class Connection(object):
    lost = QtCore.pyqtSignal()
    def __init__(self, graph, src, dest, show=True):
        self.graph = graph
        self.seq = graph.seq
        self.src = src
        self.dest = dest
        self.hidden = not show
        self.info = self.seq.get_connect_info(src.addr, dest.addr)
        self.exclusive = self.info.get('exclusive', 0)
        self.queue = self.info.get('queue', 0)
        self.time_real = self.info.get('time_real', 0)
        self.time_update = self.info.get('time_update', 0)

    def __eq__(self, other):
        if not isinstance(other, Connection):
            return False
        if self.src == other.src and self.dest == other.dest:
            return True
        return False

    def __repr__(self):
        try:
            self.seq.get_connect_info(self.src.addr, self.dest.addr)
            return 'Conn ({}:{}) > ({}:{})'.format(self.src.client.id, self.src.id, self.dest.client.id, self.dest.id)
#            return 'Connection {}:{} ({}:{}) > {}:{} ({}:{})'.format(self.src.client.name, self.src.name, self.src.client.id, self.src.id,
#                                                                     self.dest.client.name, self.dest.name, self.dest.client.id, self.dest.id)
        except alsaseq.SequencerError:
            self.graph.conn_deleted(self)
            return '(destroyed)'

class Port(QtCore.QObject):
    connection = QtCore.pyqtSignal(object, object)
    disconnection = QtCore.pyqtSignal(object, object)
    def __init__(self, client, port_id):
        QtCore.QObject.__init__(self)
        self.client = client
        self.graph = client.graph
        self.seq = self.client.seq
        self.id = port_id
        self.addr = (self.client.id, self.id)
        self.exp = '{}:{}'.format(*self.addr)
        self.info_dict = self.seq.get_port_info(self.id, self.client.id)
        self.name = self.info_dict['name']
        self.caps = get_port_caps(self.info_dict['capability'])
        self.type = get_port_type(self.info_dict['type'])
        if not len(self.type) or alsaseq.SEQ_PORT_CAP_NO_EXPORT in self.caps:
            self.hidden = True
        else:
            self.hidden = False
        self.is_input = self.is_output = False
        if alsaseq.SEQ_PORT_CAP_DUPLEX in self.caps:
            self.is_input = self.is_output = True
        else:
            #TODO trova un modo più veloce per trovare il tipo di porta, qui generi ogni volta 2 set
            if set([int(t) for t in [alsaseq.SEQ_PORT_CAP_READ, alsaseq.SEQ_PORT_CAP_SYNC_READ, alsaseq.SEQ_PORT_CAP_SUBS_READ]]) & set([int(t) for t in self.caps]):
                self.is_output = True
            if set([int(t) for t in [alsaseq.SEQ_PORT_CAP_WRITE, alsaseq.SEQ_PORT_CAP_SUBS_WRITE, alsaseq.SEQ_PORT_CAP_SUBS_WRITE]]) & set([int(t) for t in self.caps]):
                self.is_input = True
        if self.is_input and self.is_output:
            self.is_duplex = True
        else:
            self.is_duplex = False
        self.connections = ConnList(self)

    def connect(self, dest, port=None):
        if isinstance(dest, tuple):
            dest = self.graph.port_id_dict[dest[0]][dest[1]]
        elif port is not None and isinstance(dest, int) and isinstance(port, int):
            dest = self.graph.port_id_dict[dest][port]
        if (self.is_input and not dest.is_output) and (self.is_output and not dest.is_input):
            return
        if (self.is_duplex and dest.is_duplex) or self.is_output:
            try:
                self.seq.connect_ports(self.addr, dest.addr)
            except alsaseq.SequencerError:
                return False
            return True
        try:
            self.seq.connect_ports(dest.addr, self.addr)
            return True
        except alsaseq.SequencerError:
            return False

    def disconnect(self, dest, port=None):
        if isinstance(dest, tuple):
            dest = self.graph.port_id_dict[dest[0]][dest[1]]
        elif port is not None and isinstance(dest, int) and isinstance(port, int):
            dest = self.graph.port_id_dict[dest][port]
        if (self.is_input and not dest.is_output) and (self.is_output and not dest.is_input):
            return
        if (self.is_duplex and dest.is_duplex) or self.is_output:
            try:
                self.seq.disconnect_ports(self.addr, dest.addr)
                return
            except alsaseq.SequencerError:
                print 'Disconnection {} > {} not permitted'.format(self.exp, dest.exp)
                return
        try:
            self.seq.disconnect_ports(dest.addr, self.addr)
        except alsaseq.SequencerError:
            print 'Disconnection {} > {} not permitted'.format(dest.exp, self.exp)
            return

    def disconnect_all(self, dir=None, skip_hidden=True):
        if not dir:
            for conn in self.graph.get_port_connections(self):
                if skip_hidden and conn.hidden:
                    continue
                try:
                    self.seq.disconnect_ports(conn.src.addr, conn.dest.addr)
                except alsaseq.SequencerError:
                    print 'Disconnection {} > {} not permitted'.format(conn.src.exp, conn.dest.exp)
        else:
            if not self.is_duplex and ((dir == OUTPUT and not self.is_output) or (dir == INPUT and not self.is_input)):
                return
            if dir == OUTPUT:
                for conn in self.connections.output:
                    if skip_hidden and conn.hidden:
                        continue
                    try:
                        self.seq.disconnect_ports(conn.src.addr, conn.dest.addr)
                    except alsaseq.SequencerError:
                        print 'Disconnection {} > {} not permitted'.format(conn.src.exp, conn.dest.exp)
            else:
                for conn in self.connections.input:
                    if skip_hidden and conn.hidden:
                        continue
                    try:
                        self.seq.disconnect_ports(conn.src.addr, conn.dest.addr)
                    except alsaseq.SequencerError:
                        print 'Disconnection {} > {} not permitted'.format(conn.src.exp, conn.dest.exp)

    @property
    def type_str(self):
        return [_PortTypeStrings[int(t)] for t in self.type]

    @property
    def caps_str(self):
        return [_PortCapsStrings[int(c)] for c in self.caps]

    def __repr__(self):
        return 'Port "{}" ({}:{})'.format(self.name, self.client.id, self.id)

class Client(QtCore.QObject):
    port_start = QtCore.pyqtSignal(object, int)
    port_exit = QtCore.pyqtSignal(object)
    name_changed = QtCore.pyqtSignal(str)

    def __init__(self, graph, client_id):
        QtCore.QObject.__init__(self)
        self.graph = graph
        self.seq = graph.seq
        self.id = client_id
        self.info_dict = self.seq.get_client_info(client_id)
        for s in ['broadcast_filter', 'error_bounce', 'event_filter', 'event_lost', 'type']:
            setattr(self, s, self.info_dict[s])
        self._name = self.info_dict['name']
        self.port_n = self.info_dict['num_ports']
        self.port_dict = {}

    @property
    def type_str(self):
        return _ClientTypeStrings[int(self.type)]

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, name):
        if name != self._name:
            self._name = name
            self.name_changed.emit(name)

    @property
    def ports(self):
        return [self.port_dict[port_id] for port_id in sorted(self.port_dict.keys())]

    def add_port(self, port_id):
        port = Port(self, port_id)
        self.port_dict[port_id] = port
        self.port_start.emit(port, port_id)
        return port

    def remove_port(self, port):
        port = self.port_dict.pop(port, None)
        self.port_exit.emit(port)
        del port

    def get_connections(self):
        return list(set([port.connections for port in self.port_dict.values()]))

    def __repr__(self):
        return 'Client "{}" ({})'.format(self.name, self.id)

class Graph(QtCore.QObject):
    graph_changed = QtCore.pyqtSignal()
    client_start = QtCore.pyqtSignal(object, int)
    client_exit = QtCore.pyqtSignal(object)
    port_start = QtCore.pyqtSignal(object, int)
    port_exit = QtCore.pyqtSignal(object)
    new_connection = QtCore.pyqtSignal(object)

    def __init__(self, seq):
        QtCore.QObject.__init__(self)
        self.seq = seq
        self.client_id_dict = {}
        self.port_id_dict = {}
        self.connections = {}
        graph_raw = seq.connection_list()
        conn_raw = []
        for client_name, client_id, ports in graph_raw:
            client = Client(self, client_id)
            self.client_id_dict[client_id] = client
            self.port_id_dict[client_id] = client.port_dict
            for port_name, port_id, (conn_out, conn_in) in ports:
                port = client.add_port(port_id)
                self.connections[port] = port.connections
                for conn in conn_in:
                    conn_tuple = ((conn[0], conn[1]), (client_id, port_id))
                    conn_raw.append(conn_tuple)
                for conn in conn_out:
                    conn_tuple = ((client_id, port_id), (conn[0], conn[1]))
                    conn_raw.append(conn_tuple)
        conn_set = set(conn_raw)
        for conn_src, conn_dest in conn_set:
            src = self.get_port(*conn_src)
            dest = self.get_port(*conn_dest)
            conn = Connection(self, src, dest, False if any([src.hidden, dest.hidden]) else True)
            self.connections[src].append(conn)
            self.connections[dest].append(conn)


    def get_port(self, client_id, port_id):
        try:
            return self.port_id_dict[client_id][port_id]
        except:
            return None

    def get_port_connections(self, port):
        try:
            for conn in self.connections[port]:
                try:
                    self.seq.get_connect_info(conn.src.addr, conn.dest.addr)
                except:
                    self.connections[conn.src].remove(conn)
                    self.connections[conn.dest].remove(conn)
                    conn.lost.emit()
            return self.connections[port]
        except:
            return None


    def conn_deleted(self, conn):
        self.connections[conn.src].remove(conn)
        self.connections[conn.dest].remove(conn)
        self.graph_changed.emit()

    def client_created(self, data):
        client_id = data['addr.client']
        client = Client(self, client_id)
        self.client_id_dict[client_id] = client
        self.port_id_dict[client_id] = client.port_dict
        self.client_start.emit(client, client.id)
        self.graph_changed.emit()

    def client_destroyed(self, data):
        client_id = data['addr.client']
        client = self.client_id_dict[client_id]
        for port in client.port_dict.values():
            #since ALSA (should have) disconnected all client's port, get_port_connections will take care of their removal
            self.get_port_connections(port)
            client.remove_port(port)
        client = self.client_id_dict.pop(client_id)
        self.client_exit.emit(client)
        self.graph_changed.emit()

    def port_created(self, data):
        client = self.client_id_dict[data['addr.client']]
        port = client.add_port(data['addr.port'])
        self.connections[port] = port.connections
        self.port_start.emit(port, port.id)
        self.graph_changed.emit()

    def port_destroyed(self, data):
        client_id = data['addr.client']
        client = self.client_id_dict[client_id]
        port = self.port_id_dict[client_id].pop(data['addr.port'])
        self.get_port_connections(port)
        client.remove_port(port)
        self.connections.pop(port)
        self.port_exit.emit(port)
        self.graph_changed.emit()

    def conn_created(self, data):
        dest = self.get_port(data['connect.dest.client'], data['connect.dest.port'])
#        if dest.client.id == self.seq.client_id:
#            return
        src = self.get_port(data['connect.sender.client'], data['connect.sender.port'])
        conn = Connection(self, src, dest, False if any([src.hidden, dest.hidden]) else True)
        self.connections[src].append(conn)
        self.connections[dest].append(conn)
        self.new_connection.emit(conn)
        self.graph_changed.emit()

    def conn_destroyed(self, data):
        src = self.get_port(data['connect.sender.client'], data['connect.sender.port'])
#        dest = self.get_port(data['connect.dest.client'], data['connect.dest.port'])
        #this should be enough, since the cycle in get_port_connections takes care of removing all connections
        self.get_port_connections(src)
        self.graph_changed.emit()

    def graph_full(self, full_port=False, full_conn=False):
        for client in [self.client_id_dict[i] for i in sorted(self.client_id_dict.keys())]:
            c_str = '{}\n'.format(client)
            output = ''
            for port in client.port_dict.values():
                if port.hidden and not full_port:
                    continue
                output += '\t{} (type: {}, caps: {})\n'.format(port, port.type, port.caps)
                for conn in port.connections:
                    if conn.hidden and not full_conn:
                        continue
                    conn_port = conn.dest if conn.dest!= port else conn.src
                    output += '\t\t{} (type: {}, caps: {})\n'.format(conn_port, conn_port.type, conn_port.caps)
            if len(output):
                print c_str+output

    def graph_simple(self, input=None, output=None, hidden=False):
        c_output = []
        c_input = []
        for id, client in enumerate([self.client_id_dict[i] for i in sorted(self.client_id_dict.keys())]):
            c_output.append(['  {} ({})'.format(client.name, client.id)])
            c_input.append(['  {} ({})'.format(client.name, client.id)])
            for port in client.port_dict.values():
                if port.hidden and not hidden:
                    continue
                if port.is_output:
                    c_output[id].append('    {i} "{n}": ({t})'.format(i=port.id, n=port.name, t=','.join(port.type_str), c=','.join(port.caps_str)))
                if port.is_input:
                    c_input[id].append('    {i} "{n}": ({t})'.format(i=port.id, n=port.name, t=','.join(port.type_str), c=','.join(port.caps_str)))
        if (not input and not output) or all([input, output]):
            s = 'Output clients:\n'
            for client in c_output:
                if len(client) > 1:
                    s += '\n'.join(client)
                    s += '\n'
            s += '\nInput clients:\n'
            for client in c_input:
                if len(client) > 1:
                    s += '\n'.join(client)
                    s += '\n'
        elif output:
            s = 'Output clients:\n'
            for client in c_output:
                if len(client) > 1:
                    s += '\n'.join(client)
                    s += '\n'
        else:
            s = 'Input clients:\n'
            for client in c_input:
                if len(client) > 1:
                    s += '\n'.join(client)
                    s += '\n'
        print s

    @property
    def client_name_dict(self):
        name_dict = {}
        for client_id, client in self.client_id_dict.items():
            name_l = name_dict.get(client.name, [])
            name_l.append(client_id)
            name_dict[client.name] = name_l
        return name_dict



