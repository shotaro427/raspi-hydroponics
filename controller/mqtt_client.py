"""MQTT クライアントモジュール（paho-mqtt使用）"""

import json
import logging
import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)


class MqttClient:
    def __init__(self, broker, port, topic_prefix):
        self.topic_prefix = topic_prefix
        self.client = mqtt.Client(client_id="hydro-controller")
        self.client.on_connect = self._on_connect
        self.client.connect(broker, port, keepalive=60)
        self.client.loop_start()

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.info("MQTTブローカーに接続")
        else:
            logger.error(f"MQTT接続失敗: rc={rc}")

    def publish(self, subtopic, value):
        """トピックにJSON形式でpublish"""
        topic = f"{self.topic_prefix}/{subtopic}"
        payload = json.dumps({"value": value})
        self.client.publish(topic, payload)
        logger.debug(f"MQTT publish: {topic} = {payload}")

    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()