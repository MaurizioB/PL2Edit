#!/usr/bin/env python2.7
# -*- coding: utf-8 -*-
#
# Copyright (C) 2016 Maurizio Berti <maurizio.berti@gmail.com>
#

import sys
from os import path
from copy import copy
from random import randrange
from PyQt4 import QtCore, QtGui, uic
import icons
from extra import *
from midiutils import *
from dialogs import *
from info import __version__, __codeurl__, __website__
simple_values = [0, 1]+[i for i in range(3, 25)]+[26]
bit_values = [2, 25]
ClientRole = 32
PortRole = 33

_path = path.dirname(path.abspath(__file__))
#print _path

def _load_ui(widget, ui_path):
    return uic.loadUi(path.join(_path, ui_path), widget)

class MidiSeq(QtCore.QObject):
    client_start = QtCore.pyqtSignal(object)
    client_exit = QtCore.pyqtSignal(object)
    port_start = QtCore.pyqtSignal(object)
    port_exit = QtCore.pyqtSignal(object)
    connection = QtCore.pyqtSignal(object)
    disconnection = QtCore.pyqtSignal(object)
    graph_changed = QtCore.pyqtSignal()
    stopped = QtCore.pyqtSignal()
    midi_signal = QtCore.pyqtSignal(object)

    def __init__(self, main):
        QtCore.QObject.__init__(self)
        self.main = main
        self.seq = alsaseq.Sequencer(clientname='PL2 editor')
        self.keep_going = True
        input1 = self.seq.create_simple_port(name = 'input1', 
                                                     type = alsaseq.SEQ_PORT_TYPE_APPLICATION, 
                                                     caps = alsaseq.SEQ_PORT_CAP_WRITE|alsaseq.SEQ_PORT_CAP_SUBS_WRITE)
        input2 = self.seq.create_simple_port(name = 'input2', 
                                                     type = alsaseq.SEQ_PORT_TYPE_APPLICATION, 
                                                     caps = alsaseq.SEQ_PORT_CAP_WRITE|alsaseq.SEQ_PORT_CAP_SUBS_WRITE)
        output1 = self.seq.create_simple_port(name = 'PL2 output1',
                                                type = alsaseq.SEQ_PORT_TYPE_APPLICATION,
                                                caps = alsaseq.SEQ_PORT_CAP_READ|alsaseq.SEQ_PORT_CAP_SUBS_READ)
        output2 = self.seq.create_simple_port(name = 'PL2 output2',
                                                type = alsaseq.SEQ_PORT_TYPE_APPLICATION,
                                                caps = alsaseq.SEQ_PORT_CAP_READ|alsaseq.SEQ_PORT_CAP_SUBS_READ)
        self.seq_output = [output1, output2]
        self.seq.connect_ports((alsaseq.SEQ_CLIENT_SYSTEM, alsaseq.SEQ_PORT_SYSTEM_ANNOUNCE), (self.seq.client_id, input1))
        self.main.CTRL.connect(self.ctrl_send)
        self.main.NOTEON.connect(self.noteon_send)
        self.main.NOTEOFF.connect(self.noteoff_send)
        self.main.PROGRAM.connect(self.program_send)
        self.main.PANIC.connect(self.panic_send)
        self.main.PITCHBEND.connect(self.pitchbend_send)
        self.main.SYSRESET.connect(self.sysreset_send)

        self.graph = Graph(self.seq)
        self.graph.client_start.connect(self.client_start)
        self.graph.client_exit.connect(self.client_exit)
        self.graph.port_start.connect(self.port_start)
        self.graph.port_exit.connect(self.port_exit)
        self.id = self.seq.get_client_info()['id']
        self.input = (self.graph.port_id_dict[self.id][input1], self.graph.port_id_dict[self.id][input2])
        self.output = (self.graph.port_id_dict[self.id][output1], self.graph.port_id_dict[self.id][output2])

    def run(self):
        while self.keep_going:
            event_list = self.seq.receive_events(timeout=1024, maxevents=1)
            for event in event_list:
                data = event.get_data()
                if event.type == alsaseq.SEQ_EVENT_CLIENT_START:
                    self.graph.client_created(data)
                elif event.type == alsaseq.SEQ_EVENT_CLIENT_EXIT:
                    self.graph.client_destroyed(data)
                elif event.type == alsaseq.SEQ_EVENT_PORT_START:
                    self.graph.port_created(data)
                elif event.type == alsaseq.SEQ_EVENT_PORT_EXIT:
                    self.graph.port_destroyed(data)
                elif event.type == alsaseq.SEQ_EVENT_PORT_SUBSCRIBED:
                    self.graph.conn_created(data)
                elif event.type == alsaseq.SEQ_EVENT_PORT_UNSUBSCRIBED:
                    self.graph.conn_destroyed(data)
#                elif event.type in [alsaseq.SEQ_EVENT_NOTEON, alsaseq.SEQ_EVENT_NOTEOFF, alsaseq.SEQ_EVENT_CONTROLLER, 
#                                    alsaseq.SEQ_EVENT_PGMCHANGE, alsaseq.SEQ_EVENT_SYSEX]:
                elif event.type in [alsaseq.SEQ_EVENT_CLOCK, alsaseq.SEQ_EVENT_SENSING]:
                    pass
                else:
                    try:
                        newev = MidiEvent.from_alsa(event)
                        self.midi_signal.emit(newev)
#                        print newev
#                        print newev
                    except Exception as e:
                        print 'event {} unrecognized'.format(event)
                        print e
        print 'MIDI engine stopped'
        self.stopped.emit()

    def event_send(self, *events):
        for event in events:
            self.seq.output_event(event.get_event())
        self.seq.drain_output()

    def alsa_event_send(self, *events):
        for event in events:
            self.seq.output_event(event)
        self.seq.drain_output()

    def ctrl_send(self, src_port, channel, param, value):
        if src_port > 1:
            evlist = [CtrlEvent.alsa_event(self.seq_output[0], channel[0], param, value), 
                        CtrlEvent.alsa_event(self.seq_output[1], channel[1], param, value)]
            self.alsa_event_send(*evlist)
        else:
            self.alsa_event_send(CtrlEvent.alsa_event(self.seq_output[src_port], channel, param, value))

    def noteon_send(self, src_port, channel, note, velocity):
        if src_port > 1:
            evlist = [NoteOnEvent.alsa_event(self.seq_output[0], channel[0], note, velocity), 
                        NoteOnEvent.alsa_event(self.seq_output[1], channel[1], note, velocity)]
            self.alsa_event_send(*evlist)
        else:
            self.alsa_event_send(NoteOnEvent.alsa_event(self.seq_output[src_port], channel, note, velocity))

    def noteoff_send(self, src_port, channel, note, velocity):
        if src_port > 1:
            evlist = [NoteOffEvent.alsa_event(self.seq_output[0], channel[0], note, velocity), 
                        NoteOffEvent.alsa_event(self.seq_output[1], channel[1], note, velocity)]
            self.alsa_event_send(*evlist)
        else:
            self.alsa_event_send(NoteOffEvent.alsa_event(self.seq_output[src_port], channel, note, velocity))

    def program_send(self, src_port, channel, program):
        if src_port > 1:
            evlist = [ProgramEvent.alsa_event(self.seq_output[0], channel[0], program), 
                        ProgramEvent.alsa_event(self.seq_output[1], channel[1], program)]
            self.alsa_event_send(*evlist)
        else:
            self.alsa_event_send(ProgramEvent.alsa_event(self.seq_output[src_port], channel, program))

    def pitchbend_send(self, src_port, channel, value):
        if src_port > 1:
            evlist = [PitchbendEvent.alsa_event(self.seq_output[0], channel[0], value), 
                        PitchbendEvent.alsa_event(self.seq_output[1], channel[1], value)]
            self.alsa_event_send(*evlist)
        else:
            self.alsa_event_send(PitchbendEvent.alsa_event(self.seq_output[src_port], channel, value))

    def sysreset_send(self, src_port, *args):
        if src_port > 1:
            evlist = [SysRtResetEvent.alsa_event(self.seq_output[0]), 
                        SysRtResetEvent.alsa_event(self.seq_output[1])]
            self.alsa_event_send(*evlist)
        else:
            self.alsa_event_send(SysRtResetEvent.alsa_event(self.seq_output[src_port]))

    def panic_send(self, src_port, channel=1):
        event_id_list = [64, 120, 123]
        if src_port > 1:
            evlist = [CtrlEvent.alsa_event(self.seq_output[port], channel[port], param, 0) for param in event_id_list for port in range(2)]
            self.alsa_event_send(*evlist)
        else:
            self.alsa_event_send(*[CtrlEvent.alsa_event(self.seq_output[src_port], channel, param, 0) for param in event_id_list])

