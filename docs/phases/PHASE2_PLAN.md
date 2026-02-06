# Phase 2 実行計画書: センサー拡張 → Grafana一覧表示

> **ゴール**: 水位センサー・気温湿度センサーを追加し、Grafanaで全センサー値を一覧表示
>
> **前提条件**:
> - Phase 1 完了済み（DS18B20 + Docker Compose + Grafana 稼働中）
> - Raspberry Pi 4 Model B 1台構成
> - フルスクラッチ開発（Mycodo等の既存OSSは利用しない）

> **Note**: pHセンサーはPhase 5（オプション）で追加可能です。[docs/phases/PHASE5_PLAN.md](./PHASE5_PLAN.md) を参照。

---

## フェーズ2で購入が必要なもの

| 品名 | 型番 | 概算価格 | 購入先 | 備考 |
|------|------|---------|--------|------|
| フロートスイッチ | PP製 | 約300円 | Amazon | 水位検知用 |
| 温湿度センサー | DHT22 | 約500円 | Amazon | 気温・湿度計測 |
| ジャンパーワイヤ追加 | オス-メス | 約300円 | Amazon | 必要に応じて |
| **合計** | | **約1,100円** | | |

---

## Step 1: フロートスイッチ接続

### 配線

```
Pi 4 GPIO               フロートスイッチ
┌──────────┐            ┌──────────────┐
│ Pin 15   │            │              │
│ GPIO22   ├────────────┤ 端子A        │
│          │            │              │
│ Pin 6    │            │              │
│ GND      ├────────────┤ 端子B        │
└──────────┘            └──────────────┘

※ 内蔵プルアップを使用するか、外付け10kΩで3.3Vに接続
```

### 動作原理

| 水位状態 | フロート位置 | スイッチ状態 | GPIO読み取り値 |
|---------|-------------|-------------|---------------|
| 正常（水あり） | 上 | CLOSE | LOW (0) |
| 低下（水なし） | 下 | OPEN | HIGH (1) |

### controller/sensors/water_level.py

```python
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
        if state == GPIO.LOW:
            status = "normal"
        else:
            status = "low"
        logger.debug(f"水位: {status}")
        return status

    def is_low(self) -> bool:
        """水位が低下しているか"""
        return self.read() == "low"

    def cleanup(self):
        GPIO.cleanup(self.pin)
```

### テストスクリプト

```python
#!/usr/bin/env python3
"""test_water_level.py - フロートスイッチ動作確認"""

import RPi.GPIO as GPIO
import time

FLOAT_PIN = 22

GPIO.setmode(GPIO.BCM)
GPIO.setup(FLOAT_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

print("フロートスイッチテスト（Ctrl+Cで終了）")
print("フロートを手で上下させて動作確認してください")

try:
    while True:
        state = GPIO.input(FLOAT_PIN)
        status = "正常（水あり）" if state == GPIO.LOW else "低下（水なし）"
        print(f"水位: {status}", end="\r")
        time.sleep(0.5)
except KeyboardInterrupt:
    print("\n終了")
finally:
    GPIO.cleanup()
```

### config.yaml に追加

```yaml
sensors:
  water_level:
    gpio_pin: 22
    interval_sec: 10  # 水位は頻繁にチェック
```

---

## Step 2: DHT22接続（気温・湿度）

### 依存パッケージ

```bash
sudo apt install libgpiod2
pip install adafruit-circuitpython-dht
```

### 配線

```
Pi 4 GPIO               DHT22
┌──────────┐            ┌──────────────┐
│ Pin 1    │            │              │
│ 3.3V     ├────────────┤ VCC (ピン1)  │
│          │            │              │
│ Pin 11   │            │              │
│ GPIO17   ├────────────┤ DATA (ピン2) │
│          │            │              │
│          │            │ NC (ピン3)   │ ← 未使用
│          │            │              │
│ Pin 6    │            │              │
│ GND      ├────────────┤ GND (ピン4)  │
└──────────┘            └──────────────┘

※ 4.7kΩ〜10kΩのプルアップ抵抗をVCCとDATAの間に接続推奨
  （多くのDHT22モジュールは抵抗内蔵）
```

### controller/sensors/humidity.py

```python
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
```

### テストスクリプト

