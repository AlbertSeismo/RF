"""
rf Documentation
================

The receiver function method is a popular technique to investigate crustal and
upper mantle velocity discontinuities. Basic concept of the method is that a
small part of incident P-waves from a teleseismic event gets converted to
S-waves at significant discontinuities under the receiver
(for P-receiver functions).
These converted Ps phases arrive at the station after the main P phase.
The response function of the receiver side (receiver function) is constructed
by removing the source and deep mantle propagation effects.
Firstly, the S-wave field is separated from the P-wave field by a rotation
from the station coordinate system (ZNE - vertical, north, east)
to the wave coordinate system (LQT - P-wave polarization,
approx. SV-wave polarization, SH-wave polarization).
Secondly, the waveform on the L component is deconvolved from the other
components, which removes source side and propagation effects.
The resulting functions are the Q and T component of the P receiver function.
Multiple reflected waves are also visible in the receiver function.
The conversion points of the rays are called piercing points.

For a more detailed description of the working flow see e.g. chapter 4.1 of
this_ dissertation.

.. image:: _static/2layer_rays.svg
   :height: 250px
   :alt: Ray paths

.. image:: _static/2layer_synrf.svg
   :height: 250px
   :alt: Synthetic receiver function

| *Left*: In a two-layer-model part of the incoming P-wave is converted to a
    S-wave at the layer boundary. Major multiples are Pppp, Ppps and Ppss.
| *Right*: Synthetic receiver function of Q component in a two-layer-model.

Installation
------------

Dependencies of rf are

    * ObsPy_ and its dependencies,
    * toeplitz_ for time domain deconvolution,
    * geographiclib_ for ppoint calculation,
    * obspyh5_ for hdf5 file support (optional).

After the installation of Obspy rf can be installed with ::

    pip install rf

The tests can be run with the script ::

    rf-runtests

To install the development version of obspy download the source code and run ::

    python setup.py install

Using the underlying Python module
-----------------------------------

The main functionality is provided by the class :class:`~rf.rfstream.RFStream`
which is derived from ObsPy's :class:`~obspy.core.stream.Stream` class.

The canonical way to load a waveform file into a RFStream is to use
the :func:`~rf.rfstream.read_rf` function.

>>> from rf import read_rf
>>> stream = read_rf('myfile.SAC')

If you already have an ObsPy Stream and you want to turn it into a RFStream
use the generator of RFStream:

>>> from rf import RFStream
>>> stream = RFStream(obspy_stream)

The stream is again written to disc as usual by its write method:

>>> stream.write('outfile', 'SAC')

The RFStream object inherits a lot of useful methods from its ObsPy ancestor
(e.g. filter, taper, simulate, ...).

The module automatically maps important (for rf calculation) header information
from the stats object attached to every trace to the format specific headers.
At the moment only SAC and SH/Q headers are supported. When initializing an
RFStream the header information in the format specific headers are written to
the stats object and before writing the information stored in the stats object
is written back to the format specific headers. In this way the important
header information is guaranteed to be saved in the waveform files.
The following table reflects the mapping:

=================  =========  =====
stats              SH/Q       SAC
=================  =========  =====
station_latitude   COMMENT    stla
station_longitude  COMMENT    stlo
station_elevation  COMMENT    stel
event_latitude     LAT        evla
event_longitude    LON        evlo
event_depth        DEPTH      evdp
event_magnitude    MAGNITUDE  mag
event_time         ORIGIN     o
onset              P-ONSET    a
distance           DISTANCE   gcarc
back_azimuth       AZIMUTH    baz
inclination        INCI       user0
slowness           SLOWNESS   user1
pp_latitude        COMMENT    user2
pp_longitude       COMMENT    user3
pp_depth           COMMENT    user4
=================  =========  =====

.. note::
    Q-file header COMMENT is used for storing some information, because
    the Q format has a shortage of predefined headers.

.. note::
    Alternatively the hdf5 file format can be used. It is supported via the
    obspyh5 package. In this case all supported stats
    entries are automatically attached to the stored data.

The first task when calculating receiver functions is calculating some ray
specific values like azimuth and epicentral distance. An appropriate stats
dictionary can be calculated with :func:`~rf.rfstream.rfstats`:

>>> from rf import rfstats
>>> stats = rfstats(station=station, event=event, phase='P', dist_range=(30,90))
>>> for tr in stream:
>>>     tr.stats.update(stats)

or if the station and event information is already stored in the stats object:

>>> for tr in stream:
>>>     rfstats(stats=tr.stats)

Now P receiver functions can be calculated by

>>> stream.filter('bandpass', freqmin=0.05, freqmax=1.)
>>> stream.rf()
>>> stream.write('rf', 'Q')

rf can also calculate S receiver functions (not much tested):

>>> stream.rf(method='S')

When calling stream.rf the following operations are performed depending on
the given kwargs:

    * filtering
    * trimming data to window relative to onset
    * downsampling
    * rotation
    * deconvolution

Please see :meth:`RFStream.rf() <rf.rfstream.RFStream.rf>`
for a more detailed description.
RFStream provides the possibility to perform moveout correction
and piercing point calculation.

Command line tool for batch processing
--------------------------------------

The rf package provides a command line utility 'rf' which runs all the
necessary steps to perform receiver function calculation.
All you need is an inventory file (StationXML) and a file with events
(QuakeML) you want to analyze.

The command ::

    rf create

creates a :ref:`template configuration file <config>` in the current
directory. This file is in JSON format and well documented.
After adapting the file to your needs you can use the various
subcommands of rf to perform different tasks (e.g. receiver function
calculation, plotting).

To create the tutorial with a small included dataset and working configuration
you can use ::

    rf create --tutorial

Now start using rf ..., e.g. ::

    rf calc
    rf moveout
    rf plot Prf_Ps
    rf --moveout Psss moveout
    rf plot Prf_Psss

Miscellaneous
-------------

Please feel free to request features, report bugs or contribute code on
GitHub_. The code is continiously tested by travis-ci. The test status of this
version is |buildstatus|.


.. _this: http://www.diss.fu-berlin.de/diss/servlets/MCRFileNodeServlet/FUDISS_derivate_000000014929/dissertation_richter.pdf
.. _ObsPy: http://www.obspy.org/
.. _pip: http://www.pip-installer.org/
.. _obspyh5: https://github.com/trichter/obspyh5/
.. _toeplitz: https://github.com/trichter/toeplitz/
.. _geographiclib: https://pypi.python.org/pypi/geographiclib/
.. _GitHub: https://github.com/trichter/rf/
.. |buildstatus| image:: https://api.travis-ci.org/trichter/rf.png?
    branch=master
   :target: https://travis-ci.org/trichter/rf
"""
# Suggest people to cite rf.

from _version import __version__
from rfstream import read_rf, RFStream, rfstats

if 'dev' not in __version__:  # get image for correct version from travis-ci
    _travis_version = 'v' + __version__
    __doc__ = __doc__.replace('branch=master', 'branch=v%s' % __version__)