class MidiDialog(QtGui.QDialog):
    def __init__(self, parent, seq):
        QtGui.QDialog.__init__(self, parent)
#        uic.loadUi('midi.ui', self)
        _load_ui(self, 'midi.ui')
        self.parent = parent
        self.seq = seq
        self.graph = self.seq.graph
        self.graph.graph_changed.connect(self.refresh_all)
        self.input = self.seq.input
        self.output = self.seq.output
        self.refresh_all()
        self.refresh_btn.clicked.connect(self.refresh_all)

        self.midi1_input_chan_spin.setValue(self.parent._input1_channel)
        self.midi1_output_chan_spin.setValue(self.parent._channel1)
        self.midi2_input_chan_spin.setValue(self.parent._input2_channel)
        self.midi2_output_chan_spin.setValue(self.parent._channel2)

        self.midi1_input_listview.doubleClicked.connect(self.port_connect_toggle)
        self.midi2_input_listview.doubleClicked.connect(self.port_connect_toggle)
        self.midi1_output_listview.doubleClicked.connect(self.port_connect_toggle)
        self.midi2_output_listview.doubleClicked.connect(self.port_connect_toggle)
        self.midi1_input_listview.customContextMenuRequested.connect(self.port_menu)
        self.midi2_input_listview.customContextMenuRequested.connect(self.port_menu)
        self.midi1_output_listview.customContextMenuRequested.connect(self.port_menu)
        self.midi2_output_listview.customContextMenuRequested.connect(self.port_menu)
        self.midi1_input_chan_spin.valueChanged.connect(self.channel_set)
        self.midi2_input_chan_spin.valueChanged.connect(self.channel_set)
        self.midi1_output_chan_spin.valueChanged.connect(self.channel_set)
        self.midi2_output_chan_spin.valueChanged.connect(self.channel_set)

    def _create_channel_model(self):
        model = QtGui.QStandardItemModel()
        omni = QtGui.QStandardItem('omni')
        model.appendRow(omni)
        for i in range(1, 17):
            item = QtGui.QStandardItem(str(i))
            model.appendRow(item)
        return model

    def _get_port_from_item_data(self, model, index):
        return self.graph.port_id_dict[model.data(index, ClientRole).toInt()[0]][model.data(index, PortRole).toInt()[0]]

    def port_menu(self, pos):
        sender = self.sender()
        model = sender.model()
        index = sender.indexAt(pos)
        item = model.item(index.row())
        actions = []
        if item.isEnabled():
            port = self._get_port_from_item_data(model, index)
            if (sender == self.midi1_input_listview and self.input[0] in [conn.dest for conn in port.connections.output]) or\
                (sender == self.midi2_input_listview and self.input[1] in [conn.dest for conn in port.connections.output]) or\
                (sender == self.midi1_output_listview and self.output[0] in [conn.src for conn in port.connections.input]) or\
                (sender == self.midi2_output_listview and self.output[1] in [conn.src for conn in port.connections.input]):
                disconnect_action = QtGui.QAction('Disconnect', self)
                disconnect_action.triggered.connect(lambda: self.port_connect_toggle(index, sender))
                actions.append(disconnect_action)
            else:
                connect_action = QtGui.QAction('Connect', self)
                connect_action.triggered.connect(lambda: self.port_connect_toggle(index, sender))
                actions.append(connect_action)
            sep = QtGui.QAction(self)
            sep.setSeparator(True)
            actions.append(sep)
        disconnect_all_action = QtGui.QAction('Disconnect all', self)
        actions.append(disconnect_all_action)
        if sender == self.midi1_input_listview:
            disconnect_all_action.triggered.connect(lambda: self.input[0].disconnect_all())
        elif sender == self.midi2_input_listview:
            disconnect_all_action.triggered.connect(lambda: self.input[1].disconnect_all())
        elif sender == self.midi1_output_listview:
            disconnect_all_action.triggered.connect(lambda: self.output[0].disconnect_all())
        elif sender == self.midi2_output_listview:
            disconnect_all_action.triggered.connect(lambda: self.output[1].disconnect_all())

        menu = QtGui.QMenu()
        menu.addActions(actions)
        menu.exec_(sender.mapToGlobal(pos))

    def port_connect_toggle(self, index, sender=None):
        if sender is None:
            sender = self.sender()
        if sender == self.midi1_input_listview:
            port = self._get_port_from_item_data(self.midi1_input_model, index)
            if self.input[0] in [conn.dest for conn in port.connections.output]:
                port.disconnect(self.input[0])
            else:
                port.connect(self.input[0])
        elif sender == self.midi2_input_listview:
            port = self._get_port_from_item_data(self.midi2_input_model, index)
            if self.input[1] in [conn.dest for conn in port.connections.output]:
                port.disconnect(self.input[1])
            else:
                port.connect(self.input[1])
        elif sender == self.midi1_output_listview:
            port = self._get_port_from_item_data(self.midi1_output_model, index)
            if self.output[0] in [conn.src for conn in port.connections.input]:
                self.output[0].disconnect(port)
            else:
                self.output[0].connect(port)
        elif sender == self.midi2_output_listview:
            port = self._get_port_from_item_data(self.midi2_output_model, index)
            if self.output[1] in [conn.src for conn in port.connections.input]:
                self.output[1].disconnect(port)
            else:
                self.output[1].connect(port)

    def refresh_all(self):
        self.midi1_input_model = QtGui.QStandardItemModel()
        self.midi1_input_listview.setModel(self.midi1_input_model)
        self.midi1_output_model = QtGui.QStandardItemModel()
        self.midi1_output_listview.setModel(self.midi1_output_model)
        self.midi2_input_model = QtGui.QStandardItemModel()
        self.midi2_input_listview.setModel(self.midi2_input_model)
        self.midi2_output_model = QtGui.QStandardItemModel()
        self.midi2_output_listview.setModel(self.midi2_output_model)
        for client in [self.graph.client_id_dict[cid] for cid in sorted(self.graph.client_id_dict.keys())]:
            in1_client_item = QtGui.QStandardItem('{} ({})'.format(client.name, client.id))
            in2_client_item = QtGui.QStandardItem('{} ({})'.format(client.name, client.id))
            out1_client_item = QtGui.QStandardItem('{} ({})'.format(client.name, client.id))
            out2_client_item = QtGui.QStandardItem('{} ({})'.format(client.name, client.id))
            in_port_list = []
            out_port_list = []
            for port in client.ports:
                if port.hidden:
                    continue
                if port.is_output:
                    in_port_list.append(port)
                if port.is_input:
                    out_port_list.append(port)
            if len(in_port_list):
                self.midi1_input_model.appendRow(in1_client_item)
                self.midi2_input_model.appendRow(in2_client_item)
                in1_client_item.setEnabled(False)
                in2_client_item.setEnabled(False)
                for port in in_port_list:
                    in1_item = QtGui.QStandardItem('  {}'.format(port.name))
                    in2_item = QtGui.QStandardItem('  {}'.format(port.name))
                    self.midi1_input_model.appendRow(in1_item)
                    self.midi2_input_model.appendRow(in2_item)
                    in1_item_index = self.midi1_input_model.indexFromItem(in1_item)
                    self.midi1_input_model.setData(in1_item_index, QtCore.QVariant(client.id), ClientRole)
                    self.midi1_input_model.setData(in1_item_index, QtCore.QVariant(port.id), PortRole)
                    in2_item_index = self.midi2_input_model.indexFromItem(in2_item)
                    self.midi2_input_model.setData(in2_item_index, QtCore.QVariant(client.id), ClientRole)
                    self.midi2_input_model.setData(in2_item_index, QtCore.QVariant(port.id), PortRole)
                    if any([conn for conn in port.connections.output if conn.dest == self.input[0]]):
                        self.midi1_input_model.setData(in1_item_index, QtGui.QBrush(QtCore.Qt.blue), QtCore.Qt.ForegroundRole)
                        setBold(in1_item)
                    else:
                        self.midi1_input_model.setData(in1_item_index, QtGui.QBrush(QtCore.Qt.black), QtCore.Qt.ForegroundRole)
                        setBold(in1_item, False)
                    if any([conn for conn in port.connections.output if conn.dest == self.input[1]]):
                        self.midi2_input_model.setData(in2_item_index, QtGui.QBrush(QtCore.Qt.blue), QtCore.Qt.ForegroundRole)
                        setBold(in2_item)
                    else:
                        self.midi2_input_model.setData(in2_item_index, QtGui.QBrush(QtCore.Qt.black), QtCore.Qt.ForegroundRole)
                        setBold(in2_item, False)
            if len(out_port_list):
                self.midi1_output_model.appendRow(out1_client_item)
                self.midi2_output_model.appendRow(out2_client_item)
                out1_client_item.setEnabled(False)
                out2_client_item.setEnabled(False)
                for port in out_port_list:
                    out1_item = QtGui.QStandardItem('  {}'.format(port.name))
                    out2_item = QtGui.QStandardItem('  {}'.format(port.name))
                    self.midi1_output_model.appendRow(out1_item)
                    self.midi2_output_model.appendRow(out2_item)
                    out1_item_index = self.midi1_output_model.indexFromItem(out1_item)
                    self.midi1_output_model.setData(out1_item_index, QtCore.QVariant(client.id), ClientRole)
                    self.midi1_output_model.setData(out1_item_index, QtCore.QVariant(port.id), PortRole)
                    out2_item_index = self.midi2_output_model.indexFromItem(out2_item)
                    self.midi2_output_model.setData(out2_item_index, QtCore.QVariant(client.id), ClientRole)
                    self.midi2_output_model.setData(out2_item_index, QtCore.QVariant(port.id), PortRole)
                    if any([conn for conn in port.connections.input if conn.src == self.output[0]]):
                        self.midi1_output_model.setData(out1_item_index, QtGui.QBrush(QtCore.Qt.blue), QtCore.Qt.ForegroundRole)
                        setBold(out1_item)
                    else:
                        self.midi1_output_model.setData(out1_item_index, QtGui.QBrush(QtCore.Qt.black), QtCore.Qt.ForegroundRole)
                        setBold(out1_item, False)
                    if any([conn for conn in port.connections.input if conn.src == self.output[1]]):
                        self.midi2_output_model.setData(out2_item_index, QtGui.QBrush(QtCore.Qt.blue), QtCore.Qt.ForegroundRole)
                        setBold(out2_item)
                    else:
                        self.midi2_output_model.setData(out2_item_index, QtGui.QBrush(QtCore.Qt.black), QtCore.Qt.ForegroundRole)
                        setBold(out2_item, False)

        cx_text = [
                   (self.input[0].connections.input, self.input1_lbl, 'INPUT'), 
                   (self.input[1].connections.input, self.input2_lbl, 'INPUT'), 
                   (self.output[0].connections.output, self.output1_lbl, 'OUTPUT'), 
                   (self.output[1].connections.output, self.output2_lbl, 'OUTPUT'), 
                   ]
        for cx, lbl, ptxt in cx_text:
            n_conn = len([conn for conn in cx if not conn.hidden])
            cx_txt = ptxt
            if not n_conn:
                cx_txt += ' (not connected)'
            elif n_conn == 1:
                cx_txt += ' (1 connection)'
            else:
                cx_txt += ' ({} connections)'.format(n_conn)
            lbl.setText(cx_txt)

    def channel_set(self, value):
        sender = self.sender()
        if not sender:
            return
        value -= 1
        if sender == self.midi1_input_chan_spin:
            self.parent.input1_channel = value
        elif sender == self.midi2_input_chan_spin:
            self.parent.input2_channel = value
        elif sender == self.midi1_output_chan_spin:
            self.parent._channel1 = value
        elif sender == self.midi2_output_chan_spin:
            self.parent._channel2 = value

