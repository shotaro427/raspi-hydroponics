# Phase 1 実行計画書: 水温センサー → Grafana表示

> **ゴール**: DS18B20で水温を取得し、Grafanaで表示されること
>
> **前提条件**:
> - Raspberry Pi 4 Model B 1台（OS + WiFi設定済み）
> - フルスクラッチ開発（Mycodo等の既存OSSは利用しない）
> - Docker Composeで Mosquitto + InfluxDB + Grafana + Telegraf を同一マシンで動かす
> - MQTTは localhost 通信

---

## Step 0: ラズパイ初期セットアップ

### SSH有効化確認

```bash
sudo systemctl status ssh
```

activeでなければ有効化:

```bash
sudo systemctl enable --now ssh
```

### システム更新

```bash
sudo apt update && sudo apt full-upgrade -y
```

### Python 3.11+ 確認

```bash
python3 --version
```

3.11未満の場合、ソースからビルド:

```bash
sudo apt install -y build-essential libssl-dev zlib1g-dev \
  libncurses5-dev libncursesw5-dev libreadline-dev libsqlite3-dev \
  libgdbm-dev libdb5.3-dev libbz2-dev libexpat1-dev liblzma-dev \
  libffi-dev uuid-dev

cd /tmp
wget https://www.python.org/ftp/python/3.11.9/Python-3.11.9.tgz
tar xzf Python-3.11.9.tgz
cd Python-3.11.9
./configure --enable-optimizations
make -j$(nproc)
sudo make altinstall

python3.11 --version
```

### Docker + Docker Compose インストール

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
```

**再ログインが必要**（`exit` → SSH再接続）。再ログイン後:

```bash
docker --version
docker compose version
```

### I2C 有効化

```bash
sudo raspi-config
```

Interface Options → I2C → Enable

### 1-Wire 有効化

```bash
sudo raspi-config
```

Interface Options → 1-Wire → Enable

設定ファイルを確認:

```bash
grep dtoverlay /boot/firmware/config.txt
```

`dtoverlay=w1-gpio` が含まれていること。なければ手動追加:

```bash
echo "dtoverlay=w1-gpio" | sudo tee -a /boot/firmware/config.txt
```

### GPIO関連パッケージ

```bash
pip install RPi.GPIO gpiozero
```

### 作業ディレクトリ作成

```bash
mkdir -p ~/raspi-hydroponics/{controller/{sensors,actuators},server/{mosquitto,grafana},scripts,tests}
```

### 再起動

```bash
sudo reboot
```

再起動後、SSH再接続して `docker --version` と `ls /sys/bus/w1/devices/` で設定が反映されたことを確認。

---

## Step 1: Docker Compose環境構築

### ディレクトリ構成

```
server/
├── docker-compose.yml
├── mosquitto/
│   └── mosquitto.conf
└── telegraf/
    └── telegraf.conf
```

### docker-compose.yml

```yaml
version: "3.8"

services:
  mosquitto:
    image: eclipse-mosquitto:2
    container_name: mosquitto
    ports:
      - "1883:1883"
    volumes:
      - ./mosquitto/mosquitto.conf:/mosquitto/config/mosquitto.conf
      - mosquitto-data:/mosquitto/data
      - mosquitto-log:/mosquitto/log
    restart: unless-stopped

  influxdb:
    image: influxdb:2
    container_name: influxdb
    ports:
      - "8086:8086"
    volumes:
      - influxdb-data:/var/lib/influxdb2
    environment:
      - DOCKER_INFLUXDB_INIT_MODE=setup
      - DOCKER_INFLUXDB_INIT_USERNAME=admin
      - DOCKER_INFLUXDB_INIT_PASSWORD=hydroponics
      - DOCKER_INFLUXDB_INIT_ORG=home
      - DOCKER_INFLUXDB_INIT_BUCKET=hydroponics
      - DOCKER_INFLUXDB_INIT_ADMIN_TOKEN=my-super-secret-token
    restart: unless-stopped

  telegraf:
    image: telegraf
    container_name: telegraf
    volumes:
      - ./telegraf/telegraf.conf:/etc/telegraf/telegraf.conf:ro
    depends_on:
      - mosquitto
      - influxdb
    restart: unless-stopped

  grafana:
    image: grafana/grafana-oss
    container_name: grafana
    ports:
      - "3000:3000"
    volumes:
      - grafana-data:/var/lib/grafana
    depends_on:
      - influxdb
    restart: unless-stopped

