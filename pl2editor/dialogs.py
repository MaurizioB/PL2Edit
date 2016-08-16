from PyQt4 import QtGui, QtCore
from midiutils import CTRL, NOTE, NOTEON, NOTEOFF

class HSpacer(QtGui.QWidget):
    def __init__(self, width=5, parent=None):
        QtGui.QWidget.__init__(self, parent)
        self.setMinimumWidth(width)


class VSpacer(QtGui.QWidget):
    def __init__(self, height=5, parent=None):
        QtGui.QWidget.__init__(self, parent)
        self.setMinimumHeight(height)


class CtrlSpin(QtGui.QSpinBox):
    def __init__(self, value=None, noval=False, parent=None):
        QtGui.QSpinBox.__init__(self, parent)
        self.setMaximum(127)
        if noval:
            self.setMinimum(-1)
            self.setSpecialValueText(noval if isinstance(noval, str) else 'None')
            self.setValue(value if value is not None else -1)
        else:
            self.setValue(value if value is not None else 0)


class EventCombo(QtGui.QComboBox):
    def __init__(self, parent=None):
        QtGui.QComboBox.__init__(self, parent)
        self.event_model = QtGui.QStandardItemModel()
        self.event_items = {}
        for e, l in [(CTRL, 'CTRL'), (NOTE, 'NOTE OFF/ON'), (NOTEON, 'NOTE ON'), (NOTEOFF, 'NOTE OFF')]:
            item = QtGui.QStandardItem(l)
            item.type = e
            self.event_model.appendRow(item)
            self.event_items[e] = item
        self.setModel(self.event_model)

    def setEventType(self, event_type):
        try:
            self.setCurrentIndex(self.event_items[event_type].row())
        except:
            pass

class SimpleMap(QtGui.QDialog):
    def __init__(self, parent, name):
        QtGui.QDialog.__init__(self, parent)
        self.setWindowTitle('Set mapping')
        grid = QtGui.QGridLayout(self)
        caption = QtGui.QLabel('Set CTRL mapping for {} or use a MIDI controller'.format(name))
        grid.addWidget(caption, 0, 0, 1, -1)
        spacer = VSpacer()
        grid.addWidget(spacer, 1, 0)
        chan_label = QtGui.QLabel('Channel:')
        grid.addWidget(chan_label, 2, 0)
        self.chan_spin = QtGui.QSpinBox()
        self.chan_spin.setMinimum(1)
        self.chan_spin.setMaximum(16)
        grid.addWidget(self.chan_spin, 2, 1)
        id_label = QtGui.QLabel('CTRL id:')
        grid.addWidget(id_label, 2, 2)
        self.id_spin = CtrlSpin()
        grid.addWidget(self.id_spin, 2, 3)
        button_box = QtGui.QDialogButtonBox(QtGui.QDialogButtonBox.Ok|QtGui.QDialogButtonBox.Cancel)
        grid.addWidget(button_box, 3, 0, 1, -1)
        button_box.button(QtGui.QDialogButtonBox.Ok).clicked.connect(self.accept)
        button_box.button(QtGui.QDialogButtonBox.Cancel).clicked.connect(self.reject)
        parent.MidiEvent.connect(self.midi_event)

    def exec_(self, map_data=None):
        if map_data:
            event = map_data[0][0]
            self.chan_spin.setValue(event[0])
            self.id_spin.setValue(event[2])
        res = QtGui.QDialog.exec_(self)
        if not res:
            return False
        return (self.chan_spin.value()-1, CTRL, self.id_spin.value())

    def midi_event(self, event):
        if event.type != CTRL:
            return
        self.chan_spin.setValue(event.channel+1)
        self.id_spin.setValue(event.data1)


