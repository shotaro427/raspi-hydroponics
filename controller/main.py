#!/usr/bin/env python3
"""水耕栽培制御デーモン - Phase 2"""

import logging
import signal
import time
import yaml

from sensors.temperature import TemperatureSensor
from sensors.water_level import WaterLevelSensor
from sensors.humidity import HumiditySensor
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

    # センサー初期化
    temp_sensor = TemperatureSensor()
    water_sensor = WaterLevelSensor(sensor_conf["water_level"]["gpio_pin"])
    humidity_sensor = HumiditySensor(sensor_conf["humidity"]["gpio_pin"])

    mqtt_client = MqttClient(
        broker=mqtt_conf["broker"],
        port=mqtt_conf["port"],
        topic_prefix=mqtt_conf["topic_prefix"]
    )

    logger.info("制御デーモン起動（Phase 2）")

    # 読み取り間隔の管理
    last_read = {
        "temperature": 0,
        "water_level": 0,
        "humidity": 0
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

            # 水位
            if now - last_read["water_level"] >= sensor_conf["water_level"]["interval_sec"]:
                level = water_sensor.read()
                mqtt_client.publish("sensors/water_level", level)
                if level == 0:
                    logger.warning("⚠️ 水位低下！")
                else:
                    logger.info(f"水位: 正常")
                last_read["water_level"] = now

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

            time.sleep(1)

    finally:
        water_sensor.cleanup()
        humidity_sensor.cleanup()
        mqtt_client.disconnect()
        logger.info("制御デーモン停止")


if __name__ == "__main__":
    main()