class SettingsDialog(QtGui.QDialog):
    def __init__(self, parent):
        QtGui.QDialog.__init__(self, parent)
#        uic.loadUi('settings.ui', self)
        _load_ui(self, 'settings.ui')
        self.settings = parent.settings
        self.last_pgm_check.setChecked(True if self.settings.gGeneral.get_last_program(0, save=True) >= 0 else False)
        self.last_pgm_check.toggled.connect(self.last_program)
        self.conn_check.setChecked(self.settings.gGeneral.get_remember_connections(True, save=True))
        self.conn_check.toggled.connect(self.settings.gGeneral.set_remember_connections)
        self.buttonBox.button(QtGui.QDialogButtonBox.Ok).clicked.connect(self.close)

    def last_program(self, value):
        self.settings.gGeneral.set_last_program(self.parent().current_program if value else -1)

    def close(self):
        self.settings.sync()
        self.hide()

class Editor(QtGui.QMainWindow):
    CTRL = QtCore.pyqtSignal(int, object, int, int)
    NOTEON = QtCore.pyqtSignal(int, object, int, int)
    NOTEOFF = QtCore.pyqtSignal(int, object, int, int)
    PITCHBEND = QtCore.pyqtSignal(int, object, int)
    PANIC = QtCore.pyqtSignal(int, object)
    PROGRAM = QtCore.pyqtSignal(int, object, int)
    SYSRESET = QtCore.pyqtSignal(int)
    MidiEvent = QtCore.pyqtSignal(object)

    def __init__(self, backend='alsa'):
        QtGui.QMainWindow.__init__(self, parent=None)
