PL2Edit
=======

PL2Edit is a GNU/Linux editor for the `Ploytec
πλ² <http://www.ploytec.com/pl2/>`__ (PL2) synthesizer.

.. figure:: https://raw.githubusercontent.com/MaurizioB/PL2Edit/master/data/art/screenshot-main-small.jpg
   :alt: PL2Edit screenshot

   PL2Edit screenshot
It is based on the Windows official software from Ploytec, offers a very
similar interface, while adding some features.

Since there is no editor for Linux and it doesn't look to work with
WINE, I decided to write my own.

The PL2 is completely controlled via MIDI, so, every aspect of it can be
easily edited using MIDI Control messages.

Features
--------

-  Control every parameter of the synthesizer
-  Create custom templates with user programs and controller mappings,
   with user program names
-  Create custom MIDI mappings from external controllers, expecially
   useful if you can't/don't want to change controller parameters or you
   need a common automation interface in your DAW.
-  Load/save PL2 programs (exported/imported with the official software)

Requirements
------------

-  Python 2.7
-  PyQt4 at least version 4.11.1
-  pyalsa

Installation
------------

**WARNING**: this is still experimental. While it shouldn't break
anything, there's no guarantee that it will work properly.

Run this command within the package directory:

::

    python setup.py install

If you want to install PL2Edit locally (without *root* permissions), use
this:

::

    python setup.py install --user

To keep track of installed files, use this command:

::

    python setup.py install --record files.txt

Then you will be able to uninstall it by launching

::

    cat files.txt | xargs rm -rf

Usage
-----

If you installed PL2Edit as descripted above, just launch ``pl2edit``,
otherwise run this command from the main program directory:

::

    ./pl2edit

Midi connections
~~~~~~~~~~~~~~~~

Select "MIDI setup" from the menu "Settings", double click a MIDI port
to connect/disconnect it to PL2Edit. There are 2 inputs, right now
doesn't matter which one you connect to. The 2 output ports are useful
if you have 2 PL2 devices, so you can select to which port MIDI messages
are sent using the "Output port" combo box in the upper right of the
main window.

Mapping
~~~~~~~

Right click on a controller and select "Set MIDI map", then manually
input the selected input data, or just move the controllers on your
controller MIDI device. Some controllers have multiple choices, use the
small bolt button to apply the detection to that single action.

Known issues
------------

Even if PL2Edit right now offers almost any base function the official
editor does, some things are missing. Also, keep in mind that there are
still some bugs, and I cannot guarantee anything. You're using this
software at your own risk.

These are the most important bugs/issues/missing features. - Firmware
uploading is not available. I'm discussing this with the people at
Ploytec and might be possible in the future. - The MIDI clock function
doesn't work yet (that's why it's disabled). - There is no support for
JACK (yet). In the meantime you can use
`a2jmidi <http://home.gna.org/a2jmidid/>`__. - If you use an external
keyboard connected to PL2Edit, the note range is limited to the 5
central octaves shown. - If you use NoteOn/Off as triggers for
controllers, those notes won't be sent to the output. This might change
in the future. - MIDI support could still have some bugs (I created a
custom interface to pyALSA).

Aknowledgments
--------------

Some small portions of code come from (or are "based" on)
`mididings <http://das.nasophon.de/mididings/>`__, a powerful MIDI
router and processor. At first PL2Edit used it, but I realized that
there was no need for that and then I switched to pure ALSA-python.
Still, some concepts behind it were useful and I used them.
