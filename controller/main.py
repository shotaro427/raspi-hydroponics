#!/usr/bin/env python3
"""水耕栽培制御デーモン - Phase 3"""

import logging
import signal
import time
import yaml

from sensors.temperature import TemperatureSensor
from sensors.water_level import WaterLevelSensor
from sensors.humidity import HumiditySensor
from actuators.pump import CirculationPump
from scheduler import PumpScheduler
from interlock import WaterLevelInterlock
from safety import SafetyManager
from mqtt_client import MqttClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s"
)
logger = logging.getLogger(__name__)

running = True


def signal_handler(sig, frame):
    global running
    logger.info("シャットダウンシグナル受信")
    running = False


def main():
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)

    mqtt_conf = config["mqtt"]
    sensor_conf = config["sensors"]
    actuator_conf = config["actuators"]

    # センサー初期化
    temp_sensor = TemperatureSensor()
    water_sensor = WaterLevelSensor(sensor_conf["water_level"]["gpio_pin"])
    humidity_sensor = HumiditySensor(sensor_conf["humidity"]["gpio_pin"])

    # MQTT初期化
    mqtt_client = MqttClient(
        broker=mqtt_conf["broker"],
        port=mqtt_conf["port"],
        topic_prefix=mqtt_conf["topic_prefix"]
    )

    # アクチュエーター初期化
    pump = CirculationPump(
        gpio_pin=actuator_conf["circulation_pump"]["gpio_pin"],
        active_low=actuator_conf["circulation_pump"]["active_low"]
    )

    # スケジューラ初期化・開始
    scheduler = PumpScheduler(pump, actuator_conf)
    scheduler.start()

    # インターロック初期化
    interlock = WaterLevelInterlock(water_sensor, scheduler, mqtt_client)

    # 安全管理初期化
    safety = SafetyManager(pump, mqtt_client, config["safety"])

    # MQTTコマンドハンドラー
    def handle_pump_command(topic, payload):
        """ポンプ手動制御コマンド"""
        state = payload.get("state")
        if state == "on":
            pump.on()
            logger.info("MQTTコマンド: ポンプON")
        elif state == "off":
            pump.off()
            logger.info("MQTTコマンド: ポンプOFF")

    def handle_safety_reset(topic, payload):
        """緊急停止リセットコマンド"""
        if payload.get("confirm"):
            if safety.reset():
                logger.info("MQTTコマンド: 緊急停止リセット成功")
            else:
                logger.warning("MQTTコマンド: 緊急停止リセット失敗（停止中ではない）")

    # MQTTコマンドsubscribe
    mqtt_client.subscribe("commands/pump/set", handle_pump_command)
    mqtt_client.subscribe("commands/safety/reset", handle_safety_reset)

    logger.info("制御デーモン起動（Phase 3）")

    # 読み取り間隔の管理
    last_read = {
        "temperature": 0,
        "water_level": 0,
        "humidity": 0,
        "pump_status": 0
    }

    try:
        while running:
            now = time.time()

            # 水温
            if now - last_read["temperature"] >= sensor_conf["temperature"]["interval_sec"]:
                temp = temp_sensor.read()
                mqtt_client.publish("sensors/water_temp", temp)
                logger.info(f"水温: {temp:.1f}°C")
                last_read["temperature"] = now
            else:
                temp = temp_sensor.read()  # 緊急停止判定用に毎回読む

            # 水位
            if now - last_read["water_level"] >= sensor_conf["water_level"]["interval_sec"]:
                level = water_sensor.read()
                mqtt_client.publish("sensors/water_level", level)
                if level == 0:
                    logger.warning("⚠️ 水位低下！")
                else:
                    logger.info(f"水位: 正常")
                last_read["water_level"] = now
            else:
                level = water_sensor.read()  # インターロック・緊急停止判定用に毎回読む

            # 気温・湿度
            if now - last_read["humidity"] >= sensor_conf["humidity"]["interval_sec"]:
                try:
                    data = humidity_sensor.read()
                    mqtt_client.publish("sensors/air_temp", data["air_temp"])
                    mqtt_client.publish("sensors/humidity", data["humidity"])
                    logger.info(f"気温: {data['air_temp']}°C, 湿度: {data['humidity']}%")
                except Exception as e:
                    logger.error(f"DHT22読み取りエラー: {e}")
                last_read["humidity"] = now

            # インターロック確認（水位連動）
            interlock.check()

            # 安全監視（緊急停止判定）
            if not safety.is_stopped:
                water_level_status = "normal" if level == 1 else "low"
                safety.check(water_level=water_level_status, water_temp=temp)

            # ポンプ状態をMQTT送信（60秒間隔）
            if now - last_read["pump_status"] >= 60:
                mqtt_client.publish("actuators/pump/status", {
                    "state": "on" if pump.status() else "off",
                    "runtime_hours": round(pump.runtime_hours(), 2),
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")
                })
                last_read["pump_status"] = now

            time.sleep(1)

    finally:
        scheduler.stop()
        pump.cleanup()       # ポンプOFF + GPIO解放
        water_sensor.cleanup()
        humidity_sensor.cleanup()
        mqtt_client.disconnect()
        logger.info("制御デーモン停止")


if __name__ == "__main__":
    main()