#        uic.loadUi('editor.ui', self)
        _load_ui(self, 'editor.ui')
        app = QtGui.QApplication.instance()
        app.installEventFilter(self)

        self.piano = Piano(self)
        self.piano.setObjectName('piano')
        self.keyboard_layout.addWidget(self.piano)
        self.template_file = None
        self.clipboard = None
        self.toolbar_fill()
        self.connections()
        self.local = True
        self.map_dict = {}
        self.mapping = False
        self.map_dialog = None
        self.keyboard = False
        self.keyboard_shift = 1
        self.pitchbend = False
        metrics = QtGui.QFontMetrics(self.waveform_combo.font())
        self.portamento_lbl.setMinimumWidth(metrics.width('BD Rel. Time:'))

        self.velocity = self.velocity_spin.value()
        self.mod_wheel = self.mod_spin.value()

        #midi thread
        self.midiseq_thread = QtCore.QThread()
        self.midiseq = MidiSeq(self)
        self.midiseq.moveToThread(self.midiseq_thread)
        self.midiseq.stopped.connect(self.midiseq_thread.quit)
        self.midiseq_thread.started.connect(self.midiseq.run)
        self.midiseq.midi_signal.connect(self.midi_event)
        self.midiseq_thread.start()

        self.output_combo.currentIndexChanged.connect(self.output_set)

        self.qsettings = QtCore.QSettings('jidesk', 'PL2 editor')
        self.settings = SettingsObj(self.qsettings)
        self.start_connections()

        #applying settings
        self._input1_channel = self.settings.gMIDI.get_Input1_channel(-1, True)
        self._input2_channel = self.settings.gMIDI.get_Input2_channel(-1, True)
        self._channel1 = self.settings.gMIDI.get_Output1_channel(0, True)
        self._channel2 = self.settings.gMIDI.get_Output2_channel(0, True)
        self.output = self.settings.gGeneral.get_Output(0, True)
        self.output_combo.blockSignals(True)
        self.output_combo.setCurrentIndex(self.output)
        self.output_combo.blockSignals(False)

        #preload (widget labels, etc), *might* be not necessary
        self.controller3Mode_combo.setCurrentIndex(0)
        self.controller3_change(0)
        self.priority_combo.setCurrentIndex(0)
        self.local = False

        last_program = self.settings.gGeneral.get_last_program(0)
        if last_program <= 0:
            last_program = 0
        self.current_program = last_program
        self.program_combo.setCurrentIndex(last_program)

        self.midi_dialog = MidiDialog(self, self.midiseq)
        self.settings_dialog = SettingsDialog(self)
        self.actionMidiShow.triggered.connect(self.midi_dialog.show)
        self.actionSettings.triggered.connect(self.settings_dialog.show)

    def start_connections(self):
        if self.settings.gGeneral.get_remember_connections(True):
            graph = self.midiseq.graph
            client_name_dict = copy(graph.client_name_dict)
            conn_tuples = [
                           (self.midiseq.input[0], self.settings.gMIDI.Input1), 
                           (self.midiseq.input[1], self.settings.gMIDI.Input2), 
                           (self.midiseq.output[0], self.settings.gMIDI.Output1), 
                           (self.midiseq.output[1], self.settings.gMIDI.Output2), 
                           ]
            for my_port, ext_port in conn_tuples:
                if not ext_port: continue
                for (client_name, port_name), (client_id, port_id) in ext_port:
                    client_id_got_list = client_name_dict.get(client_name, [])
                    for client_id_got in client_id_got_list:
                        if client_id_got and graph.port_id_dict.get(client_id_got).get(port_id):
                            my_port.connect(client_id, port_id)


    def toolbar_fill(self):
        program_label = QtGui.QLabel('  Program:')
        self.toolBar.insertWidget(self.actionStore, program_label)
        self.program_combo = QtGui.QComboBox()
        self.program_combo.setEditable(True)
        self.program_combo.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)
        self.program_combo.setInsertPolicy(QtGui.QComboBox.NoInsert)
        self.program_model = QtGui.QStandardItemModel()
        for i, p in enumerate(Programs):
            item = QtGui.QStandardItem('{} {}'.format(i+1, p))
            item.prog_data = parse_prog_data('presets/{:02d}.pl2'.format(i+1))
            self.program_model.appendRow(item)
        for p in range(33, 65):
            item = QtGui.QStandardItem('{} User'.format(p))
            item.prog_data = None
            setItalic(item)
            self.program_model.appendRow(item)
        self.program_combo.setModel(self.program_model)
        self.program_combo.currentIndexChanged.connect(self.program_change)
        self.toolBar.insertWidget(self.actionStore, self.program_combo)
        for action in self.toolBar.actions():
            action.setIconText(action.text())

        self.actionStore.triggered.connect(self.program_store)
        self.actionRestore.triggered.connect(self.program_restore)
        self.actionRename.triggered.connect(self.program_rename)
        self.actionCopy.triggered.connect(self.program_copy)
        self.actionPaste.triggered.connect(self.program_paste)
        self.actionProgramLoad.triggered.connect(self.program_load)
        self.actionMenuProgramLoad.triggered.connect(self.program_load)
        self.actionProgramSave.triggered.connect(self.program_save)
        self.actionMenuProgramSave.triggered.connect(self.program_save)
        self.actionFactoryDefault.triggered.connect(self.program_factory)
        self.actionRandom.triggered.connect(self.program_random)
        self.actionPaste.setEnabled(False)
        self.actionOpenTemplate.triggered.connect(self.template_open)
        self.actionSaveTemplate.triggered.connect(self.template_save)
        self.actionSaveTemplateAs.triggered.connect(self.template_save_as)
        self.actionAbout.triggered.connect(self.about)
        self.actionAboutQt.triggered.connect(lambda: QtGui.QMessageBox.aboutQt(self))

        QtGui.QIcon.setThemeName(QtGui.QApplication.style().objectName())
        icon_dict = {self.actionStore: 'edit-redo', self.actionRestore: 'edit-undo', self.actionCopy: 'edit-copy', self.actionPaste: 'edit-paste', 
                     self.actionRename: 'edit-rename', self.actionProgramLoad: 'document-open', self.actionProgramSave: 'document-save', 
                     self.actionFactoryDefault: 'dialog-ok', self.actionRandom: 'view-refresh', 
                     self.actionOpenTemplate: 'document-open', self.actionSaveTemplate: 'document-save', self.actionSaveTemplateAs: 'document-save-as', 
                     self.actionMenuProgramLoad: 'document-open', self.actionMenuProgramSave: 'document-save', 
                     self.actionQuit: 'application-exit'}
        for widget, icon in icon_dict.items():
            widget.setIcon(QtGui.QIcon.fromTheme(icon))


    @property
    def channel(self):
        if self.output == 0:
            return self._channel1
        elif self.output == 1:
            return self._channel2
        else:
            return (self._channel1, self._channel2)

    @property
    def input1_channel(self):
        return self._input1_channel

    @input1_channel.setter
    def input1_channel(self, value):
        self._input1_channel = value
        self.settings.gMIDI.set_Input1_channel(value)

    @property
    def input2_channel(self):
        return self._input2_channel

    @input2_channel.setter
    def input2_channel(self, value):
        self._input2_channel = value
        self.settings.gMIDI.set_Input2_channel(value)

    def output_set(self, index):
        self.output = index
        self.settings.gGeneral.set_Output(self.output)

    def program_change(self, index):
        self.current_program = index
        if self.settings.gGeneral.get_last_program(0) >= 0:
            self.settings.gGeneral.set_last_program(index)
        custom = True if index >= 32 else False
        prog_data = self.program_model.item(index).prog_data
        if not custom:
            self.actionProgramSave.setEnabled(True)
            self.actionMenuProgramSave.setEnabled(True)
        else:
