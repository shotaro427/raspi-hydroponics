"""水位センサー（フロートスイッチ）読取モジュール"""

import logging
import RPi.GPIO as GPIO

logger = logging.getLogger(__name__)


class WaterLevelSensor:
    def __init__(self, gpio_pin: int):
        """
        Args:
            gpio_pin: フロートスイッチ接続GPIOピン番号
        """
        self.pin = gpio_pin
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        logger.info(f"水位センサー初期化: GPIO{self.pin}")

    def read(self) -> str:
        """水位状態を返す（"normal" or "low"）"""
        state = GPIO.input(self.pin)
        if state == GPIO.HIGH:
            status = 1
        else:
            status = 0
        logger.debug(f"水位: {"正常" if status == 1 else "低下"}")
        return status

    def is_low(self) -> bool:
        """水位が低下しているか"""
        return self.read() == "low"

    def cleanup(self):
        GPIO.cleanup(self.pin)