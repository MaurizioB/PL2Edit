import string
from PyQt4 import QtGui, QtCore
from midiutils import BlackKeys
from collections import namedtuple
from icons import *

key_white_width = 24
width_tmp = int(round(key_white_width/3.0*2))
key_black_width = width_tmp if (width_tmp & 1)==1 else width_tmp+1

key_white_height = key_white_width*6
key_black_height = int(key_white_height*0.55)

key_letters = ['z', 's', 'x', 'd', 'c', 'v', 'g', 'b', 'h', 'n', 'j', 'm', 'q', '2', 'w', '3', 'e', 'r', '5', 't', '6', 'y', '7', 'u', 'i', '9', 'o', '0', 'p']

MapEvent = namedtuple('MapEvent', 'channel type id')

Programs = ['Upright Bass', 'Analog Synth', 'Lord', 'Cempilo', 'Analog Strings', 'Summer Bass', 'Will You', 
            'Berlin 61', 'Main Bass', 'On Air', 'Black Roses', 'Poison', '5th down', 'Dub Bass', 'Charles', 
            'Wesley', 'Analog Bass', 'Signals', 'Mr. Finger', 'Dead Cat', 'Titanium', 'Neon Wobble', 'PR-L08', 
            'PR-L09', 'Geiger', 'Metropolis', 'Vettel', 'Analog Pad', 'Lukas', 'Transformator', 'Smacker', 'Electric Moskito']

base2 = [64, 32, 16, 8, 4, 2, 1]

#miditype_d = {CTRL: alsaseq.SEQ_EVENT_CONTROLLER, 
#              NOTEON: alsaseq.SEQ_EVENT_NOTEON, 
#              NOTEOFF: alsaseq.SEQ_EVENT_NOTEOFF, 
#              PROGRAM: alsaseq.SEQ_EVENT_PGMCHANGE, 
#              SYSEX: alsaseq.SEQ_EVENT_SYSEX}


class ReprConst(object):
    def __init__(self):
        self.name = None
    def get_name(self):
        return [k for k, v in globals().items() if v is self][0]
    def __str__(self):
        if not self.name:
            self.name = self.get_name()
        return self.name
    def __repr__(self):
        if not self.name:
            self.name = self.get_name()
        return self.name


AllValues, MapDict, ProgData = [ReprConst() for i in range(3)]

def setBold(item, bold=True):
    font = item.font()
    font.setBold(bold)
    item.setFont(font)

def setItalic(item, bold=True):
    font = item.font()
    font.setItalic(bold)
    item.setFont(font)

def parse_prog_data(file_path):
    try:
        with open(file_path, 'rb') as f:
            data = ''.join(f.readlines())
        if not len(data):
            return None
        last = data.index('-')-len(data)
        prog_data = eval('[{}]'.format(data[4:last].replace(')(', '),(')))
        if len(prog_data) != 27 or not all(False for x in prog_data if x[1] < 0):
            return False
        return [d[1] for d in prog_data]
    except:
        return False

def bit_convert(value, length=7):
    if not value < 2**length:
        return False
    bit_list = []
    for x in range(length-1,-1,-1):
        bit = 2**x
        if bit&value:
            value -= bit
            bit_list.append(True)
        else:
            bit_list.append(False)
    return bit_list


class PianoKey(QtGui.QWidget):
    NoteOn = QtCore.pyqtSignal(int)
    NoteOff = QtCore.pyqtSignal(int)

    def __init__(self, parent, id, letter=None):
        QtGui.QWidget.__init__(self, parent)
        self.parent = parent
        self.id = id+36