#            if prog_data and all([True if x >= 0 else False for x in prog_data]):
            if prog_data and all(False for x in prog_data if x < 0):
                self.actionProgramSave.setEnabled(True)
                self.actionMenuProgramSave.setEnabled(True)
            else:
                self.actionProgramSave.setEnabled(False)
                self.actionMenuProgramSave.setEnabled(False)
        self.actionStore.setEnabled(custom)
        self.actionRename.setEnabled(custom)
        self.panic()
        self.PROGRAM.emit(self.output, self.channel, index)
        self.program_set(prog_data)

    def program_set(self, prog_data, send=False):
        if not prog_data:
            self.local = True
            for data in self.ctrl_dict.items():
                widget = data.widget
                label = data.label if data.label else widget
                setItalic(label)
                if isinstance(widget, QtGui.QComboBox):
                    widget.setCurrentIndex(-1)
                elif isinstance(widget, QtGui.QSpinBox):
                    widget.setMinimum(-1)
                    widget.setSpecialValueText('???')
                    widget.setValue(-1)
                else:
                    widget.setChecked(False)
            self.local = False
            return
        self.local = True
        signal_list = []
        for i in simple_values:
            data = self.ctrl_dict.get_id(i)
            widget = data.widget
            label = data.label if data.label else widget
            value = prog_data[i]
            if value < 0:
                setItalic(label)
            else:
                setItalic(label, False)
            if isinstance(widget, QtGui.QSpinBox):
                widget.setValue(value)
                if value >= 0:
                    widget.setSpecialValueText('')
                    widget.setMinimum(0)
                else:
                    widget.setMinimum(-1)
                    widget.setSpecialValueText('???')
                    widget.setValue(-1)
                signal_list.append((widget.valueChanged, value))
            elif isinstance(widget, QtGui.QComboBox):
                widget.setCurrentIndex(value)
                signal_list.append((widget.currentIndexChanged, value))
            else:
                value = True if value == 64 else False
                widget.setChecked(value)
                signal_list.append((widget.toggled, value))
        for index in bit_values:
            value = prog_data[index]
            bits = bit_convert(value)
            for i, data in enumerate(self.ctrl_dict.get_id(index)):
                label = data.label if data.label else data.widget
                if value >= 0:
                    setItalic(label, False)
                    if data.ext[0] < data.ext[1]:
                        div = base2.index(data.ext[1])
                        pos = 0, 1
                    else:
                        div = base2.index(data.ext[0])
                        pos = 1, 0
                    value = pos[bits[div]]
                else:
                    setItalic(label)
                    value = -1
                if isinstance(data.widget, QtGui.QCheckBox):
                    data.widget.setChecked(value if value >= 0 else False)
                    signal = data.widget.toggled
                else:
                    data.widget.setCurrentIndex(value)
                    signal = data.widget.currentIndexChanged
            signal_list.append((signal, value))
        self.local = False
        if send:
            for signal, value in signal_list:
                signal.emit(value)

    def program_store(self):
        index = self.program_combo.currentIndex()
        self.PROGRAM.emit(self.output, self.channel, 0)
        QtCore.QTimer.singleShot(200, lambda: self.PROGRAM.emit(self.output, self.channel, index))

    def program_restore(self):
        index = self.program_combo.currentIndex()
        item = self.program_model.item(index)
        #sysrt + panic + program
        if index >= 32:
            item.prog_data = None
            item.setText('{} User'.format(index+1))
            setBold(item, False)
            setItalic(item)
            self.program_set(None)
        self.sysreset_send(self.panic, lambda: self.PROGRAM.emit(self.output, self.channel, index))

    def program_rename(self):
        index = self.program_combo.currentIndex()
        item = self.program_model.item(index)
        name, res = QtGui.QInputDialog.getText(self, 'Rename user program', 'Please enter the name for user program {}:'.format(index+1), text=item.text())
        if res:
            item.setText(name)
            setItalic(item, False)

    def program_copy(self):
        index = self.program_combo.currentIndex()
        item = self.program_model.item(index)
        prog_data = item.prog_data
        if prog_data:
            self.clipboard = copy(prog_data)
            self.actionPaste.setEnabled(True)

    def program_paste(self):
        if not self.clipboard:
            return
        index = self.program_combo.currentIndex()
        item = self.program_model.item(index)
        self.program_set(self.clipboard, True)
        item.prog_data = self.clipboard

    def program_save(self):
        prog_data = self.program_model.item(self.program_combo.currentIndex()).prog_data
        if not all(False for x in prog_data if x < 0):
            return
        file_data = 'PL2*'
        for i in prog_data:
            file_data += '(1,{})'.format(i)
        file_data += '-\x00'
        index = self.program_combo.currentIndex()
        name = str(self.program_model.item(index).text().toLatin1())
        prefix = '{} '.format(index+1)
        if name.startswith(prefix) and name.lower() != '{} user'.format(index+1).lower():
            name = name[len(prefix):]
        res = QtGui.QFileDialog.getSaveFileName(self, 'Save PL2 program to...', './{}.pl2'.format(name), filter=('PL2 program files (*.pl2)'))
        if not res:
            return
        try:
            with open(res, 'wb') as out_file:
                out_file.write(file_data)
        except:
            QtGui.QMessageBox.critical(self, 'Error writing file', 'There was an error writing the PL2 program file')

    def program_load(self):
        res = QtGui.QFileDialog.getOpenFileName(self, 'Open PL2 program', filter='PL2 program files (*.pl2);;Any files (*)')
        if res:
            prog_data = parse_prog_data(res)
            if prog_data in [None, False]:
                QtGui.QMessageBox.critical(self, 'Error opening file', 'There was an error loading the PL2 program file')
                return
            self.program_set(prog_data, True)
            index = self.program_combo.currentIndex()
            item = self.program_model.item(index)
            item.prog_data = prog_data
            if index >= 32:
                name = path.basename(str(res.toLatin1()))
                if name.endswith('.pl2'):
                    name = name[:-4]
                item.setText(name)
                setItalic(item, False)

    def program_factory(self):
        index = self.program_combo.currentIndex()
        item = self.program_model.item(index)
        i = 1 if index < 32 else -31
        prog_data = parse_prog_data('presets/{:02d}.pl2'.format(index+i))
        item.prog_data = prog_data
        if index < 32:
            if self.output > 1:
                self.sysreset_send(self.panic, lambda: self.program_set(prog_data), ProgramEvent(0, self.channel[0], index), ProgramEvent(1, self.channel[1], index))
            else:
                self.sysreset_send(self.panic, lambda: self.program_set(prog_data), ProgramEvent(self.output, self.channel, index))
        else:
            self.program_set(prog_data, True)

    def program_random(self):
        for widget in self.ctrl_dict.get_widget_list():
            if isinstance(widget, QtGui.QComboBox):
                widget.setCurrentIndex(randrange(widget.model().rowCount()))
            elif isinstance(widget, QtGui.QSpinBox):
                widget.setValue(randrange(128))
            else:
                widget.setChecked(randrange(2))

    def sysreset_send(self, *args):
        object_list = [(o, o.isEnabled()) for o in self.centralWidget().children() if isinstance(o, QtGui.QWidget)]
        object_list.extend([(self.toolBar, True), (self.menubar, True)])
        for o, v in object_list:
            o.setEnabled(False)
        def delayed():
            for arg in args:
                if isinstance(arg, MidiEvent):
                    self.midiseq.event_send(arg)
                else:
                    arg()
            for o, e in object_list:
                o.setEnabled(e)
        self.SYSRESET.emit(self.output)
        timer = QtCore.QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(delayed)
        timer.start(1000)

    def template_open(self):
        res = QtGui.QFileDialog.getOpenFileName(self, 'Open PL2 template...', filter=('PL2 template files (*.pl2t)'))
        if not res:
            return
        try:
            data = '{'
            with open(res, 'rb') as f:
                for l in f.readlines():
                    data += l
                    data += ','
            data += '}'
            data = eval(data)
            print data
        except:
            QtGui.QMessageBox.critical(self, 'Error reading file', 'There was an error loading the PL2 template file')
            return
        map_dict = data[MapDict]
        self.map_dict = {}
        for event, event_dict in map_dict.items():
            self.map_dict[event] = {}
            for target_value, event_list in event_dict.items():
                self.map_dict[event][target_value] = []
                for target, value in event_list:
                    self.map_dict[event][target_value].append((getattr(self, target), value))
        for prog_id, prog_data, prog_name in data[ProgData]:
            if not 32 <= prog_id < 64 or not prog_data or len(prog_data) != 27:
                continue
            item = self.program_model.item(prog_id)
            item.prog_data = prog_data
            if prog_name:
                item.setText(prog_name)
                setBold(item)
                setItalic(item, False)


    def template_save(self):
        if not self.template_file:
            self.template_save_as()
        else:
            self.template_write(self.template_file)

    def template_save_as(self):
        if self.template_file and str(self.template_file).endswith('pl2t'):
            name = path.basename(self.template_file)
        else:
            name = ''
        res = QtGui.QFileDialog.getSaveFileName(self, 'Save PL2 template to...', name, filter=('PL2 template files (*.pl2t)'))
        if not res:
            return
        self.template_file = res
        self.template_write(res)

    def template_write(self, file_path):
        prog_list = []
        for p in range(32, 64):
            prog_item = self.program_model.item(p)
            prog_data = prog_item.prog_data
            prog_name = str(prog_item.text().toLatin1())
            if prog_data is not None:
                if prog_name == '{} User'.format(p+1):
                    prog_name = None
                prog_list.append((p, prog_data, prog_name))
        map_dict = {}
        for event, event_dict in self.map_dict.items():
            map_dict[event] = {}
            for target_value, event_list in event_dict.items():
                map_dict[event][target_value] = []
                for target, value in event_list:
                    map_dict[event][target_value].append((str(target.objectName()), value))
        file_data = 'MapDict: {}'.format(map_dict)
        file_data += '\nProgData: {}'.format(prog_list)
        try:
            with open(file_path, 'wb') as out_file:
                out_file.write(file_data)
        except:
            QtGui.QMessageBox.critical(self, 'Error writing file', 'There was an error writing the PL2 template file')


    def eventFilter(self, source, event):
        if source == self:
            if event.type() == QtCore.QEvent.KeyPress and not event.isAutoRepeat() and self.keyboard and event.text() in key_letters:
                self.piano.keys[key_letters.index(event.text())+self.keyboard_shift*12].mousePressEvent(None)
            elif event.type() == QtCore.QEvent.KeyRelease and not event.isAutoRepeat() and self.keyboard and event.text() in key_letters:
                self.piano.keys[key_letters.index(event.text())+self.keyboard_shift*12].mouseReleaseEvent(None)
