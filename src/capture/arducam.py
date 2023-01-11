import numpy as np
import cv2
import logging
import time

import arducam as ac

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

ERROR_CODES = {
    0x0000: 'USB_CAMERA_NO_ERROR',
    0xFF01: 'USB_CAMERA_USB_CREATE_ERROR',
    0xFF02: 'USB_CAMERA_USB_SET_CONTEXT_ERROR',
    0xFF03: 'USB_CAMERA_VR_COMMAND_ERROR',
    0xFF04: 'USB_CAMERA_USB_VERSION_ERROR',
    0xFF05: 'USB_CAMERA_BUFFER_ERROR',
    0xFF0B: 'USB_CAMERA_I2C_BIT_ERROR',
    0xFF0C: 'USB_CAMERA_I2C_NACK_ERROR',
    0xFF0D: 'USB_CAMERA_I2C_TIMEOUT',
    0xFF20: 'USB_CAMERA_USB_TASK_ERROR',
    0xFF21: 'USB_CAMERA_DATA_OVERFLOW_ERROR',
    0xFF22: 'USB_CAMERA_DATA_LACK_ERROR',
    0xFF23: 'USB_CAMERA_FIFO_FULL_ERROR',
    0xFF24: 'USB_CAMERA_DATA_LEN_ERROR',
    0xFF25: 'USB_CAMERA_FRAME_INDEX_ERROR',
    0xFF26: 'USB_CAMERA_USB_TIMEOUT_ERROR',
    0xFF30: 'USB_CAMERA_READ_EMPTY_ERROR',
    0xFF31: 'USB_CAMERA_DEL_EMPTY_ERROR',
    0xFF51: 'USB_CAMERA_SIZE_EXCEED_ERROR',
    0xFF61: 'USB_USERDATA_ADDR_ERROR',
    0xFF62: 'USB_USERDATA_LEN_ERROR',
    0xFF71: 'USB_BOARD_FW_VERSION_NOT_SUPPORT_ERROR',
    0x10000: 'config file not found',
}

# Registers
# Refer to datasheet for this: https://datasheetspdf.com/pdf-file/1252892/OmniVision/OV7251/1
# note: registers are little-endian

# exposure is a 16 bit value with 4 bits for debug, distributed like so:
# |           |                  exposure time                |           |
# |   unused  |15|14|13|12|11|10|09|08|07|06|05|04|03|02|01|00|   debug   |
# |07|06|05|04|03|02|01|00|07|06|05|04|03|02|01|00|07|06|05|04|03|02|01|00|
# |         0x3500        |         0x3501        |         0x3502        |

# frame length (vertical timing size?) is a 16 bit value distributed like so
# |                 frame length                  |
# |15|14|13|12|11|10|09|08|07|06|05|04|03|02|01|00|
# |07|06|05|04|03|02|01|00|07|06|05|04|03|02|01|00|
# |         0x380e        |         0x380f        |

# hardware-level image manipulation is 16 bits of flags distributed like so:
# ??: unknown
# vf: vertical flip
# vb: vertical binning
# hm: horizontal mirror
# hb: horizontal binning
# db: debug
# |??|??|  debug |vf|vb|    debug     |??|hm|db|hb|
# |07|06|05|04|03|02|01|00|07|06|05|04|03|02|01|00|
# |         0x3820        |         0x3821        |

# Errors

"""
Error raised when an ArduCam-related class encouters a TypeError
"""
class ArduCamDataTypeError(TypeError):
    def __init__(self, ctx, expected, got):
        super.__init__(self, f"{ctx} expected type {expected}, but got {got} instead.")

"""
Error raised when the ArduCam interface library fails
"""
class ArduCamCriticalError(Exception):
    def __init__(self, msg):
        self.msg = msg

"""
Error raised when capturing a frame fails
"""
class ArduCamCaptureError(Exception):
    def __init__(self, msg):
        self.msg = msg

# Classes

"""
ArduCamManager:
Manages ArduCams and creates ArduCamSources for them
"""
class ArduCamManager:
    def __init__(self):
        self._devices = ac.get_devices()

    def get_devices(self):
        self._devices = ac.get_devices()
        return [(device.serial, device.usb_index) for device in self._devices]