volumes:
  mosquitto-data:
  mosquitto-log:
  influxdb-data:
  grafana-data:
```

### mosquitto.conf

```
listener 1883
allow_anonymous true
persistence true
persistence_location /mosquitto/data/
log_dest file /mosquitto/log/mosquitto.log
```

### telegraf.conf

```toml
[agent]
  interval = "10s"
  flush_interval = "10s"

[[inputs.mqtt_consumer]]
  servers = ["tcp://mosquitto:1883"]
  topics = ["hydroponics/#"]
  data_format = "json"
  topic_tag = "topic"

[[outputs.influxdb_v2]]
  urls = ["http://influxdb:8086"]
  token = "my-super-secret-token"
  organization = "home"
  bucket = "hydroponics"
```

### 設定ファイル配置と起動

```bash
cd ~/raspi-hydroponics/server

# ディレクトリ作成
mkdir -p mosquitto telegraf

# mosquitto.conf と telegraf.conf を上記の内容で作成（省略）

# 起動
docker compose up -d

# 全サービスがrunningか確認
docker compose ps
```

4つのサービス（mosquitto, influxdb, telegraf, grafana）が全て `running` であること。

### Grafana初期ログイン

1. ブラウザで `http://<PiのIP>:3000` にアクセス
2. ユーザー名: `admin` / パスワード: `admin`
3. 初回ログイン時にパスワード変更を求められるので変更する

---

## Step 2: DS18B20 水温センサー接続

### 配線図

```
Pi 4 GPIO               DS18B20（防水型）
┌──────────┐            ┌──────────┐
│ Pin 1    │            │          │
│ 3.3V     ├──┬─────────┤ VCC (赤) │
│          │  │         │          │
│          │ [4.7kΩ]    │          │
│          │  │         │          │
│ Pin 7    │  │         │          │
│ GPIO4    ├──┴─────────┤ DATA(黄) │
│          │            │          │
│ Pin 9    │            │          │
│ GND      ├────────────┤ GND (黒) │
└──────────┘            └──────────┘

※ 4.7kΩプルアップ抵抗は VCC と DATA の間に接続
※ ブレッドボードで配線するのが簡単
```

### 1-Wire デバイス認識確認

```bash
ls /sys/bus/w1/devices/
```

`28-xxxxxxxxxxxx` というディレクトリが見えるはず。見えない場合は配線とconfig.txtの設定を再確認。

```bash
cat /sys/bus/w1/devices/28-*/temperature
```

ミリ度Cで温度が出力される（例: `23456` = 23.456°C）。

### Pythonテストスクリプト

#### 方法1: sysfsから直接読む（依存なし）

```python
#!/usr/bin/env python3
"""test_ds18b20.py - DS18B20動作確認スクリプト（sysfs版）"""

import glob
import time

DEVICE_BASE_DIR = "/sys/bus/w1/devices/"
DEVICE_PATTERN = "28-*"


def find_device():
    """1-Wireデバイスを検索"""
    devices = glob.glob(DEVICE_BASE_DIR + DEVICE_PATTERN)
    if not devices:
        raise FileNotFoundError("DS18B20が見つかりません。配線と1-Wire設定を確認してください。")
    return devices[0]


def read_temperature(device_path):
    """sysfsからミリ度Cを読んで°Cに変換"""
    temp_file = device_path + "/temperature"
    with open(temp_file, "r") as f:
        raw = f.read().strip()
    return int(raw) / 1000.0


if __name__ == "__main__":
    device = find_device()
    print(f"デバイス検出: {device}")

    for i in range(5):
        temp = read_temperature(device)
        print(f"[{i+1}/5] 水温: {temp:.1f} °C")
        time.sleep(2)

    print("テスト完了")
```

#### 方法2: w1thermsensorライブラリを使用

```bash
pip install w1thermsensor
```

