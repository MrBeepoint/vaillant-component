"""
Interfaces with Vaillant binary sensors.
"""
import logging
from abc import ABC

from vr900connector.model import Room, Circulation, Device, BoilerStatus

from homeassistant.components.binary_sensor import BinarySensorDevice, DOMAIN
from . import DOMAIN as VAILLANT, CONF_BINARY_SENSOR_BOILER_ERROR, CONF_BINARY_SENSOR_CIRCULATION, \
    CONF_BINARY_SENSOR_SYSTEM_ONLINE, CONF_BINARY_SENSOR_SYSTEM_UPDATE, CONF_BINARY_SENSOR_ROOM_WINDOW, \
    CONF_BINARY_SENSOR_ROOM_CHILD_LOCK, CONF_BINARY_SENSOR_DEVICE_BATTERY, CONF_BINARY_SENSOR_DEVICE_RADIO_REACH, \
    HUB, BaseVaillantEntity

_LOGGER = logging.getLogger(__name__)

DEVICE_CLASS_POWER = 'power'
DEVICE_CLASS_WINDOW = 'window'
DEVICE_CLASS_LOCK = 'lock'
DEVICE_CLASS_BATTERY = 'battery'
DEVICE_CLASS_CONNECTIVITY = 'connectivity'
DEVICE_CLASS_PROBLEM = 'problem'


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Vaillant binary sensor platform."""
    sensors = []
    HUB.update_system()

    if HUB.system:
        if HUB.system.circulation:  # and config[CONF_BINARY_SENSOR_CIRCULATION]:
            sensors.append(VaillantCirculationBinarySensor(HUB.system.circulation))

        if HUB.system.boiler_status:
            # if config[CONF_BINARY_SENSOR_BOILER_ERROR]:
            sensors.append(VaillantBoilerErrorBinarySensor(HUB.system.boiler_status))
            # if config[CONF_BINARY_SENSOR_SYSTEM_ONLINE]:
            sensors.append(VaillantBoxOnlineBinarySensor(HUB.system.boiler_status))
            # if config[CONF_BINARY_SENSOR_SYSTEM_UPDATE]:
            sensors.append(VaillantBoxUpdateBinarySensor(HUB.system.boiler_status))

        for room in HUB.system.rooms:
            # if config[CONF_BINARY_SENSOR_ROOM_WINDOW]:
            sensors.append(VaillantWindowBinarySensor(room))
            # if config[CONF_BINARY_SENSOR_ROOM_CHILD_LOCK]:
            sensors.append(VaillantChildLockBinarySensor(room))
            for device in room.devices:
                # if config[CONF_BINARY_SENSOR_DEVICE_BATTERY]:
                sensors.append(VaillantRoomDeviceBatteryBinarySensor(device, room))
                # if config[CONF_BINARY_SENSOR_DEVICE_RADIO_REACH]:
                sensors.append(VaillantRoomDeviceConnectivityBinarySensor(device, room))

    _LOGGER.info("Adding %s binary sensor entities", len(sensors))

    async_add_entities(sensors)


class VaillantCirculationBinarySensor(BaseVaillantEntity, BinarySensorDevice):

    def __init__(self, circulation: Circulation):
        super().__init__(DOMAIN, DEVICE_CLASS_POWER, circulation.name, circulation.name)
        self._circulation = circulation

    @property
    def is_on(self):
        from vr900connector.model import HeatingMode, QuickMode

        active_mode = self._circulation.active_mode
        return active_mode.current_mode == HeatingMode.ON \
            or active_mode.sub_mode == HeatingMode.ON \
            or active_mode == QuickMode.QM_HOTWATER_BOOST

    @property
    def available(self):
        return self._circulation is not None

    async def vaillant_update(self):
        new_circulation = HUB.find_component(self._circulation)

        if new_circulation:
            _LOGGER.debug("New / old state: %s / %s", new_circulation.active_mode.current_mode,
                          self._circulation.active_mode.current_mode)
        else:
            _LOGGER.debug("Circulation %s doesn't exist anymore", self._circulation.id)
        self._circulation = new_circulation


class VaillantWindowBinarySensor(BaseVaillantEntity, BinarySensorDevice):

    def __init__(self, room: Room):
        super().__init__(DOMAIN, DEVICE_CLASS_WINDOW, room.name, room.name)
        self._room = room

    @property
    def is_on(self):
        return self._room.window_open

    @property
    def available(self):
        return self._room is not None

    async def vaillant_update(self):
        new_room: Room = HUB.find_component(self._room)

        if new_room:
            _LOGGER.debug("New / old state: %s / %s", new_room.child_lock, self._room.child_lock)
        else:
            _LOGGER.debug("Room %s doesn't exist anymore", self._room.id)
        self._room = new_room


class VaillantChildLockBinarySensor(BaseVaillantEntity, BinarySensorDevice):

    def __init__(self, room: Room):
        super().__init__(DOMAIN, DEVICE_CLASS_LOCK, room.name, room.name)
        self._room = room

    @property
    def available(self):
        return self._room is not None

    async def vaillant_update(self):
        new_room: Room = HUB.find_component(self._room)

        if new_room:
            _LOGGER.debug("New / old state: %s / %s", new_room.child_lock, self._room.child_lock)
        else:
            _LOGGER.debug("Room %s doesn't exist anymore", self._room.id)
        self._room = new_room

    @property
    def is_on(self):
        """According to the doc, true means unlock, false lock"""
        return not self._room.child_lock


class VaillantRoomDeviceBinarySensor(BaseVaillantEntity, BinarySensorDevice, ABC):

    def __init__(self, device: Device, room: Room, device_class):
        super().__init__(DOMAIN, device_class, device.sgtin, device.name)
        self._room = room
        self._device = device
        self._device_class = device_class

    def _find_device(self, new_room: Room, sgtin: str):
        if new_room:
            for device in new_room.devices:
                if device.sgtin == sgtin:
                    return device

    @property
    def available(self):
        return self._device is not None

    async def vaillant_update(self):
        new_room: Room = HUB.find_component(self._room)
        new_device: Device = self._find_device(new_room, self._device.sgtin)

        if new_room:
            if new_device:
                _LOGGER.debug("New / old state: %s / %s", new_device.battery_low, self._device.battery_low)
            else:
                _LOGGER.debug("Device %s doesn't exist anymore", self._device.sgtin)
        else:
            _LOGGER.debug("Room %s doesn't exist anymore", self._room.id)
        self._room = new_room
        self._device = new_device


class VaillantRoomDeviceBatteryBinarySensor(VaillantRoomDeviceBinarySensor):

    def __init__(self, device: Device, room: Room):
        super().__init__(device, room, DEVICE_CLASS_BATTERY)

    @property
    def is_on(self):
        """According to the doc, true means normal, false low"""
        return self._device.battery_low


class VaillantRoomDeviceConnectivityBinarySensor(VaillantRoomDeviceBinarySensor):

    def __init__(self, device: Device, room: Room):
        super().__init__(device, room, DEVICE_CLASS_CONNECTIVITY)

    @property
    def is_on(self):
        """According to the doc, true means connected, false disconnected"""
        return not self._device.radio_out_of_reach


class BaseVaillantSystemBinarySensor(BaseVaillantEntity, BinarySensorDevice):

    def __init__(self, device_class, boiler_status: BoilerStatus):
        super().__init__(DOMAIN, device_class, boiler_status.device_name, boiler_status.device_name)
        self._boiler_status = boiler_status

    @property
    def available(self):
        return self._boiler_status is not None

    async def vaillant_update(self):
        boiler_status: BoilerStatus = HUB.system.boiler_status

        if boiler_status:
            _LOGGER.debug("Found new boiler status error? %s, online? %s, up to date? %s", boiler_status.is_error,
                          boiler_status.is_online, boiler_status.is_up_to_date)
        else:
            _LOGGER.debug("Boiler status doesn't exist anymore")
        self._boiler_status = boiler_status


class VaillantBoxUpdateBinarySensor(BaseVaillantSystemBinarySensor):

    def __init__(self, boiler_status: BoilerStatus):
        super().__init__(DEVICE_CLASS_POWER, boiler_status)

    @property
    def is_on(self):
        return not self._boiler_status.is_up_to_date


class VaillantBoxOnlineBinarySensor(BaseVaillantSystemBinarySensor):

    def __init__(self, boiler_status: BoilerStatus):
        super().__init__(DEVICE_CLASS_CONNECTIVITY, boiler_status)

    @property
    def is_on(self):
        return self._boiler_status.is_online


class VaillantBoilerErrorBinarySensor(BaseVaillantSystemBinarySensor):

    def __init__(self, boiler_status: BoilerStatus):
        super().__init__(DEVICE_CLASS_PROBLEM, boiler_status)

    @property
    def is_on(self):
        return self._boiler_status.is_error

    @property
    def state_attributes(self):
        return {
            'code': self._boiler_status.code,
            'title': self._boiler_status.title,
            'last_update': self._boiler_status.last_update
        }