class ComboMap(QtGui.QDialog):
    def __init__(self, parent, name, items):
        QtGui.QDialog.__init__(self, parent)
        self.detect = None
        self.setWindowTitle('Set mapping')
        self.name = name
        grid = QtGui.QGridLayout(self)
        caption = QtGui.QLabel('Set MIDI data for {} or use a control surface'.format(name))
        grid.addWidget(caption, 0, 0, 1, -1)
        spacer = VSpacer()
        grid.addWidget(spacer, 1, 0)
        channel_label = QtGui.QLabel('chan')
        channel_label.setAlignment(QtCore.Qt.AlignHCenter)
        grid.addWidget(channel_label, 3, 1)
        event_label = QtGui.QLabel('type')
        event_label.setAlignment(QtCore.Qt.AlignHCenter)
        grid.addWidget(event_label, 3, 2)
        id_label = QtGui.QLabel('id')
        id_label.setAlignment(QtCore.Qt.AlignHCenter)
        grid.addWidget(id_label, 3, 3)
        value_label = QtGui.QLabel('value')
        value_label.setAlignment(QtCore.Qt.AlignHCenter)
        grid.addWidget(value_label, 3, 4)
        self.single_chk = QtGui.QCheckBox('COMMON')
        self.single_chk.setStyleSheet('font-weight: bold;')
        self.single_chk.toggled.connect(self.common_set)
        grid.addWidget(self.single_chk, 4, 0)
        self.chan_spin = QtGui.QSpinBox()
        self.chan_spin.setMinimum(1)
        self.chan_spin.setMaximum(16)
        self.chan_spin.valueChanged.connect(self.common_check)
        grid.addWidget(self.chan_spin, 4, 1)
        self.event_combo = EventCombo()
        self.event_combo.currentIndexChanged.connect(self.common_check)
        grid.addWidget(self.event_combo, 4, 2)
        self.id_spin = CtrlSpin()
        self.id_spin.setAlignment(QtCore.Qt.AlignLeft)
        self.id_spin.valueChanged.connect(self.common_check)
        grid.addWidget(self.id_spin, 4, 3)
        self.detect_group = QtGui.QButtonGroup()
        self.detect_group.setExclusive(False)
        self.common_detect_btn = QtGui.QPushButton(QtGui.QIcon(':/icons/bolt.png'), '')
        self.common_detect_btn.setToolTip('MIDI learn')
        self.common_detect_btn.setCheckable(True)
        self.common_detect_btn.clicked.connect(lambda value, btn=self.common_detect_btn: self.detect_set(btn, value))
        self.detect_group.addButton(self.common_detect_btn)
        self.detect_group.setId(self.common_detect_btn, 0)
        grid.addWidget(self.common_detect_btn, 4, 5)

        self.spin_list = []
        values = len(items)
        last_row = grid.rowCount()
        for r, item in enumerate(items):
            row = last_row+r
            label = QtGui.QLabel(item)
#            label.setAlignment(QtCore.Qt.AlignRight)
            grid.addWidget(label, row, 0)
            chan_spin = QtGui.QSpinBox()
            chan_spin.setMinimum(1)
            chan_spin.setMaximum(16)
            chan_spin.valueChanged.connect(self.spin_check)
            grid.addWidget(chan_spin, row, 1)
            event_combo = EventCombo()
            event_combo.currentIndexChanged.connect(self.spin_check)
            grid.addWidget(event_combo, row, 2)
            id_spin = CtrlSpin()
            id_spin.valueChanged.connect(self.spin_check)
            grid.addWidget(id_spin, row, 3)
            value_spin = QtGui.QSpinBox()
            value_spin.setMaximum(127)
            value_spin.setSizePolicy(QtGui.QSizePolicy.Maximum, QtGui.QSizePolicy.Fixed)
            value_spin.setValue([128/values*a for a in range(values)][r])
            grid.addWidget(value_spin, row, 4)
            value_spin.valueChanged.connect(self.spin_check)
            btn = QtGui.QPushButton(QtGui.QIcon(':/icons/bolt.png'), '')
            btn.setToolTip('MIDI learn')
            btn.setCheckable(True)
            btn.clicked.connect(lambda value, btn=btn: self.detect_set(btn, value))
            self.detect_group.addButton(btn)
            self.detect_group.setId(btn, r+1)
            grid.addWidget(btn, row, 5, 1, 1)
            self.spin_list.append([chan_spin, event_combo, id_spin, value_spin])
        self.button_box = QtGui.QDialogButtonBox(QtGui.QDialogButtonBox.Ok|QtGui.QDialogButtonBox.Cancel)
        grid.addWidget(self.button_box, grid.rowCount(), 0, 1, 5)
        self.button_box.button(QtGui.QDialogButtonBox.Ok).clicked.connect(self.accept)
        self.button_box.button(QtGui.QDialogButtonBox.Cancel).clicked.connect(self.reject)
        self.id_spin.valueChanged.connect(self.spin_enable)
        parent.MidiEvent.connect(self.midi_event)

        #preload > da rimuovere una volta che exec_ accetta parametri
        self.single_chk.setChecked(True)