#            elif event.type() == QtCore.QEvent.WindowDeactivate:
#                self.panic()
#                self.piano.all_notes_off()
        return QtGui.QMainWindow.eventFilter(self, source, event)

    def connections(self):
        for key in self.piano.keys:
            key.NoteOn.connect(self.noteon_send)
            key.NoteOff.connect(self.noteoff_send)

        self.showKeyboard_chk.toggled.connect(self.keyboard_enable)
        self.create_controller3_models()
        self.panic_btn.clicked.connect(self.panic)
        self.velocity_spin.valueChanged.connect(lambda value: self.sibling_change(value, self.velocity_slider))
        self.velocity_spin.valueChanged.connect(self.velocity_change)
        self.velocity_slider.valueChanged.connect(lambda value: self.sibling_change(value, self.velocity_spin))
        self.velocity_slider.valueChanged.connect(self.velocity_change)
        self.velocity_spin.label_text = 'Keyboard velocity'
        self.velocity_spin.customContextMenuRequested.connect(self.widget_menu)
        self.velocity_slider.customContextMenuRequested.connect(lambda pos: self.widget_menu(pos, self.velocity_spin))

        self.mod_spin.valueChanged.connect(lambda value: self.sibling_change(value, self.mod_slider))
        self.mod_slider.valueChanged.connect(lambda value: self.sibling_change(value, self.mod_spin))
        self.mod_spin.valueChanged.connect(self.mod_send)
        self.mod_slider.valueChanged.connect(self.mod_send)
        self.mod_spin.customContextMenuRequested.connect(self.widget_menu)
        self.mod_slider.customContextMenuRequested.connect(lambda pos: self.widget_menu(pos, self.mod_spin))

        self.pitch_slider.valueChanged.connect(self.pitch_send)
        self.pitch_slider.leaveEvent = self.pitch_out
        self.pitch_slider.mouseReleaseEvent = self.pitch_rel
        self.pitch_chk.toggled.connect(self.pitch_set)

        self.ctrl_dict = MultiList('controller widget name id', 'ctrl ext func label', unique=False)

        self.controller3Mode_combo.currentIndexChanged.connect(self.valueChanged)
        self.controller3Mode_combo.currentIndexChanged.connect(self.controller3_change)
        self.controller3Mode_combo.customContextMenuRequested.connect(self.widget_menu)
        self.ctrl_dict.append('controller3Mode', self.controller3Mode_combo, 'Controller #3 mode', 26, 3, None, None, self.controller3Mode_lbl)

        self.oscMode_combo.currentIndexChanged.connect(self.valueChanged)
        self.oscMode_combo.customContextMenuRequested.connect(lambda pos: self.widget_menu(pos, self.oscMode_combo))
        self.ctrl_dict.append('oscMode', self.oscMode_combo, 'Oscillator mode', 0, ((26, 27), (26, 27), (27,), (26,)), (126, 127, 26, 27), self.oscMode_send, self.oscMode_lbl)

        self.waveform_combo.currentIndexChanged.connect(self.waveform_change)
        self.waveform_combo.currentIndexChanged.connect(self.valueChanged)
        self.waveform_combo.customContextMenuRequested.connect(lambda pos: self.widget_menu(pos, self.waveform_combo))
        self.ctrl_dict.append('waveform', self.waveform_combo, 'Waveform', 1, 24, (0, 32, 64, 96), None, self.waveform_lbl)

        self.priority_after_values = {self.priority_combo: 0, self.aftertouch_chk: 0}
        self.priority_combo.currentIndexChanged.connect(self.priority_after_change)
        self.priority_combo.customContextMenuRequested.connect(lambda pos: self.widget_menu(pos, self.priority_combo))
        self.aftertouch_chk.toggled.connect(self.priority_after_change)
        self.aftertouch_chk.customContextMenuRequested.connect(lambda pos: self.widget_menu(pos, self.aftertouch_chk))
        self.ctrl_dict.append('priority', self.priority_combo, 'Priority', 2, 89, (64, 0), self.priority_after_send, self.priority_lbl)
        self.ctrl_dict.append('aftertouch', self.aftertouch_chk, 'Aftertouch', 2, 89, (0, 32), self.priority_after_send, None)

        self.portamento_chk.toggled.connect(self.valueChanged)
        self.portamento_chk.customContextMenuRequested.connect(self.widget_menu)
        self.ctrl_dict.append('portamento', self.portamento_chk, 'Portamento', 3, 65, (0, 64), None, None)

        self.portamentoTime_slider.focusInEvent = self.tab_rewrite
        self.portamentoTime_spin.valueChanged.connect(lambda value: self.sibling_change(value, self.portamentoTime_slider))
        self.portamentoTime_slider.valueChanged.connect(lambda value: self.sibling_change(value, self.portamentoTime_spin))
        self.portamentoTime_spin.valueChanged.connect(self.valueChanged)
        self.portamentoTime_slider.valueChanged.connect(lambda value: self.valueChanged(value, self.portamentoTime_spin))
        self.portamentoTime_spin.customContextMenuRequested.connect(lambda pos: self.widget_menu(pos, self.portamentoTime_spin))
        self.portamentoTime_slider.customContextMenuRequested.connect(lambda pos: self.widget_menu(pos, self.portamentoTime_spin))
        self.ctrl_dict.append('portamentoTime', self.portamentoTime_spin, 'Portamento time', 4, 5, None, None, self.portamento_lbl)
        
        self.digitalFilter_combo.currentIndexChanged.connect(self.valueChanged)
        self.digitalFilter_combo.customContextMenuRequested.connect(self.widget_menu)
        self.ctrl_dict.append('digitalFilter', self.digitalFilter_combo, 'Digital filter type', 24, 28, (0, 64, 96), None, self.digitalFilter_lbl)

        mod_dict = {'modAdsrRelease': ('ADSR release', 64), 'modAnalogFilterCutoff': ('Analog filter cutoff', 8),
                    'modDigitalFilterCutoff': ('Digital filter cutoff', 4), 'modPreFilterVolume': ('Pre filter volume', 32), 
                    'modResonance': ('Resonance', 16), 'modPwm1': ('PWM 1', 1), 'modPwm2': ('PWM 2', 2)}
        self.mod_values = {}
        for k, (label, value) in mod_dict.items():
            widget = getattr(self, '{}_chk'.format(k))
            widget.toggled.connect(self.mod_data_change)
            widget.customContextMenuRequested.connect(self.widget_menu)
            self.mod_values[widget] = 0
            self.ctrl_dict.append(k, widget, label, 25, 31, (0, value), self.mod_data_send, widget)

        chk_dict = {'pwmModulation': ('PWM modulation', 9, 85), 'pitchModulation': ('Pitch modulation', 10, 86),
                    'filterModulation': ('Filter modulation', 11, 87), 'ampModulation': ('Amp modulation', 12, 88), 
                    'adsrFilter': ('ADSR filter link', 6, 29), 'keyOffAttack': ('Key off attack', 7, 30), 'waveDcOffset': ('Wave DC offset', 8, 83)
                    }
        for k, (label, index, ctrl) in chk_dict.items():
            widget = getattr(self, '{}_chk'.format(k))
            widget.toggled.connect(self.valueChanged)
            widget.customContextMenuRequested.connect(self.widget_menu)
            self.ctrl_dict.append(k, widget, label, index, ctrl, (0, 64), None, widget)

        dial_list = self.findChildren(QtGui.QDial, QtCore.QRegExp('.*_dial'))
        dial_dict = {'preFilterVolume': ('Pre Filter volume', 13, 20), 'filterDcOffset': ('Filter DC offset', 14, 22), 'pwm1': ('PWM 1', 15, 25), 
                     'adsrAttack': ('ADSR attack', 17, 17), 'adsrDecay': ('ADSR decay', 18, 19), 'pwm2': ('PWM 2', 16, 23), 
                     'adsrSustain': ('ADSR sustain', 19, 21), 'adsrRelease': ('ADSR release', 20, 16), 'outVolume': ('Out volume', 5, 7), 
                     'digitalCutoff': ('Digital cutoff', 21, 18), 'resonance': ('Resonance', 22, 15), 'analogCutoff': ('Analog cutoff', 23, 14)
                     }
        for dial in dial_list:
            dial_name = str(dial.objectName()).split('_')[0]
            label, dial_id, dial_ctrl = dial_dict.get(dial_name, ('None', 0, 0))
            spin = getattr(self, dial_name+'_spin')
            spin.valueChanged.connect(lambda value, sibling=dial: self.sibling_change(value, sibling))
            dial.valueChanged.connect(lambda value, sibling=spin: self.sibling_change(value, sibling))
            spin.valueChanged.connect(self.valueChanged)
            dial.valueChanged.connect(lambda value, spin=spin: self.valueChanged(value, spin))
            self.ctrl_dict.append(dial_name, spin, label, dial_id, dial_ctrl, None, None, getattr(self, dial_name+'_lbl'))
            dial.focusInEvent = self.tab_rewrite
            spin.customContextMenuRequested.connect(lambda pos, widget=spin: self.widget_menu(pos, widget))
            dial.customContextMenuRequested.connect(lambda pos, widget=spin: self.widget_menu(pos, widget))


    def tab_rewrite(self, event):
        widget = QtGui.QApplication.instance().focusWidget()
        widget.nextInFocusChain().setFocus()

    def keyboard_enable(self, value):
        self.keyboard = value
        self.piano.show_keys(value)
        if not value:
            self.panic()

    def panic(self):
        self.PANIC.emit(self.output, self.channel)
        self.piano.all_notes_off()

    def create_controller3_models(self):
        self.controller3_firstMode = QtGui.QStandardItemModel()
        self.controller3_secondMode = QtGui.QStandardItemModel()
        modelist = [['Waveform {}'.format(i) for i in range(1, 5)], ['bassdrum mode', 'undevizesime', 'quartvizesime', 'clubvizesime']]
        for i in range(4):
            item = QtGui.QStandardItem(modelist[0][i])
            self.controller3_firstMode.appendRow(item)
            item = QtGui.QStandardItem(modelist[1][i])
            self.controller3_secondMode.appendRow(item)
        self.waveform_combo.setMinimumContentsLength(max([len(i) for i in modelist[0]+modelist[1]]))

    def sibling_change(self, value, sibling):
        sibling.blockSignals(True)
        sibling.setValue(value)
        sibling.blockSignals(False)

    def controller3_change(self, value):
        prevIndex = self.waveform_combo.currentIndex()
        if prevIndex < 0:
            prevIndex = 0
        self.waveform_combo.blockSignals(True)
        if value in [0, 2]:
            self.waveform_combo.setModel(self.controller3_firstMode)
        else:
            self.waveform_combo.setModel(self.controller3_secondMode)
        self.waveform_combo.setCurrentIndex(prevIndex)
        self.waveform_combo.blockSignals(False)
        if self.local:
            self.waveform_combo.currentIndexChanged.emit(prevIndex)

    def waveform_change(self, value):
        if value == 0 and self.controller3Mode_combo.currentIndex() in [1, 3]:
            self.portamento_chk.setEnabled(False)
            self.portamento_lbl.setText('BD Rel. Time:')
            self.pwm1_lbl.setText('BD Timbre:')
            self.pwm2_lbl.setText('BD Attack:')
            self.waveDcOffset_chk.setText('BD Rel. sound')
        else:
            self.portamento_chk.setEnabled(True)
            self.portamento_lbl.setText('Time:')
            self.pwm1_lbl.setText('PWM 1::')
            self.pwm2_lbl.setText('PWM 2:')
            self.waveDcOffset_chk.setText('Wave DC Offset:')

    def priority_after_change(self, value):
        widget = self.sender()
        data = self.ctrl_dict.get_widget(widget)
        self.priority_after_values[widget] = data.ext[value]
        self.valueChanged(value)

    def mod_data_change(self, value):
        widget = self.sender()
        data = self.ctrl_dict.get_widget(widget)
        self.mod_values[widget] = data.ext[value]
        self.valueChanged(value)

    def valueChanged(self, value, widget=None):
        if self.local:
            return
        if not widget:
            widget = self.sender()
        data = self.ctrl_dict.get_widget(widget)
        if not data.func:
            if not data.ext:
                self.CTRL.emit(self.output, self.channel, data.ctrl, value)
            else:
                value = data.ext[value]
                self.CTRL.emit(self.output, self.channel, data.ctrl, value)
        else:
            value = data.func(data.ctrl, data.ext, value)
        program = self.program_combo.currentIndex()
        if program < 32:
            return
        prog_data = self.program_model.item(program).prog_data
        ctrl_data = self.ctrl_dict.get_widget(widget)
        ctrl_id = ctrl_data.id
        if not prog_data:
            prog_data = [-1 for i in range(27)]
            self.program_model.item(program).prog_data = prog_data
        if isinstance(widget, QtGui.QSpinBox):
            widget.setMinimum(0)
            widget.setSpecialValueText('')
        prog_data[ctrl_id] = value
        label = ctrl_data.label if ctrl_data.label else widget
        if ctrl_id in bit_values:
            [setItalic(c.label if c.label else c.widget, False) for c in self.ctrl_dict.get_id(ctrl_id)]
        else:
            setItalic(label, False)
        if not all(False for x in prog_data if x < 0):
            return
        self.actionProgramSave.setEnabled(True)
        self.actionMenuProgramSave.setEnabled(True)
        setBold(self.program_model.item(self.program_combo.currentIndex()))

    def oscMode_send(self, ctrl, ext, value):
        for c in ctrl[value]:
            self.CTRL.emit(self.output, self.channel, c, 0)
        self.CTRL.emit(self.output, self.channel, ext[value], 64)
        return value

    def priority_after_send(self, ctrl, ext, value):
        value = sum(self.priority_after_values.values())
        self.CTRL.emit(self.output, self.channel, ctrl, value)
        return value

    def mod_data_send(self, ctrl, ext, value):
        value = sum(self.mod_values.values())
        self.CTRL.emit(self.output, self.channel, ctrl, value)
        return value

    def noteon_send(self, id):
        self.NOTEON.emit(self.output, self.channel, id, self.velocity)

    def noteoff_send(self, id):
        self.NOTEOFF.emit(self.output, self.channel, id, self.velocity)

    def velocity_change(self, value):
        self.velocity = value

    def mod_value_change(self, value):
        self.mod_wheel = value

    def mod_send(self, value):
        self.CTRL.emit(self.output, self.channel, 1, value)

    def pitch_send(self, value):
        value = value*128
        if value > 8191: value = 8191
        self.PITCHBEND.emit(self.output, self.channel, value)
        self.pitchbend = True if (value != 0 and not self.pitch_chk.isChecked()) else False

    def pitch_set(self, value):
        self.pitchbend = value
        if not value:
            self.pitch_slider.setValue(0)

    def pitch_out(self, event):
        if self.pitchbend and not self.pitch_chk.isChecked():
            self.pitch_slider.setValue(0)

    def pitch_rel(self, event):
        if self.pitchbend and not self.pitch_chk.isChecked():
            self.pitch_slider.setValue(0)
        return QtGui.QSlider.mouseReleaseEvent(self.pitch_slider, event)

    def widget_get_mapping(self, widget):
        mapping = {}
        for event, event_dict in self.map_dict.items():
            for target_value, event_list in event_dict.items():
                for target, value in event_list:
                    if widget == target:
                        mapping[value] = (event, target_value)
        return mapping

    def widget_check_mapping(self, widget):
        for event, event_dict in self.map_dict.items():
            for target_value, event_list in event_dict.items():
                for target, value in event_list:
                    if widget == target:
                        return True
        return False

    def widget_clear_mapping(self, widget):
        for event, event_dict in self.map_dict.items():
            for target_value, event_list in event_dict.items():
                clear_list = []
                for i, (target, value) in enumerate(event_list):
                    if widget == target:
                        clear_list.append(i)
                clear_list.reverse()
                for i in clear_list:
                    event_list.pop(i)
                if not len(event_list):
                    event_dict.pop(target_value)
            if not len(event_dict):
                self.map_dict.pop(event)

    def widget_menu(self, pos, target=None):
        widget = self.sender()
        if not target:
            target = widget
        menu = QtGui.QMenu()
        map_action = QtGui.QAction('Set MIDI map', self)
        clear_action = QtGui.QAction('Clear MIDI map', self)
        exists = self.widget_check_mapping(target)
        if not exists:
            clear_action.setEnabled(False)
        menu.addActions([map_action, clear_action])
        action = menu.exec_(widget.mapToGlobal(pos))
        if action == clear_action:
            self.widget_clear_mapping(target)
        elif action == map_action:
            ctrl_data = self.ctrl_dict.get_widget(target)
            name = ctrl_data.name if ctrl_data is not None else target.label_text
            if isinstance(target, QtGui.QSpinBox):
                self.map_dialog = SimpleMap(self, name)
                res = self.map_dialog.exec_(self.widget_get_mapping(target))
                if not res:
                    return
                self.widget_clear_mapping(target)
                event = res
                event_dict = self.map_dict.get(event)
                if not event_dict:
                    event_dict = {}
                    self.map_dict[event] = event_dict
                event_list  = event_dict.get(AllValues)
                if not event_list:
                    event_list = []
                    event_dict[AllValues] = event_list
                event_list.append((target, 0))
            elif isinstance(target, QtGui.QComboBox):
                model = target.model()
                itemlist = [model.item(i).text() for i in range(model.rowCount())]
                self.map_dialog = ComboMap(self, name, itemlist)
                res = self.map_dialog.exec_(self.widget_get_mapping(target))
                if not res:
                    return
                self.widget_clear_mapping(target)
                if len(res) == 1:
                    chan, event_type, event_id, values = res[0]
                    event = (chan, event_type, event_id)
                    event_dict = self.map_dict.get(event)
                    if not event_dict:
                        event_dict = {}
                        self.map_dict[event] = event_dict
                    for i, e in enumerate(values):
                        event_list = event_dict.get(e)
                        if not event_list:
                            event_list = []
                            event_dict[e] = event_list
                        event_list.append((target, i))
                else:
                    for i, event_data in enumerate(res):
                        chan, event_type, event_id, event_value = event_data
                        event = (chan, event_type, event_id)
                        event_dict = self.map_dict.get(event)
                        if not event_dict:
                            event_dict = {}
                            self.map_dict[event] = event_dict
                        event_list = event_dict.get(event_value)
                        if not event_list:
                            event_list = []
                            event_dict[event_value] = event_list
                        event_list.append((target, i))
            else:
                self.map_dialog = CheckboxMap(self, name)
                res = self.map_dialog.exec_(self.widget_get_mapping(target))
                if not res:
                    return
                self.widget_clear_mapping(target)
                if len(res) == 1:
                    chan, event_type, event_id, event_value = res[0]
                    event = (chan, event_type, event_id)
                    event_dict = self.map_dict.get(event)
                    if not event_dict:
                        event_dict = {}
                        self.map_dict[event] = event_dict
                    event_list  = event_dict.get(event_value)
                    if not event_list:
                        event_list = []
                        event_dict[event_value] = event_list
                    event_list.append((target, True))
                    return
                for i, event_data in enumerate(res):
                    chan, event_type, event_id, event_value = event_data
                    event = (chan, event_type, event_id)
                    event_dict = self.map_dict.get(event)
                    if not event_dict:
                        event_dict = {}
                        self.map_dict[event] = event_dict
                    event_list = event_dict.get(event_value)
                    if not event_list:
                        event_list = []
                        event_dict[event_value] = event_list
                    event_list.append((target, i))

    def midi_event(self, event):
        if event.port == 0:
            if not self._input1_channel == -1 and self._input1_channel != event.channel:
                print 'son qui'
                return
        elif event.port == 1:
            if not self._input2_channel == -1 and self._input2_channel != event.channel:
                return
        if self.map_dialog and self.map_dialog.isVisible():
            self.MidiEvent.emit(event)
            return
        event_dict = self.map_dict.get((event.channel, event.type, event.data1))
        if not event_dict:
            if event.type == NOTEON and event.velocity == 0:
                event.type = NOTEOFF
            if event.type == NOTEON and 36 <= event.note <= 96:
                self.piano.keys[event.note-36].mousePressEvent(None, event.velocity)
                return
            if event.type == NOTEOFF and 36 <= event.note <= 96:
                self.piano.keys[event.note-36].mouseReleaseEvent(None)
                return
            return
        if AllValues in event_dict:
            for widget, i in event_dict[AllValues]:
                widget.setValue(event.data2)
