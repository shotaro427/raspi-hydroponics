"""水位連動ロジック（自動復帰可能）"""

import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class WaterLevelInterlock:
    """水位センサーと連動してスケジューラを制御する

    水位低下時:
      1. 循環ポンプを即座に停止
      2. スケジューラを一時停止
      3. アラート発報（MQTT）

    水位復帰時:
      1. スケジューラを再開
      2. ポンプ制御をスケジュールに戻す
      3. ログ記録
    """

    def __init__(self, water_sensor, scheduler, mqtt_client):
        """
        Args:
            water_sensor: WaterLevelSensorインスタンス
            scheduler: PumpSchedulerインスタンス
            mqtt_client: MqttClientインスタンス
        """
        self.water_sensor = water_sensor
        self.scheduler = scheduler
        self.mqtt_client = mqtt_client
        self._was_low = False

    def check(self) -> None:
        """メインループから定期的に呼ばれる。
        水位を確認し、必要に応じてスケジューラをpause/resumeする。
        """
        level = self.water_sensor.read()
        is_low = (level == 0)

        # 水位が低下した瞬間
        if is_low and not self._was_low:
            self._on_water_low()
            self._was_low = True

        # 水位が復帰した瞬間
        elif not is_low and self._was_low:
            self._on_water_normal()
            self._was_low = False

    def _on_water_low(self) -> None:
        """水位低下検知時の処理"""
        logger.warning("⚠️ 水位低下検知 → ポンプ停止＋スケジューラ一時停止")

        # スケジューラを一時停止（ポンプも自動でOFFになる）
        self.scheduler.pause()

        # MQTTアラート送信
        alert_payload = {
            "type": "water_level_low",
            "message": "水位低下：循環ポンプを自動停止しました",
            "timestamp": datetime.now().isoformat(),
            "auto_resume": True
        }
        self.mqtt_client.publish("alerts/interlock", alert_payload)

    def _on_water_normal(self) -> None:
        """水位復帰時の処理"""
        logger.info("✅ 水位復帰 → スケジューラ再開")

        # スケジューラ再開
        self.scheduler.resume()

        # MQTT通知
        resume_payload = {
            "type": "water_level_normal",
            "message": "水位復帰：循環ポンプ制御を再開しました",
            "timestamp": datetime.now().isoformat()
        }
        self.mqtt_client.publish("alerts/interlock", resume_payload)