```python
#!/usr/bin/env python3
"""test_ds18b20_lib.py - DS18B20動作確認スクリプト（w1thermsensor版）"""

from w1thermsensor import W1ThermSensor
import time

sensor = W1ThermSensor()
print(f"デバイスID: {sensor.id}")

for i in range(5):
    temp = sensor.get_temperature()
    print(f"[{i+1}/5] 水温: {temp:.1f} °C")
    time.sleep(2)

print("テスト完了")
```

実行:

```bash
cd ~/raspi-hydroponics/tests
python3 test_ds18b20.py
```

5回の読み取りで妥当な温度値（室温付近）が出力されれば成功。

---

## Step 3: Python制御デーモンの骨格作成

### ディレクトリ構成

```
controller/
├── main.py              # メインループ
├── sensors/
│   └── temperature.py   # DS18B20水温読取
├── mqtt_client.py       # localhost MQTT pub/sub
└── config.yaml          # 設定ファイル
```

### config.yaml

```yaml
mqtt:
  broker: localhost
  port: 1883
  topic_prefix: hydroponics

sensors:
  temperature:
    pin: 4
    interval_sec: 60
```

### sensors/temperature.py

```python
"""DS18B20水温センサー読取モジュール"""

import glob
import logging

logger = logging.getLogger(__name__)

DEVICE_BASE_DIR = "/sys/bus/w1/devices/"
DEVICE_PATTERN = "28-*"


class TemperatureSensor:
    def __init__(self):
        self.device_path = self._find_device()
        logger.info(f"DS18B20検出: {self.device_path}")

    def _find_device(self):
        devices = glob.glob(DEVICE_BASE_DIR + DEVICE_PATTERN)
        if not devices:
            raise FileNotFoundError("DS18B20が見つかりません")
        return devices[0]

    def read(self):
        """水温を°Cで返す"""
        temp_file = self.device_path + "/temperature"
        with open(temp_file, "r") as f:
            raw = f.read().strip()
        temp_c = int(raw) / 1000.0
        logger.debug(f"水温: {temp_c:.1f}°C")
        return temp_c
```

### mqtt_client.py

```python
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
```

### main.py

```python
#!/usr/bin/env python3
"""水耕栽培制御デーモン - メインループ"""

import logging
import signal
import time
import yaml

from sensors.temperature import TemperatureSensor
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

    # 設定読み込み
    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)

    mqtt_conf = config["mqtt"]
    sensor_conf = config["sensors"]["temperature"]

    # 初期化
    temp_sensor = TemperatureSensor()
    mqtt_client = MqttClient(
        broker=mqtt_conf["broker"],
        port=mqtt_conf["port"],
        topic_prefix=mqtt_conf["topic_prefix"]
    )

    logger.info("制御デーモン起動")
    interval = sensor_conf["interval_sec"]

    try:
        while running:
            temp = temp_sensor.read()
            mqtt_client.publish("sensors/water_temp", temp)
            logger.info(f"水温: {temp:.1f}°C → MQTT送信完了")
            time.sleep(interval)
    finally:
        mqtt_client.disconnect()
        logger.info("制御デーモン停止")


if __name__ == "__main__":
    main()
```

### pip依存パッケージ

```bash
pip install paho-mqtt pyyaml w1thermsensor
```

### systemdサービスファイル

`/etc/systemd/system/hydroponics-controller.service`:

```ini
[Unit]
Description=Hydroponics Controller
After=network.target docker.service

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/raspi-hydroponics/controller
ExecStart=/usr/bin/python3 main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

有効化と起動:

```bash
sudo systemctl daemon-reload
sudo systemctl enable hydroponics-controller
sudo systemctl start hydroponics-controller

# ログ確認
journalctl -u hydroponics-controller -f
```

---

## Step 4: MQTT → InfluxDB → Grafana パイプライン構築

### データフロー

```
Python (main.py)
  │
  │ paho-mqtt publish
  │ topic: hydroponics/sensors/water_temp
  │ payload: {"value": 23.5}
  ▼
Mosquitto (localhost:1883)
  │
  │ subscribe: hydroponics/#
  ▼
Telegraf
  │
  │ [[outputs.influxdb_v2]]
  ▼