#        self.name = note_name(self.id)
#        self.black = True if self.name[1]=='#' else False
        self.black = self.id in BlackKeys
        self.pressed = False
        self.hover = False
        self.octave, self.note = divmod(id, 12)
        self.hover_color = QtCore.Qt.gray
        self.pen = QtGui.QPen(QtCore.Qt.black, 0.5, QtCore.Qt.SolidLine)
        self.text_pen = QtGui.QPen(QtCore.Qt.red, 0.5, QtCore.Qt.SolidLine)
        if self.black:
            self.color = QtCore.Qt.black
            self._width = key_black_width
            self._height = key_black_height
            self.setMinimumSize(self._width, self._height)
            self.setMaximumSize(self._width, self._height)
            if (self.note & 1) == 1:
                self.move(self.octave*7*key_white_width+self.note/2*key_white_width+key_black_width, 0)
            else:
                self.move(self.octave*7*key_white_width+(self.note+1)/2*key_white_width+key_black_width, 0)
        else:
            self.color = QtCore.Qt.white
            self._width = key_white_width
            self._height = key_white_height
            self.setMinimumSize(self._width, self._height)
            self.setMaximumSize(self._width, self._height)
            if (self.note & 1) == 0:
                self.move(self.octave*7*key_white_width+self.note/2*key_white_width, 0)
            else:
                self.move(self.octave*7*key_white_width+(self.note+1)/2*key_white_width, 0)
            self.lower()
        self._color = self.color
        self.current_color = self.color
        self.draw_func = self.draw_key
        if letter:
            self.letter = letter.upper()
            delta = self._height - key_black_width*2
            self.text_rect = QtCore.QRectF(0, delta, self._width, self._width)

    def text_enable(self, value):
        if value:
            self.draw_func = self.draw_key_with_text
        else:
            self.draw_func = self.draw_key
        self.update()

    def showEvent(self, event):
        self.update()

    def paintEvent(self, event):
        qp = QtGui.QPainter()
        qp.begin(self)
        self.draw_func(qp)
        qp.end()

    def draw_key(self, qp):
        qp.setPen(self.pen)
        qp.setBrush(self.current_color)
        qp.drawRect(0, 0, self._width, self._height)

    def draw_key_with_text(self, qp):
        qp.setPen(self.pen)
        qp.setBrush(self.current_color)
        qp.drawRect(0, 0, self._width, self._height)
        qp.setPen(self.text_pen)
        qp.setFont(QtGui.QFont('Decorative', key_black_width))
        qp.drawText(self.text_rect, QtCore.Qt.AlignHCenter, self.letter)

    def mousePressEvent(self, event, velocity=None):
        if not velocity:
            velocity = self.parent.main.velocity
        self.pressed = True
        self.NoteOn.emit(self.id)
        self.current_color = QtGui.QColor.fromRgb(255-velocity, 255-velocity, 128-velocity)
        self.update()

    def mouseReleaseEvent(self, event):
        self.pressed = False
        self.NoteOff.emit(self.id)
        self.current_color = self.hover_color if self.hover else self.color
        self.update()

    def enterEvent(self, event):
        self.hover = True
        self.current_color = self.hover_color
        self.update()

    def leaveEvent(self, event):
        self.hover = False
        if self.pressed:
            self.pressed = False
            self.NoteOff.emit(self.id)
        self.current_color = self.color
        self.update()

class Piano(QtGui.QWidget):
    def __init__(self, parent):
        QtGui.QWidget.__init__(self, parent)
        self.main = parent
        self.keys = []
        self.prev = None
        self.highlight = None
        for i in range(61):
            if 12 <= i < 41:
                letter = key_letters[i-12]
            else:
                letter = None
            key = PianoKey(self, i, letter)
            self.keys.append(key)
        self.setMinimumHeight(key.height())
        self.setMinimumWidth(key.width()*36)
        app = QtGui.QApplication.instance()
        app.installEventFilter(self)

    def show_keys(self, value):
        for l in range(12, 41):
            self.keys[l].text_enable(value)

    def eventFilter(self, source, event):
        if event.type() == QtCore.QEvent.MouseMove and source == self:
            try:
                key = self.childAt(event.pos())
                if not isinstance(key, PianoKey):
                    return QtGui.QWidget.eventFilter(self, source, event)
                if self.prev:
                    if key == self.prev:
                        return True
                    else:
                        self.prev.leaveEvent(event)
                        key.mousePressEvent(event)
                self.prev = key
            except Exception as E:
                print E
                pass
        elif event.type() == QtCore.QEvent.MouseButtonRelease:
            if self.prev:
                self.prev.leaveEvent(event)
        return QtGui.QWidget.eventFilter(self, source, event)

    def noteon_send(self, id):
        print id

    def noteoff_send(self, id):
        print id

    def all_notes_off(self):
        for i in range(12, 41):
            key = self.keys[i]
            key.blockSignals(True)
            key.mouseReleaseEvent(False)
            key.blockSignals(False)