#        self.ctrl_spin.setValue(-1)

    def common_check(self, *args):
        if self.single_chk.isChecked():
            for chan_spin, event_combo, id_spin, value_spin in self.spin_list:
                chan_spin.setValue(self.chan_spin.value())
                event_combo.setCurrentIndex(self.event_combo.currentIndex())
                id_spin.setValue(self.id_spin.value())

    def common_set(self, value):
        self.chan_spin.setEnabled(value)
        self.event_combo.setEnabled(value)
        self.id_spin.setEnabled(value)
        self.common_detect_btn.setEnabled(value)
        detect_buttons = self.detect_group.buttons()
        detect_buttons[0].setEnabled(value)
        for i, (chan_spin, event_combo, id_spin, value_spin) in enumerate(self.spin_list):
            chan_spin.setEnabled(not value)
            event_combo.setEnabled(not value)
            id_spin.setEnabled(not value)
        [btn.setChecked(False) for btn in detect_buttons]
        self.spin_check()

    def spin_enable(self, value):
        if value < 0:
            toggle = False
        else:
            toggle = True
        for i, i, i, value_spin in self.spin_list:
            value_spin.setEnabled(toggle)

    def spin_check(self, value=None):
        value_list = []
        valid = True
        if self.single_chk.isChecked():
            for i, i, i, value_spin in self.spin_list:
                value_list.append(value_spin.value())
                if value_list.count(value_spin.value()) > 1:
                    valid = False
        else:
            for chan_spin, event_combo, id_spin, value_spin in self.spin_list:
                data = chan_spin.value(), event_combo.currentIndex(), id_spin.value(), value_spin.value()
                value_list.append(data)
                if value_list.count(data) > 1:
                    valid = False
        self.button_box.button(QtGui.QDialogButtonBox.Ok).setEnabled(valid)

    def detect_set(self, btn, value):
        for other in self.detect_group.buttons():
            if other != btn and value:
                other.setChecked(False)
        self.detect = self.detect_group.id(btn) if value else None


    def midi_event(self, event):
        if self.detect is not None:
            if self.detect == 0:
                chan_spin = self.chan_spin
                event_combo = self.event_combo
                id_spin = self.id_spin
            else:
                chan_spin, event_combo, id_spin, value_spin = self.spin_list[self.detect-1]
                if self.single_chk.isChecked():
                    chan_spin = self.chan_spin
                    event_combo = self.event_combo
                    id_spin = self.id_spin
                value_spin.setValue(event.data2)
            chan_spin.setValue(event.channel+1)
            event_combo.setEventType(event.type)
            id_spin.setValue(event.data1)
            self.detect_group.buttons()[self.detect].setChecked(False)
            self.detect = None

    def exec_(self, map_data=None):
        if map_data:
            ev_map = []
            for spin, (ev_data, value) in map_data.items():
                chan_spin, event_combo, id_spin, value_spin = self.spin_list[spin]
                chan, event_type, param = ev_data
                ev_map.append(ev_data)
                chan_spin.setValue(chan+1)
                event_combo.setEventType(event_type)
                id_spin.setValue(param)
                value_spin.setValue(value)
            if len(set(ev_map)) == 1:
                (chan, event_type, param), value = map_data[0]
                self.chan_spin.setValue(chan+1)
                self.event_combo.setEventType(event_type)
                self.id_spin.setValue(param)
            else:
                self.single_chk.setChecked(False)
        res = QtGui.QDialog.exec_(self)
        if not res:
            return False
        if self.single_chk.isChecked():
            return [(self.chan_spin.value()-1, self.event_combo.model().item(self.event_combo.currentIndex()).type, self.id_spin.value(),
                    [spin.value() for i, i, i, spin in self.spin_list], )]
        return [(chan_spin.value()-1, event_combo.model().item(event_combo.currentIndex()).type, id_spin.value(), value_spin.value()) for chan_spin, event_combo, id_spin, value_spin in self.spin_list]