"""
ArduCamSource:
Wrapper class for one (1) ArduCam unit
"""
class ArduCamSource:
    def __init__(
            self,
            cam_id,
            frame_size,
            frame_rate,
            cfg_file):

        self._cam_id = cam_id
        self._frame_size = frame_size
        self._frame_rate = frame_rate
        self._cfg_file = cfg_file

        self._active = False
        self._init_done = False

        try:
            self._init_cam()
        except ArduCamCriticalError as error: # init may fail, catch and handle it """gracefully"""
            logger.debug(error.msg)
        else:
            self._init_done = True

    @property
    def init_done(self): # check if init was a success
        return self._init_done

    @property
    def exposure_time(self):
        # see exposure time register description at the top of this file
        try:
            return int(
                hex(ac.read_reg(self._cam_id, 0x3500))[2:].rjust(2, '0')[1]
                + hex(ac.read_reg(self._cam_id, 0x3501))[2:].rjust(2, '0')
                + hex(ac.read_reg(self._cam_id, 0x3502))[2:].rjust(2, '0')[:1], 16
            )
        except KeyError:
            return -1

    @exposure_time.setter
    def exposure_time(self, new_exposure_time):
        try:
            assert 0 < new_exposure_time <= 0xffff
            h = hex(new_exposure_time)[2:].rjust(4, '0')
            nums = (h[0], h[1:3], h[3])

            w = hex(ac.read_reg(self._cam_id, 0x3500))[2:].rjust(2, '0')[0] + h[0]
            ac.write_reg(self._cam_id, 0x3500, int(w, 16))

            w = h[1:3]
            ac.write_reg(self._cam_id, 0x3501, int(w, 16))

            w = h[3] + hex(ac.read_reg(self._cam_id, 0x3502))[2:].rjust(2, '0')[1]
            ac.write_reg(self._cam_id, 0x3502, int(w, 16))

        except KeyError:
            pass

    @property
    def frame_length(self):
        return (ac.read_reg(self._idx_backup, 0x380e) * 0x100) + ac.read_reg(self._idx_backup, 0x380f)

    def _init_cam(self):
        # check that the cam id is a valid number
        if not isinstance(self._cam_id, int):
            raise ArduCamDataTypeError(self, int, type(self._cam_id))

        # init the device via ac lib
        logger.debug(f"Attempting to open ArduCam with id {self._cam_id}")
        ret = 0x0000 # default value of "no error"
        try:
            ret = ac.initialize_device(self._cfg_file, self._cam_id)
        except RuntimeError as error:
            # something went wrong in the arducam interface library
            raise ArduCamCriticalError(f"Error opening ArduCam with id {self._cam_id}: {error}. This is an error within the ArduCam interface library. Abandon all hope ye who enter there.") from error

        if ret == 0x0000: # 0x0000: 'USB_CAMERA_NO_ERROR'
            # cam init success
            logger.debug(f"Success opening ArduCam with id {self._cam_id}")
        else:
            # arducam interface lib returned an error code
            raise ArduCamCriticalError(f"Error opening ArduCam with id {self._cam_id}: {ret}, {ERROR_CODES[ret]}")

        # start capture
        logger.debug(f"Attempting to begin capture on ArduCam with id {self._cam_id}")
        try:
            ret = ac.begin_capture(self._cam_id)
        except RuntimeError as error:
            # something went wrong in the arducam interface library
            raise ArduCamCriticalError(f"Error beginning capture on ArduCam with id {self._cam_id}: {error}. This is an error within the ArduCam interface library. Abandon all hope ye who enter there.") from error

        if ret == 0x0000:  # 0x0000: 'USB_CAMERA_NO_ERROR'
            # cam capture success
            logger.debug(f"Success beginning capture on ArduCam with id {self._cam_id}")
            self._active = True
        else:
            # arducam interface lib returned an error code
            raise ArduCamCriticalError(f"Error beginning capture ArduCam on with id {self._cam_id}: {ret}, {ERROR_CODES[ret]}")

    def close(self):
        logger.debug(f"Attempting shutdown of ArduCam with id {self._cam_id}")
        try:
            ac.end_capture(self._cam_id)
            ac.close_device(self._cam_id)
        except RuntimeError as error: # if there is an error, we don't care because the arudcam source is closed anyways
            logger.debug(f"Error while shutting down ArduCam with id {self._cam_id}")
        logger.debug(f"Shutdown of ArduCam with id {self._cam_id} complete")

    def re_init(self, new_id):
        self._active = False
        self._init_done = False
        self.close()

        self._cam_id = new_id
        try:
            self._init_cam()
        except ArduCamCriticalError as error:  # init may fail, catch and handle it """gracefully"""
            logger.debug(error.msg)
        else:
            self._init_done = True

    def capture_frame(self):
        if not self._active:
            return np.zeros(self._frame_size) # must return np.ndarray

        img = None
        try:
            img = ac.capture_img(self._cam_id)
        except RuntimeError as error:
            raise ArduCamCaptureError(f"Critical error while capturing frame on camera id {self._cam_id}")
        if img is None:
            logger.debug(f"Failed to capture frame on camera id {self._cam_id} (img = None)")
            return np.zeros(self._frame_size)
        return np.array(img), time.time()