class MultiList(object):
    def __init__(self, fields=None, data_fields=1, unique=True):
        self.fields = fields.split()
        self.field_n = len(self.fields)
        self.unique = unique
        if data_fields is None:
            self.data_fields = []
            self.data_n = 0
        elif isinstance(data_fields, int):
            self.data_fields = ['data{}'.format(n) for n in range(data_fields)]
            self.data_n = data_fields
        else:
            self.data_fields = data_fields.split()
            self.data_n = len(self.data_fields)
        self._data = []
        self._nt_list = []
        self._nt_full = namedtuple('MultiList', [f for f in self.fields+self.data_fields])
        self._nt_full.__new__.__defaults__ = (None, )*len(self.fields)
        self.field_dicts = []
        for field in self.fields:
            self.field_dicts.append({})
            setattr(self, 'get_{}'.format(field), self._create_get(field))
            setattr(self, 'get_{}_list'.format(field), self._create_get_fieldlist(field))

    def append(self, *data):
        if not self.field_n <= len(data) <= self.field_n+self.data_n:
            raise ValueError('Data length must be between {} and {}'.format(self.field_n, self.field_n+self.data_n))
        if self.unique:
            for i in range(self.field_n):
                if data[i] in self.field_dicts[i].keys():
                    raise ValueError('Data "{}" is already there'.format(data[i]))
        self._data.append(list(data))
        if self.unique:
            for index, field in enumerate(self.field_dicts):
                field[data[index]] = self._data[-1]
            return
        for index, field in enumerate(self.field_dicts):
            try:
                field[data[index]].append(self._data[-1])
            except:
                field[data[index]] = [self._data[-1]]

    def items(self):
        for i in self._data:
            yield self._nt_full(*i)

    def get_field_values(self, index):
        return [field[index] for field in self._data]

    def get_by_column_id(self, column, value):
        if not 0 <= column < len(self.fields):
            raise KeyError('field index must be between 0 and {}'.format(len(self.fields)))
        try:
#            return [v for i, v in enumerate(self.field_dicts[column][value]) if i!=column]
            if self.unique:
                return self._nt_list[column](*[v for i, v in enumerate(self.field_dicts[column][value]) if i!=column])
            results = [[v for i, v in enumerate(res) if i!=column] for res in self.field_dicts[column][value]]
            if len(results) == 1:
                return self._nt_list[column](*results[0])
            elif len(results) > 1:
                return [self._nt_list[column](*r) for r in results]
            
        except Exception as e:
            print e
            return None

    def get_by_column_name(self, field_name, value):
        try:
            column = self.fields.index(field_name)
            return self.get_by_column_id(column, value)
        except:
            raise KeyError('Field \'{}\' does not exist'.format(field_name))

    def _create_get(self, field_name):
        self._nt_list.append(namedtuple(field_name, [f for f in self.fields if f!=field_name]+self.data_fields))
        def get_func(value):
            try:
                column = self.fields.index(field_name)
                return self.get_by_column_id(column, value)
            except:
                return None
        return get_func

    def _create_get_fieldlist(self, field_name):
        def get_func():
            return self.get_field_values(self.fields.index(field_name))
        return get_func

    def __getitem__(self, index):
        return self._data[index]

    def __setitem__(self, index, data):
        if index >= len(self._data):
            raise IndexError('List index out of range')
        item = self._data[index]
        if len(data) > self.data_n:
            raise IndexError('Data out of range')
        for i, v in enumerate(data):
            item[self.field_n+i] = v


def _decode(txt):
    txt = txt.replace('_', '__')
    txt = txt.replace(' ', '_')
    return txt

def _encode(txt):
    txt = txt.replace('__', '::')
    txt = txt.replace('_', ' ')
    txt = txt.replace('::', '_')
    return txt

def _is_int(value):
    try:
        int(value)
        return True
    except:
        return False