class CheckboxMap(QtGui.QDialog):
    def __init__(self, parent, name):
        QtGui.QDialog.__init__(self, parent)
        self.detect = None
        self.setWindowTitle('Set mapping')
        self.name = name
        grid = QtGui.QGridLayout(self)
        caption = QtGui.QLabel('Set MIDI data for controller {}'.format(name))
        grid.addWidget(caption, 0, 0, 1, 4)
        spacer = VSpacer()
        grid.addWidget(spacer, 1, 0)
        self.toggle = QtGui.QCheckBox('Set toggle mode')
        self.toggle.toggled.connect(self.toggle_set)
        grid.addWidget(self.toggle, 2, 0, 1, -1)
        channel_label = QtGui.QLabel('chan')
        channel_label.setAlignment(QtCore.Qt.AlignHCenter)
        grid.addWidget(channel_label, 3, 1)
        event_label = QtGui.QLabel('type')
        event_label.setAlignment(QtCore.Qt.AlignHCenter)
        grid.addWidget(event_label, 3, 2)
        id_label = QtGui.QLabel('id')
        id_label.setAlignment(QtCore.Qt.AlignHCenter)
        grid.addWidget(id_label, 3, 3)
        value_label = QtGui.QLabel('value')
        value_label.setAlignment(QtCore.Qt.AlignHCenter)
        grid.addWidget(value_label, 3, 4)

        self.detect_group = QtGui.QButtonGroup()
        self.detect_group.setExclusive(False)

        self.enable_label = QtGui.QLabel('Enable {}'.format(name))
        grid.addWidget(self.enable_label, 4, 0)
        self.enable_chan_spin = QtGui.QSpinBox()
        self.enable_chan_spin.setMinimum(1)
        self.enable_chan_spin.setMaximum(16)
        grid.addWidget(self.enable_chan_spin, 4, 1)
        self.enable_event_combo = EventCombo()
        grid.addWidget(self.enable_event_combo, 4, 2)
        self.enable_id_spin = CtrlSpin()
#        self.ctrl_spin.setSizePolicy(QtGui.QSizePolicy.Maximum, QtGui.QSizePolicy.Fixed)
        self.enable_id_spin.setAlignment(QtCore.Qt.AlignLeft)
        grid.addWidget(self.enable_id_spin, 4, 3)
        self.enable_value_spin = CtrlSpin(value=64)
        grid.addWidget(self.enable_value_spin, 4, 4)
        enable_detect_btn = QtGui.QPushButton(QtGui.QIcon(':/icons/bolt.png'), '')
        enable_detect_btn.setToolTip('MIDI learn')
        enable_detect_btn.setCheckable(True)
        enable_detect_btn.clicked.connect(lambda value, btn=enable_detect_btn: self.detect_set(btn, value))
        self.detect_group.addButton(enable_detect_btn)
        self.detect_group.setId(enable_detect_btn, 0)
        grid.addWidget(enable_detect_btn, 4, 5)

        self.disable_label = QtGui.QLabel('Enable {}'.format(name))
        grid.addWidget(self.disable_label, 5, 0)
        self.disable_chan_spin = QtGui.QSpinBox()
        self.disable_chan_spin.setMinimum(1)
        self.disable_chan_spin.setMaximum(16)
        grid.addWidget(self.disable_chan_spin, 5, 1)
        self.disable_event_combo = EventCombo()
        grid.addWidget(self.disable_event_combo, 5, 2)
        self.disable_id_spin = CtrlSpin()