#                return
        event_list = event_dict.get(event.data2)
        if not event_list:
            return
        for widget, value in event_list:
            if isinstance(widget, QtGui.QComboBox):
                widget.setCurrentIndex(value)
            else:
                if isinstance(value, bool):
                    widget.setChecked(not widget.isChecked())
                else:
                    widget.setChecked(value)

    def about(self):
        title = self.windowTitle()
        title.insert(0, 'About ')
        text = '''<b>Ploytec &pi;&lambda;&sup2; Editor v. {version}</b><br>
                  Created by <a href="{web}">Maurizio Berti</a><br><br>
                  Based on the original editor from <a href="http://www.ploytec.com/">Ploytec GmbH</a><br>
                  Uses code portions of <a href="http://das.nasophon.de/mididings/">mididings</a>.<br><br>
                  Source code available on <a href="{code}">GitHub</a>
                  '''.format(version=__version__, web=__website__, code=__codeurl__)
        QtGui.QMessageBox.about(self, title, text)

    def settings_save(self):
        def get_connections(port, dir):
            ports = [getattr(conn, dir) for conn in port.connections if not conn.hidden]
            return [((p.client.name, p.name), (p.client.id, p.id)) for p in ports]
        self.settings.gMIDI.set_Input1(get_connections(self.midiseq.input[0], 'src'))
        self.settings.gMIDI.set_Input2(get_connections(self.midiseq.input[1], 'src'))
        self.settings.gMIDI.set_Output1(get_connections(self.midiseq.output[0], 'dest'))
        self.settings.gMIDI.set_Output2(get_connections(self.midiseq.output[1], 'dest'))
        self.settings.gMIDI.set_Input1_channel(self._input1_channel)
        self.settings.gMIDI.set_Input2_channel(self._input2_channel)
        self.settings.gMIDI.set_Output1_channel(self._channel1)
        self.settings.gMIDI.set_Output2_channel(self._channel2)
        self.settings.sync()

    def closeEvent(self, event):
        self.settings_save()
        self.midiseq.keep_going = False
        self.midiseq_thread.terminate()
        self.midiseq_thread.wait()
        try:
            del self.midiseq.seq
        except:
            pass
        self.midiseq.deleteLater()
        self.midiseq_thread.deleteLater()
        QtGui.QMainWindow.closeEvent(self, event)

def Handler(level, msg):
    #ignore warning for "non standard" widgets as QDial
    #original message: 'QGradient::setColorAt: Color position must be specified in the range 0 to 1'
    if 'QGradient::setColorAt:' in msg:
        return
    else:
        print msg

def main():
    app = QtGui.QApplication(sys.argv)
    QtCore.qInstallMsgHandler(Handler)
    editor = Editor()
    editor.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()

