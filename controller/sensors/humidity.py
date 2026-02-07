"""気温・湿度センサー（DHT22）読取モジュール"""

import logging
import board
import adafruit_dht

logger = logging.getLogger(__name__)


class HumiditySensor:
    def __init__(self, gpio_pin: int):
        """
        Args:
            gpio_pin: DHTセンサー接続GPIOピン番号
        """
        # board.D17 のように指定する必要がある
        pin = getattr(board, f"D{gpio_pin}")
        self.dht = adafruit_dht.DHT22(pin)
        self.gpio_pin = gpio_pin
        logger.info(f"DHT22初期化: GPIO{gpio_pin}")

    def read(self) -> dict:
        """気温(°C)と湿度(%)を返す"""
        try:
            temperature = self.dht.temperature
            humidity = self.dht.humidity
            if temperature is None or humidity is None:
                raise RuntimeError("読み取り失敗")
            logger.debug(f"気温: {temperature:.1f}°C, 湿度: {humidity:.1f}%")
            return {
                "air_temp": round(temperature, 1),
                "humidity": round(humidity, 1)
            }
        except RuntimeError as e:
            # DHT22は読み取り失敗が頻繁に起きるので再試行が必要
            logger.warning(f"DHT22読み取りエラー: {e}")
            raise

    def cleanup(self):
        self.dht.exit()