class SettingsGroup(object):
    def __init__(self, settings, name=None):
        self._settings = settings
        self._group = settings.group()
        for k in settings.childKeys():
            value = settings.value(k).toPyObject()
            if isinstance(value, QtCore.QString):
                value = str(value)
                if value == 'true':
                    value = True
                elif value == 'false':
                    value = False
                elif _is_int(value):
                    value = int(value)
                else:
                    try:
                        value = float(value)
                    except:
                        pass
            setattr(self, _decode(str(k)), value)
        if len(self._group):
            for g in settings.childGroups():
                settings.beginGroup(g)
                setattr(self, 'g{}'.format(_decode(g)), SettingsGroup(settings))
                settings.endGroup()
        self._done = True

    def createGroup(self, name):
        self._settings.beginGroup(self._group)
        self._settings.beginGroup(name)
        gname = 'g{}'.format(_decode(name))
        setattr(self, gname, SettingsGroup(self._settings))
        self._settings.endGroup()
        self._settings.endGroup()

    def __setattr__(self, name, value):
        if '_done' in self.__dict__.keys():
            if not isinstance(value, SettingsGroup):
                dname = _encode(name)
                if len(self._group):
                    self._settings.beginGroup(self._group)
                    self._settings.setValue(dname, value)
                    self._settings.endGroup()
                else:
                    self._settings.setValue(dname, value)
                super(SettingsGroup, self).__setattr__(name, value)
            else:
                super(SettingsGroup, self).__setattr__(name, value)
        else:
            super(SettingsGroup, self).__setattr__(name, value)

    def __getattr__(self, name):
        def save_func(value):
            self._settings.beginGroup(self._group)
            self._settings.setValue(_encode(name[4:]), value)
            self._settings.endGroup()
            setattr(self, name[4:], value)
            return value
        if name.startswith('set_'):
            obj = type('setter', (object, ), {})()
            obj.__class__.__call__ = lambda x, y=None: setattr(self, name[4:], y)
            return obj
        if not name.startswith('get_'):
            return
        try:
            orig = super(SettingsGroup, self).__getattribute__(name[4:])
            if isinstance(orig, bool):
                obj = type(type(orig).__name__, (object,), {'value': orig})()
                obj.__class__.__call__ = lambda x,  y=None, save=False, orig=orig: orig
                obj.__class__.__len__ = lambda x: orig
                obj.__class__.__eq__ = lambda x, y: True if x.value==y else False
            else:
                obj = type(type(orig).__name__, (type(orig), ), {})(orig)
                obj.__class__.__call__ = lambda x, y=None, save=False, orig=orig: orig
            return obj
        except AttributeError:
            print 'Setting {} not found, returning default'.format(name[4:])
            obj = type('obj', (object,), {})()
            obj.__class__.__call__ = lambda x, y=None, save=False:y if not save else save_func(y)
            return obj

class SettingsObj(object):
    def __init__(self, settings):
        self._settings = settings
        self._sdata = []
        self._load()
        self._done = True

    def _load(self):
        for d in self._sdata:
            delattr(self, d)
        self._sdata = []
        self._settings.sync()
        self.gGeneral = SettingsGroup(self._settings)
        self._sdata.append('gGeneral')
        for g in self._settings.childGroups():
            self._settings.beginGroup(g)
            gname = 'g{}'.format(self._decode(g))
            self._sdata.append(gname)
            setattr(self, gname, SettingsGroup(self._settings))
            self._settings.endGroup()

    def __getattr__(self, name):
        if not (name.startswith('g') and name[1] in string.ascii_uppercase):
            raise AttributeError
        name = name[1:]
        self._settings.beginGroup(name)
        gname = 'g{}'.format(self._decode(name))
        self._sdata.append(gname)
        new_group = SettingsGroup(self._settings)
        setattr(self, gname, new_group)
        self._settings.endGroup()
        return new_group

    def sync(self):
        self._settings.sync()

    def createGroup(self, name):
        self._settings.beginGroup(name)
        gname = 'g{}'.format(self._decode(name))
        self._sdata.append(gname)
        setattr(self, gname, SettingsGroup(self._settings))
        self._settings.endGroup()

    def _decode(self, txt):
        txt = txt.replace('_', '__')
        txt = txt.replace(' ', '_')
        return txt






