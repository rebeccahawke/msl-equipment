"""
A wrapper around the :class:`~.benhw32.Bentham32` class.
"""
import os
import inspect

from msl.loadlib import Client64

from msl.equipment.connection import Connection
from msl.equipment.exceptions import BenthamError
from .errors import BI_OK, ERROR_CODES
from .tokens import MonochromatorCurrentWL, BenMono


class Bentham(Connection, Client64):

    def __init__(self, record):
        """A wrapper around the :class:`~.benhw32.Bentham32` class.

        This class can be used with either a 32- or 64-bit Python interpreter
        to call the 32-bit functions in ``benhw32_cdecl.dll``.

        The :obj:`~msl.equipment.record_types.ConnectionRecord.properties`
        for a Bentham device supports the following key-value pairs in the
        :ref:`connection_database`::

            'model': 'C:\\path\\to\\System.cfg',  # default is '' 
            'setup': 'C:\\path\\to\\System.atr',  # default is ''
        
        If the ``model`` and ``setup`` values are not defined in the :ref:`connection_database`
        then you will have to call :meth:`build_system_model`, :meth:`load_setup`
        and :meth:`initialise` (in that order) to configure the SDK.

        Do not instantiate this class directly. Use the :meth:`~.EquipmentRecord.connect`
        method to connect to the equipment.

        Parameters
        ----------
        record : :class:`~.EquipmentRecord`
            A record from an :ref:`equipment_database`.
        """
        Connection.__init__(self, record)
        self.set_exception_handler(BenthamError)

        path = record.connection.address.split('::')[2]
        head, tail = os.path.split(path)
        self._tail = tail
        self.log_debug('Starting 32-bit server for {}'.format(tail))

        # the IEEE_32M.dll library must be available on PATH
        env_path = [head, os.path.join(head, 'IEEE', 'Dummy')]

        Client64.__init__(self, 'benhw32', append_sys_path=os.path.dirname(__file__),
                          append_environ_path=env_path, lib_path=path)

        self._hw_id = None

        cfg_path = record.connection.properties.get('model', '')
        atr_path = record.connection.properties.get('setup', '')
        if cfg_path and atr_path:
            self.build_system_model(cfg_path)
            self.load_setup(atr_path)
            self.initialise()

    def auto_measure(self):
        ret, reading = self.request32('auto_measure')
        self.errcheck(ret)
        return reading

    def build_system_model(self, path):
        """Set the model configuration file.

        Parameters
        ----------
        path : :obj:`str`
            The path to the ``System.cfg`` file.
        """
        if not os.path.isfile(path):
            raise IOError('Cannot find {}'.format(path))
        ret, error_report = self.request32('build_system_model', path)
        self.errcheck(ret, path, append_msg=error_report)
        return ret

    def disconnect(self):
        """Disconnect from the SDK and from the 32-bit server."""
        self.errcheck(self.request32('close'))
        self.log_debug('Stopping 32-bit server for {}'.format(self._tail))
        self.shutdown_server32()

    def errcheck(self, result, *args, **kwargs):
        """Checks whether a function call to the SDK was successful."""
        frame = inspect.getouterframes(inspect.currentframe())[1]
        self.log_debug('{}.{}{} -> {}'.format(self.__class__.__name__, frame.function, args, result))
        if result != BI_OK:
            e, m = ERROR_CODES[result]
            try:
                append_msg = kwargs['append_msg']
            except KeyError:
                append_msg = ''
            print('{0}: {1} {2}'.format(e, m, append_msg))
            self.raise_exception('{0}: {1} {2}'.format(e, m, append_msg))
        return result

    def get(self, hw_id, token, index):
        ret, value = self.request32('get', hw_id, token, index)
        self.errcheck(ret, hw_id, token, index)
        return value

    def get_component_list(self):
        ret, components = self.request32('get_component_list')
        self.errcheck(ret)
        return components

    def get_hardware_type(self, hw_id):
        ret, hardware_type = self.request32('get_hardware_type', hw_id)
        self.errcheck(ret, hw_id)
        return hardware_type

    def get_mono_items(self, hw_id):
        ret, items = self.request32('get_mono_items', hw_id)
        self.errcheck(ret, hw_id)
        return items

    @property
    def wavelength(self):
        if self._hw_id is None:
            for item in self.get_component_list():
                if self.get_hardware_type(item) == BenMono:
                    self._hw_id = item
                    break
            if self._hw_id is None:
                raise ValueError('Cannot get wavelength. BenMono is not a hardware type.')
        return self.get(self._hw_id, MonochromatorCurrentWL, 0)

    @wavelength.setter
    def wavelength(self, wavelength):
        self.select_wavelength(wavelength)

    def initialise(self):
        """Initialize the connection."""
        return self.errcheck(self.request32('initialise'))

    def load_setup(self, path):
        """Load the setup file.

        Parameters
        ----------
        path : :obj:`str`
            The path to the ``System.atr`` file.
        """
        if not os.path.isfile(path):
            raise IOError('Cannot find {}'.format(path))
        return self.errcheck(self.request32('load_setup', path), path)

    def park(self):
        return self.errcheck(self.request32('park'))

    def select_wavelength(self, wavelength):
        ret, recommended_delay_ms = self.request32('select_wavelength', wavelength)
        self.errcheck(ret, wavelength)
        return recommended_delay_ms

    def set(self, hw_id, token, index, value):
        ret = self.request32('set', hw_id, token, index, value)
        return self.errcheck(ret, hw_id, token, index, value)

    def version(self):
        """:obj:`str`: The version number of the SDK."""
        version = self.request32('get_version')
        self.log_debug('{}.version() -> {}'.format(self.__class__.__name__, version))
        return version

    def zero_calibration(self, start_wavelength, stop_wavelength):
        ret = self.request32('zero_calibration', start_wavelength, stop_wavelength)
        return self.errcheck(ret, start_wavelength, stop_wavelength)
