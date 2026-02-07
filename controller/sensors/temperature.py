"""DS18B20水温センサー読取モジュール"""

import glob
import logging

logger = logging.getLogger(__name__)

DEVICE_BASE_DIR = "/sys/bus/w1/devices/"
DEVICE_PATTERN = "28-*"


class TemperatureSensor:
    def __init__(self):
        self.device_path = self._find_device()
        logger.info(f"DS18B20検出: {self.device_path}")

    def _find_device(self):
        devices = glob.glob(DEVICE_BASE_DIR + DEVICE_PATTERN)
        if not devices:
            raise FileNotFoundError("DS18B20が見つかりません")
        return devices[0]

    def read(self):
        """水温を°Cで返す"""
        temp_file = self.device_path + "/temperature"
        with open(temp_file, "r") as f:
            raw = f.read().strip()
        temp_c = int(raw) / 1000.0
        logger.debug(f"水温: {temp_c:.1f}°C")
        return temp_c