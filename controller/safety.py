"""緊急停止ロジック（手動リセット必要）"""

import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class SafetyManager:
    """緊急停止の監視と制御

    緊急停止時のアクション:
      1. 循環ポンプ停止
      2. アラート発報（MQTT hydroponics/alerts/emergency_stop）
      3. ログ記録（タイムスタンプ + 理由）
      4. 手動リセットまで自動復帰しない
    """

    def __init__(self, pump, mqtt_client, config: dict):
        """
        Args:
            pump: CirculationPumpインスタンス
            mqtt_client: MqttClientインスタンス
            config: config.yaml の safety セクション
        """
        self.pump = pump
        self.mqtt_client = mqtt_client
        self.config = config["emergency_stop"]

        self._is_stopped = False
        self._stop_reason = None
        self._stop_timestamp = None

        # 閾値
        self.water_temp_max = self.config["water_temp_max"]
        self.manual_reset_required = self.config["manual_reset_required"]

        logger.info(f"安全管理初期化: 水温上限={self.water_temp_max}°C")

    def check(self, water_level: str, water_temp: float) -> None:
        """メインループから呼ばれる。条件を確認し必要に応じて緊急停止する。

        Args:
            water_level: "normal" or "low"
            water_temp: 水温（°C）
        """
        if self._is_stopped:
            return  # 既に緊急停止中

        # 水温異常チェック
        if water_temp > self.water_temp_max:
            self.emergency_stop(f"水温異常: {water_temp:.1f}°C (上限: {self.water_temp_max}°C)")

    def emergency_stop(self, reason: str) -> None:
        """緊急停止を実行する。

        Args:
            reason: 停止理由（ログ・MQTT通知に含める）
        """
        if self._is_stopped:
            return

        self._is_stopped = True
        self._stop_reason = reason
        self._stop_timestamp = datetime.now()

        # ポンプ強制停止
        self.pump.off()

        logger.critical(f"🚨 緊急停止: {reason}")

        # MQTTアラート送信
        alert_payload = {
            "type": "emergency_stop",
            "reason": reason,
            "timestamp": self._stop_timestamp.isoformat(),
            "manual_reset_required": self.manual_reset_required
        }
        self.mqtt_client.publish("alerts/emergency_stop", alert_payload)

    def reset(self) -> bool:
        """手動リセット。MQTTコマンドから呼ばれる。

        Returns:
            True: リセット成功, False: リセット条件を満たさない
        """
        if not self._is_stopped:
            logger.warning("緊急停止中ではありません（リセット不要）")
            return False

        self._is_stopped = False
        reset_timestamp = datetime.now()

        logger.info(f"✅ 緊急停止リセット（停止理由: {self._stop_reason}）")

        # MQTTリセット通知
        reset_payload = {
            "type": "emergency_stop_reset",
            "previous_reason": self._stop_reason,
            "stop_timestamp": self._stop_timestamp.isoformat(),
            "reset_timestamp": reset_timestamp.isoformat()
        }
        self.mqtt_client.publish("alerts/emergency_stop", reset_payload)

        # リセット情報をクリア
        self._stop_reason = None
        self._stop_timestamp = None

        return True

    @property
    def is_stopped(self) -> bool:
        """緊急停止中かどうか"""
        return self._is_stopped