InfluxDB (localhost:8086)
  │
  │ Flux query
  ▼
Grafana (localhost:3000)
```

### InfluxDB 初期セットアップ

docker-compose.yml の環境変数で自動セットアップ済み（Step 1参照）。

Web UIでの確認:

1. `http://<PiのIP>:8086` にアクセス
2. ログイン: `admin` / `hydroponics`
3. 左メニュー「Data Explorer」でデータ到着を確認

### MQTT疎通確認

Pythonデーモン起動前に、手動でMQTTの疎通を確認する:

```bash
# ターミナル1: subscribe（受信待ち）
docker exec mosquitto mosquitto_sub -t 'hydroponics/#' -v

# ターミナル2: publish（テスト送信）
docker exec mosquitto mosquitto_pub -t 'hydroponics/sensors/water_temp' -m '{"value": 23.5}'
```

ターミナル1に `hydroponics/sensors/water_temp {"value": 23.5}` が表示されれば疎通OK。

### Grafana ダッシュボード設定

#### 1. データソース追加

1. Grafana (`http://<PiのIP>:3000`) にログイン
2. 左メニュー → Connections → Data sources → Add data source
3. **InfluxDB** を選択
4. 設定:
   - Query Language: **Flux**
   - URL: `http://influxdb:8086`
   - Organization: `home`
   - Token: `my-super-secret-token`
   - Default Bucket: `hydroponics`
5. 「Save & test」で接続確認

#### 2. ダッシュボード作成

1. 左メニュー → Dashboards → New Dashboard → Add visualization
2. データソース: InfluxDB（上で追加したもの）
3. Query（Flux）:

```flux
from(bucket: "hydroponics")
  |> range(start: -1h)
  |> filter(fn: (r) => r.topic == "hydroponics/sensors/water_temp")
  |> filter(fn: (r) => r._field == "value")
```

4. Visualization: **Time series**
5. Panel title: **水温（°C）**
6. 閾値設定:
   - Thresholds → Add threshold
   - 18°C: 緑（適正下限）
   - 25°C: 黄（適正上限）
   - 30°C: 赤（危険）
7. 「Apply」で保存

#### 3. 自動リフレッシュ

ダッシュボード右上の更新間隔を `1m`（1分）に設定。

---

## Step 5: 動作確認チェックリスト

### ハードウェア
- [ ] DS18B20が `/sys/bus/w1/devices/28-*` で認識されている
- [ ] `cat /sys/bus/w1/devices/28-*/temperature` で温度値が読める
- [ ] Pythonテストスクリプト（test_ds18b20.py）で水温が読める

### Docker / サービス
- [ ] `docker compose ps` で4サービス全てが running
- [ ] MQTTブローカー（Mosquitto）が稼働中
- [ ] `mosquitto_sub` でトピックを確認できる

### データパイプライン
- [ ] Pythonデーモンが水温をMQTTにpublishしている
- [ ] TelegrafがMQTTからInfluxDBにデータを転送している
- [ ] InfluxDB Web UI（:8086）のData Explorerでデータが確認できる
- [ ] Grafana（:3000）で水温のタイムシリーズグラフが表示されている

### 永続化 / 自動起動
- [ ] `systemctl status hydroponics-controller` が active
- [ ] Pi再起動後、Docker Composeの全サービスが自動復旧する
- [ ] Pi再起動後、hydroponics-controllerが自動起動する

---

## フェーズ1で購入が必要なもの

| 品名 | 概算価格 | 購入先 | 備考 |
|------|---------|--------|------|
| DS18B20 防水温度センサー | 約500円 | Amazon/秋月電子 | ケーブル付き防水型を推奨 |
| 4.7kΩ抵抗 | 約50円 | 秋月電子 | センサーキットに付属の場合あり |
| ブレッドボード | 約300-500円 | Amazon/秋月電子 | ハーフサイズで十分 |
| ジャンパーワイヤ（オス-メス） | 約300-500円 | Amazon/秋月電子 | 10本セット程度 |
| **合計** | **約1,150-1,550円** | | |

※ Pi 4本体、SDカードは手持ちのため購入不要