#        self.ctrl_spin.setSizePolicy(QtGui.QSizePolicy.Maximum, QtGui.QSizePolicy.Fixed)
        self.disable_id_spin.setAlignment(QtCore.Qt.AlignLeft)
        grid.addWidget(self.disable_id_spin, 5, 3)
        self.disable_value_spin = CtrlSpin()
        grid.addWidget(self.disable_value_spin, 5, 4)
        disable_detect_btn = QtGui.QPushButton(QtGui.QIcon(':/icons/bolt.png'), '')
        disable_detect_btn.setToolTip('MIDI learn')
        disable_detect_btn.setCheckable(True)
        disable_detect_btn.clicked.connect(lambda value, btn=disable_detect_btn: self.detect_set(btn, value))
        self.detect_group.addButton(disable_detect_btn)
        self.detect_group.setId(disable_detect_btn, 1)
        grid.addWidget(disable_detect_btn, 5, 5)

        self.button_box = QtGui.QDialogButtonBox(QtGui.QDialogButtonBox.Ok|QtGui.QDialogButtonBox.Cancel)
        grid.addWidget(self.button_box, grid.rowCount(), 0, 1, 5)
        self.button_box.button(QtGui.QDialogButtonBox.Ok).clicked.connect(self.accept)
        self.button_box.button(QtGui.QDialogButtonBox.Cancel).clicked.connect(self.reject)

        parent.MidiEvent.connect(self.midi_event)


    def detect_set(self, btn, value):
        for other in self.detect_group.buttons():
            if other != btn and value:
                other.setChecked(False)
        self.detect = self.detect_group.id(btn) if value else None

    def toggle_set(self, value):
        label = 'Toggle {}' if value else 'Enable {}'
        self.enable_label.setText(label.format(self.name))
        self.disable_chan_spin.setEnabled(not value)
        self.disable_event_combo.setEnabled(not value)
        self.disable_id_spin.setEnabled(not value)
        self.disable_value_spin.setEnabled(not value)
        self.detect_group.buttons()[1].setEnabled(not value)
        if value and self.detect == 1:
            self.detect_group.buttons()[-1].setChecked(False)
            self.detect = None

    def midi_event(self, event):
        if self.detect is not None:
            if self.detect == 0:
                self.enable_chan_spin.setValue(event.channel+1)
                self.enable_event_combo.setEventType(event.type)
                self.enable_id_spin.setValue(event.data1)
                self.enable_value_spin.setValue(event.data2)
            if self.detect == 1 or self.toggle.isChecked():
                self.disable_chan_spin.setValue(event.channel+1)
                self.disable_event_combo.setEventType(event.type)
                self.disable_id_spin.setValue(event.data1)
                self.disable_value_spin.setValue(event.data2)
            self.detect_group.buttons()[self.detect].setChecked(False)
            self.detect = None

    def exec_(self, map_data=None):
        if map_data:
            if len(map_data) == 1:
                (chan, event_type, param), value = map_data[True]
                self.enable_chan_spin.setValue(chan+1)
                self.enable_event_combo.setEventType(event_type)
                self.enable_id_spin.setValue(param)
                self.enable_value_spin.setValue(value)
                self.toggle.setChecked(True)
            else:
                (chan, event_type, param), value = map_data[0]
                self.disable_chan_spin.setValue(chan+1)
                self.disable_event_combo.setEventType(event_type)
                self.disable_id_spin.setValue(param)
                self.disable_value_spin.setValue(value)
                (chan, event_type, param), value = map_data[1]
                self.enable_chan_spin.setValue(chan+1)
                self.enable_event_combo.setEventType(event_type)
                self.enable_id_spin.setValue(param)
                self.enable_value_spin.setValue(value)
        res = QtGui.QDialog.exec_(self)
        if not res:
            return False
        if self.toggle.isChecked():
            return [(self.enable_chan_spin.value()-1, self.enable_event_combo.model().item(self.enable_event_combo.currentIndex()).type, 
                    self.enable_id_spin.value(), self.enable_value_spin.value()), ]
        return [(self.disable_chan_spin.value()-1, self.disable_event_combo.model().item(self.disable_event_combo.currentIndex()).type, self.disable_id_spin.value(), self.disable_value_spin.value()), 
                (self.enable_chan_spin.value()-1, self.enable_event_combo.model().item(self.enable_event_combo.currentIndex()).type, self.enable_id_spin.value(), self.enable_value_spin.value())]


