"""循環ポンプ制御モジュール"""

import logging
import time

import RPi.GPIO as GPIO

logger = logging.getLogger(__name__)


class CirculationPump:
    """循環ポンプ制御クラス

    4chリレーモジュール経由でDC12V水中ポンプを制御する。
    一般的なリレーモジュールはACTIVE LOW（LOW信号でON）。
    """

    def __init__(self, gpio_pin: int, active_low: bool = True):
        """初期化。GPIOを設定しポンプOFF状態で開始する。

        Args:
            gpio_pin: リレー制御用GPIOピン番号（config.yamlから取得）
            active_low: True=LOW信号でリレーON（一般的な4chリレー）
        """
        self.pin = gpio_pin
        self.active_low = active_low
        self._is_on = False
        self._on_since: float | None = None
        self._total_runtime = 0.0

        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.pin, GPIO.OUT)
        # 初期状態: OFF（安全側）
        GPIO.output(self.pin, GPIO.HIGH if active_low else GPIO.LOW)
        logger.info(f"循環ポンプ初期化: GPIO{self.pin} (active_low={active_low})")

    def on(self) -> None:
        """ポンプをONにする"""
        if self._is_on:
            return
        GPIO.output(self.pin, GPIO.LOW if self.active_low else GPIO.HIGH)
        self._is_on = True
        self._on_since = time.time()
        logger.info("循環ポンプ: ON")

    def off(self) -> None:
        """ポンプをOFFにする"""
        if not self._is_on:
            return
        GPIO.output(self.pin, GPIO.HIGH if self.active_low else GPIO.LOW)
        self._is_on = False
        if self._on_since:
            self._total_runtime += time.time() - self._on_since
            self._on_since = None
        logger.info("循環ポンプ: OFF")

    def status(self) -> bool:
        """現在の状態を返す（True=ON, False=OFF）"""
        return self._is_on

    def runtime_hours(self) -> float:
        """累積稼働時間を時間単位で返す"""
        runtime = self._total_runtime
        if self._is_on and self._on_since:
            runtime += time.time() - self._on_since
        return runtime / 3600.0

    def cleanup(self) -> None:
        """GPIO解放。シャットダウン時に呼ぶ。"""
        self.off()
        GPIO.cleanup(self.pin)
        logger.info(f"循環ポンプ GPIO{self.pin} クリーンアップ完了")
