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
        self.client.on_message = self._on_message
        self._callbacks = {}  # {topic: callback}
        self.client.connect(broker, port, keepalive=60)
        self.client.loop_start()

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.info("MQTTブローカーに接続")
            # 再接続時にsubscribeを再設定
            for topic in self._callbacks.keys():
                full_topic = f"{self.topic_prefix}/{topic}"
                client.subscribe(full_topic)
                logger.debug(f"再subscribe: {full_topic}")
        else:
            logger.error(f"MQTT接続失敗: rc={rc}")

    def _on_message(self, client, userdata, msg):
        """メッセージ受信時のコールバック"""
        # topic_prefixを除いたsubtopicを取得
        full_topic = msg.topic
        if full_topic.startswith(f"{self.topic_prefix}/"):
            subtopic = full_topic[len(self.topic_prefix) + 1:]
        else:
            subtopic = full_topic

        # 登録されたコールバックを呼び出す
        if subtopic in self._callbacks:
            try:
                payload = json.loads(msg.payload.decode())
                self._callbacks[subtopic](subtopic, payload)
            except json.JSONDecodeError as e:
                logger.error(f"MQTT JSONデコードエラー: {e}")
            except Exception as e:
                logger.error(f"MQTTコールバック実行エラー: {e}")

    def publish(self, subtopic, value):
        """トピックにJSON形式でpublish"""
        topic = f"{self.topic_prefix}/{subtopic}"
        # valueが既にdictの場合はそのまま、それ以外は{"value": ...}で包む
        if isinstance(value, dict):
            payload = json.dumps(value)
        else:
            payload = json.dumps({"value": value})
        self.client.publish(topic, payload)
        logger.debug(f"MQTT publish: {topic} = {payload}")

    def subscribe(self, subtopic: str, callback) -> None:
        """トピックをsubscribeしコールバックを登録する。

        Args:
            subtopic: subscribeするMQTTトピック（topic_prefix以降）
            callback: メッセージ受信時に呼ばれるコールバック関数
                      callback(topic: str, payload: dict) の形式
        """
        full_topic = f"{self.topic_prefix}/{subtopic}"
        self._callbacks[subtopic] = callback
        self.client.subscribe(full_topic)
        logger.info(f"MQTT subscribe: {full_topic}")

    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()