```python
#!/usr/bin/env python3
"""test_dht22.py - DHT22動作確認"""

import board
import adafruit_dht
import time

dht = adafruit_dht.DHT22(board.D17)

print("DHT22テスト（5回読み取り）")

for i in range(5):
    try:
        temp = dht.temperature
        hum = dht.humidity
        print(f"[{i+1}/5] 気温: {temp:.1f}°C, 湿度: {hum:.1f}%")
    except RuntimeError as e:
        print(f"[{i+1}/5] 読み取りエラー: {e}（再試行で解消することが多い）")
    time.sleep(2)

dht.exit()
print("テスト完了")
```

### config.yaml に追加

```yaml
sensors:
  humidity:
    gpio_pin: 17
    interval_sec: 60
```

---

## Step 3: controller/ にセンサーモジュール統合

### ディレクトリ構成（Phase 2完了後）

```
controller/
├── main.py
├── config.yaml
├── mqtt_client.py
└── sensors/
    ├── __init__.py
    ├── temperature.py   # Phase 1
    ├── water_level.py   # Phase 2 新規
    └── humidity.py      # Phase 2 新規
```

### config.yaml（完全版）

```yaml
mqtt:
  broker: localhost
  port: 1883
  topic_prefix: hydroponics

sensors:
  temperature:
    interval_sec: 60

  water_level:
    gpio_pin: 22
    interval_sec: 10

  humidity:
    gpio_pin: 17
    interval_sec: 60
```

### main.py（Phase 2版）

```python
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
                if level == "low":
                    logger.warning("⚠️ 水位低下！")
                else:
                    logger.info(f"水位: {level}")
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
```

### MQTTトピック一覧

| トピック | 値 | 単位 |
|---------|-----|------|
| `hydroponics/sensors/water_temp` | 数値 | °C |
| `hydroponics/sensors/water_level` | "normal" or "low" | - |
| `hydroponics/sensors/air_temp` | 数値 | °C |
| `hydroponics/sensors/humidity` | 数値 | % |

---

## Step 4: Grafanaダッシュボードにウィジェット追加

### パネル設定

#### 1. 水位パネル（Stat）

- Visualization: **Stat**
- Query (Flux):

```flux
from(bucket: "hydroponics")
  |> range(start: -1m)
  |> filter(fn: (r) => r.topic == "hydroponics/sensors/water_level")
  |> filter(fn: (r) => r._field == "value")
  |> last()
```

- Value mappings:
  - "normal" → 🟢 正常
  - "low" → 🔴 低下

#### 2. 気温パネル（Time series）

- Visualization: **Time series**
- Query (Flux):

```flux
from(bucket: "hydroponics")
  |> range(start: -1h)
  |> filter(fn: (r) => r.topic == "hydroponics/sensors/air_temp")
  |> filter(fn: (r) => r._field == "value")
```

- Unit: Celsius (°C)
- Thresholds: 15°C〜30°C を緑

#### 3. 湿度パネル（Time series）

- Visualization: **Time series**
- Query (Flux):

```flux
from(bucket: "hydroponics")
  |> range(start: -1h)
  |> filter(fn: (r) => r.topic == "hydroponics/sensors/humidity")
  |> filter(fn: (r) => r._field == "value")
```

- Unit: Percent (0-100)
- Thresholds: 40%〜70% を緑

#### 4. 全センサー一覧ダッシュボード

推奨レイアウト（2x2グリッド）:

```
┌───────────────┬───────────────┐
│   水温 (°C)   │ 水位 (ステータス)│
│  Time series  │     Stat      │
├───────────────┼───────────────┤
│   気温 (°C)   │   湿度 (%)    │
│  Time series  │  Time series │
└───────────────┴───────────────┘
```

---

## 動作確認チェックリスト

### センサー認識
- [ ] フロートスイッチが水位変化に反応する（手動テスト）
- [ ] DHT22から気温・湿度が読める（test_dht22.py）

### データパイプライン
- [ ] 全センサー値がMQTTにpublishされている（mosquitto_sub で確認）
- [ ] InfluxDB Data Explorerで全トピックのデータが確認できる
- [ ] Grafanaで全センサー値のパネルが表示されている

### アラート
- [ ] 水位低下時にログ警告が出る

### 永続化
- [ ] hydroponics-controllerサービス再起動後も動作する
- [ ] Pi再起動後も自動復旧する

---

## ブレッドボード配線図

→ [docs/diagrams/phase2_breadboard.svg](../diagrams/phase2_breadboard.svg) を参照（pHセンサー無し版）
