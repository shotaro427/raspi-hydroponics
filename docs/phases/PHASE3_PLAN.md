# Phase 3: アクチュエーター制御

> **Status**: 計画中
> **前提**: Phase 1-2 完了済み（全センサー稼働中）
> **Last Updated**: 2026-02-07

## ゴール

**循環ポンプをリレー制御し、タイマー＋水位連動で自動運転する**

---

## 前提条件

- Phase 1-2 完了済み（DS18B20, DHT22, フロートスイッチ全て稼働中）
- Pi 4 Model B 1台構成
- フルスクラッチ開発（既存OSSは利用しない）

---

## エアポンプについて

NFT（薄膜水耕法）方式では根の上部が常に空気に触れており、DWC方式ほどエアレーションの必要性が高くない。
小規模ハーブ栽培であることも考慮し、**Phase 3 ではエアポンプを設置しない**。

養液交換の頻度を上げることで溶存酸素不足を補う。将来必要になった場合は、リレーCH2（GPIO27）を使って追加可能。

---

## GPIO競合の解決

Phase 2 では DHT22 を GPIO17 に接続していたが、Phase 3 で GPIO17 をリレーIN1（循環ポンプ制御）に使用するため、**DHT22 を GPIO5 (Pin 29) に移動**する。

| 変更対象 | 変更前 | 変更後 |
|---------|--------|--------|
| DHT22 DATA線 | GPIO17 (Pin 11) | **GPIO5 (Pin 29)** |
| config.yaml `sensors.humidity.gpio_pin` | 17 | **5** |

> GPIO5 は 1-Wire・I2C・SPI 等の特殊機能に使われておらず、DHT22 で問題なく使用可能。
> Phase 2 のドキュメント・配線図・config.yaml も合わせて修正済み。

---

## GPIO割り当て一覧（Phase 1〜3）

| GPIO | Pin | 用途 | Phase | 方向 | 備考 |
|------|-----|------|-------|------|------|
| GPIO4 | 7 | DS18B20 水温センサー | 1 | IN | 1-Wire |
| GPIO5 | 29 | DHT22 気温・湿度 | 2 | IN | GPIO17から移動 |
| GPIO22 | 15 | フロートスイッチ（水位） | 2 | IN | 内蔵プルアップ使用 |
| GPIO17 | 11 | リレーIN1 → 循環ポンプ | 3 | OUT | ACTIVE LOW |
| GPIO27 | 13 | リレーIN2 → 予備 | - | OUT | 将来エアポンプ等に利用可 |
| GPIO23 | 16 | リレーIN3 → UV殺菌灯 | 4予約 | OUT | Phase 4で使用 |
| GPIO24 | 18 | リレーIN4 → 予備 | - | OUT | 未使用 |

---

## 購入品リスト

| 品名 | 型番 | 概算価格 | 購入先 | 備考 |
|------|------|---------|--------|------|
| 4chリレーモジュール | 5V駆動 | 約500円 | Amazon/秋月電子 | 光アイソレータ付き必須 |
| DC12V水中ポンプ | - | 約1,500円 | Amazon | 流量200-400L/h |
| AC-DC 12V電源 | 5A | 約1,500円 | Amazon | ポンプ用 |
| **合計** | | **約3,500円** | | |

> **Note**: エアポンプは不採用（NFT方式のためエアレーション不要と判断）。
> DC分岐ケーブルもポンプ1台のみのため不要。
> 12V電源は5Aを選んでおくと、Phase 4のUV殺菌灯追加時にも対応可能。

---

## 配線詳細

### 配線A: リレーモジュール ↔ Raspberry Pi

リレーモジュールの**入力側**をPiのGPIOに接続する。

```
Raspberry Pi 4                         4ch リレーモジュール（入力側）
┌──────────────────────┐              ┌──────────────────────────────┐
│ Pin 2  (5V)          ├──── 赤 ─────┤ VCC                          │
│ Pin 6  (GND)         ├──── 黒 ─────┤ GND                          │
│ Pin 11 (GPIO17)      ├──── 青 ─────┤ IN1  →  CH1: 循環ポンプ       │
│ Pin 13 (GPIO27)      ├─ ─ 灰 ─ ─ ─┤ IN2  →  CH2: 予備            │
│ Pin 16 (GPIO23)      ├─ ─ 灰 ─ ─ ─┤ IN3  →  CH3: UV殺菌灯（予約） │
│ Pin 18 (GPIO24)      ├─ ─ 灰 ─ ─ ─┤ IN4  →  CH4: 予備            │
└──────────────────────┘              └──────────────────────────────┘
                                        ※ 破線 = Phase 4以降で接続
                                        ※ Phase 3 では IN1 のみ使用
```

**接続時の注意点**:
- ジャンパーワイヤ（オス-メス）を使用
- VCCは必ず5V（3.3Vではリレーが動作しない）
- GNDはPiと共通

---

### 配線B: DC12V 循環ポンプ（リレーCH1経由）

リレーモジュールの**出力側** COM/NO端子を使って、12V電源とポンプの間にリレーを挟む。

```
AC-DC 12V PSU               リレーCH1 出力側            DC12V 循環ポンプ
┌──────────────┐            ┌──────────────────┐        ┌──────────────────┐
│              │            │                  │        │                  │
│  +12V out  ──┼──オレンジ──┤→ COM1            │        │                  │
│              │            │                  │        │                  │
│              │            │  NO1  ───────────┼─オレンジ┤→ + (赤線)        │
│              │            │                  │        │                  │
│              │            │  NC1 (使わない)   │        │                  │
│              │            │                  │        │                  │
│  GND out   ──┼──── 黒 ────┼──────────────────┼── 黒 ──┤→ - (黒線)        │
│              │            │                  │        │                  │
└──────────────┘            └──────────────────┘        └──────────────────┘
```

**電流の流れ**:
```
GPIO17 → LOW の場合:
  12V PSU (+) → COM1 → [リレー接点ON] → NO1 → ポンプ(+) → ポンプ(-) → PSU GND
  → ポンプ回転 ✅

GPIO17 → HIGH の場合:
  12V PSU (+) → COM1 → [リレー接点OFF] → NO1 は開放
  → 電流が流れない → ポンプ停止 ✅
```

---

### 配線C: 12V電源（全体図）

ポンプ1台のみのため、DC分岐ケーブルは不要。12V電源から直接リレーCOM1に接続する。

```
    AC100V コンセント
         │
  ┌──────┴──────┐
  │ AC-DC 12V   │
  │ 5A 電源     │
  │ (60W)       │
  └──┬─────┬────┘
     │     │
+12V │     │ GND
     │     │
  COM1     │
  ┌──┘     │
  │ リレー  │
  │ CH1    │
  │ NO1    │
  │  │     │
  │  ▼     │
  │  P+    │
  │ 循環   │
  │ ポンプ  │
  │  P-    │
  │  │     │
  └──┴─────┘
     GND共通
```

**12V電源の容量計算**:
- 循環ポンプ: 約3-5W（0.25-0.42A @ 12V）
- 5A電源なら余裕あり（Phase 4のUV殺菌灯も同電源から取れる）

---

## リレー動作ロジック（ACTIVE LOW）

一般的な4chリレーモジュールは**ACTIVE LOW**（LOW信号でリレーON）で動作する。

### 真理値表

| GPIO出力 | リレーコイル | NO端子の状態 | ポンプ | 安全性 |
|---------|------------|------------|-------|--------|
| **HIGH (1)** | 非通電 | 開放 (OPEN) | **停止** | Pi起動時のデフォルト = 安全 |
| **LOW (0)** | 通電 | 閉路 (CLOSE) | **動作** | コードで明示的にONした時のみ |

### 端子の意味

```
COM (Common)        = 共通端子。電源の+12Vを接続
NO  (Normally Open) = 通常開放。リレーON時に閉じる → ポンプに接続
NC  (Normally Close)= 通常閉路。リレーON時に開く → 今回は使わない
```

### 安全設計上の意味

1. **Pi起動時**: GPIOのデフォルト状態はHIGH → 全リレーOFF → ポンプ停止（安全側）
2. **Pi異常終了・クラッシュ時**: GPIOはHIGHに戻る → ポンプ停止（安全側）
3. **Pi電源断時**: リレーのコイルに電流が流れない → ポンプ停止（安全側）
4. **ソフトウェアで明示的にLOWにした時のみ**ポンプが動作する

→ フェイルセーフ設計: 何か異常が起きたら常にポンプが止まる方向に倒れる

### JD-VCC ジャンパーについて

多くの4chリレーモジュールにはJD-VCCジャンパーがある:

```
ジャンパー装着（デフォルト）:
  VCC ──── JD-VCC が直結
  → Pi の 5V でリレーコイルも駆動
  → 配線がシンプル。初期段階はこれでOK

ジャンパー外す（電気的分離）:
  VCC ←── Pi 5V（ロジック用のみ）
  JD-VCC ←── 別の 5V 電源（リレーコイル駆動用）
  → Pi と 12V 系統が完全に分離（光アイソレータが有効になる）
  → ノイズ耐性が向上。本番運用時に推奨
```

---

## ソフトウェア実装

### Step 1: リレーモジュール動作確認

4chリレーモジュールをPiに接続し、GPIO制御で動作確認する。

#### 配線

（上記「配線A: リレーモジュール ↔ Raspberry Pi」参照）

#### 動作確認スクリプト

```bash
# GPIOを手動でHIGH/LOWしてリレー動作を確認
# カチッという音が鳴ればOK
python3 -c "
import RPi.GPIO as GPIO
import time

GPIO.setmode(GPIO.BCM)
GPIO.setup(17, GPIO.OUT)
GPIO.output(17, GPIO.HIGH)  # 初期状態: OFF

print('リレーCH1 (GPIO17) テスト...')
GPIO.output(17, GPIO.LOW)   # ON → カチッ
time.sleep(2)
GPIO.output(17, GPIO.HIGH)  # OFF → カチッ

GPIO.cleanup()
print('テスト完了')
"
```

> **確認ポイント**: GPIO.output(17, GPIO.LOW) でカチッと音が鳴り、GPIO.output(17, GPIO.HIGH) でカチッと戻ればOK。
> 音が鳴らない場合 → VCC/GND の配線を確認。

---

### Step 2: controller/actuators/pump.py

循環ポンプのON/OFF制御を実装する。

```python
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
```

#### MQTTトピック

| 方向 | トピック | ペイロード |
|------|---------|-----------|
| コマンド受信 | `hydroponics/commands/pump/set` | `{"state": "on"}` or `{"state": "off"}` |
| ステータス送信 | `hydroponics/actuators/pump/status` | `{"state": "on", "runtime_hours": 1.5, "timestamp": "..."}` |

---

### Step 3: controller/scheduler.py（タイマー制御）

スケジュールに従って循環ポンプを自動制御する。

#### 依存パッケージ

```bash
pip install apscheduler
```

#### config.yaml 設定

```yaml
actuators:
  circulation_pump:
    gpio_pin: 17
    active_low: true
    schedule:
      day_start: "06:00"
      day_end: "22:00"
      on_minutes: 15
      off_minutes: 15
```

#### クラス設計

```python
"""タイマー制御スケジューラ"""

import logging
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)


class PumpScheduler:
    """循環ポンプのタイマー制御を管理する

    日中モード (day_start〜day_end):
      - 循環ポンプ: on_minutes ON / off_minutes OFF を繰り返す

    夜間モード (day_end〜day_start):
      - 循環ポンプ: OFF
    """

    def __init__(self, pump, config: dict):
        """
        Args:
            pump: CirculationPumpインスタンス
            config: config.yaml の actuators セクション
        """

    def start(self) -> None:
        """スケジューラを開始する"""

    def stop(self) -> None:
        """スケジューラを停止する（グレースフルシャットダウン時）"""

    def pause(self) -> None:
        """一時停止（水位低下時にinterlockから呼ばれる）
        循環ポンプを即座にOFFにし、スケジュールを一時停止する。
        """

    def resume(self) -> None:
        """再開（水位復帰時にinterlockから呼ばれる）
        スケジュールを再開し、現在のモードに応じてポンプ制御を復帰する。
        """

    def _toggle_pump(self) -> None:
        """循環ポンプのON/OFFをトグルする（interval_minutesごとに呼ばれる）"""

    def _enter_day_mode(self) -> None:
        """日中モードに入る（day_startの時刻に呼ばれる）
        循環ポンプのインターバル制御を開始する。
        """

    def _enter_night_mode(self) -> None:
        """夜間モードに入る（day_endの時刻に呼ばれる）
        循環ポンプをOFFにする。
        """
```

#### 動作タイムライン（例）

```
時刻    循環ポンプ  モード
──────────────────────────
00:00   OFF        夜間
06:00   ON         日中開始
06:15   OFF        インターバル
06:30   ON         インターバル
06:45   OFF        インターバル
 ...    (15分ON/OFF繰り返し)
22:00   OFF        夜間開始
23:59   OFF        夜間
```

---

### Step 4: controller/interlock.py（水位連動ロジック）

水位センサーと連動してポンプを制御する。

**interlock と safety の違い:**

| | interlock | safety |
|---|----------|--------|
| 目的 | 水位低下時のポンプ保護 | 致命的異常の緊急停止 |
| トリガー | 水位LOW | 水位LOW持続 or 水温30°C超 |
| 復帰 | **自動復帰**（水位復帰時） | **手動リセット必須** |
| 対象 | 循環ポンプ | 循環ポンプ |

#### クラス設計

```python
"""水位連動ロジック（自動復帰可能）"""

import logging

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

    def check(self) -> None:
        """メインループから定期的に呼ばれる。
        水位を確認し、必要に応じてスケジューラをpause/resumeする。
        """

    def _on_water_low(self) -> None:
        """水位低下検知時の処理"""

    def _on_water_normal(self) -> None:
        """水位復帰時の処理"""
```

---

### Step 5: controller/safety.py（緊急停止ロジック）

安全を確保するための緊急停止機能を実装する。

#### 緊急停止条件

| 条件 | 閾値 | 備考 |
|------|------|------|
| 水位最低レベル以下 | フロートスイッチ LOW 持続 | interlock で停止後も復帰しない場合 |
| 水温異常 | 30°C 超 | ポンプ過熱・環境温度異常 |

> **Note**: Phase 1-4 では pH センサーは未実装のため、緊急停止は水位・水温のみで判定する。

#### クラス設計

```python
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

    def check(self, water_level: str, water_temp: float) -> None:
        """メインループから呼ばれる。条件を確認し必要に応じて緊急停止する。

        Args:
            water_level: "normal" or "low"
            water_temp: 水温（°C）
        """

    def emergency_stop(self, reason: str) -> None:
        """緊急停止を実行する。

        Args:
            reason: 停止理由（ログ・MQTT通知に含める）
        """

    def reset(self) -> bool:
        """手動リセット。MQTTコマンドから呼ばれる。

        Returns:
            True: リセット成功, False: リセット条件を満たさない
        """

    @property
    def is_stopped(self) -> bool:
        """緊急停止中かどうか"""
```

#### 手動リセット

```bash
# MQTTコマンドでリセット
mosquitto_pub -t "hydroponics/commands/safety/reset" -m '{"confirm": true}'
```

---

### Step 6: controller/mqtt_client.py にsubscribe機能追加

Phase 1 の publish 機能に加え、コマンド受信のための subscribe 機能を追加する。

```python
def subscribe(self, topic: str, callback) -> None:
    """トピックをsubscribeしコールバックを登録する。

    Args:
        topic: subscribeするMQTTトピック
        callback: メッセージ受信時に呼ばれるコールバック関数
                  callback(topic: str, payload: dict) の形式
    """
```

subscribe するトピック:

| トピック | 用途 |
|---------|------|
| `hydroponics/commands/pump/set` | 循環ポンプの手動ON/OFF |
| `hydroponics/commands/safety/reset` | 緊急停止の手動リセット |

---

### Step 7: controller/main.py（Phase 3版）

Phase 2 の main.py を拡張し、アクチュエーター制御を統合する。

#### 追加する初期化処理

```python
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

# MQTTコマンドsubscribe
mqtt_client.subscribe("hydroponics/commands/pump/set", handle_pump_command)
mqtt_client.subscribe("hydroponics/commands/safety/reset", handle_safety_reset)
```

#### メインループに追加する処理

```python
while running:
    now = time.time()

    # ... 既存のセンサー読み取り ...

    # インターロック確認（水位連動）
    interlock.check()

    # 安全監視（緊急停止判定）
    if not safety.is_stopped:
        safety.check(water_level=level, water_temp=temp)

    # ポンプ状態をMQTT送信（60秒間隔）
    if now - last_read.get("pump_status", 0) >= 60:
        mqtt_client.publish("actuators/pump/status", {
            "state": "on" if pump.status() else "off",
            "runtime_hours": round(pump.runtime_hours(), 2)
        })
        last_read["pump_status"] = now

    time.sleep(1)
```

#### グレースフルシャットダウン

```python
finally:
    scheduler.stop()
    pump.cleanup()       # ポンプOFF + GPIO解放
    water_sensor.cleanup()
    humidity_sensor.cleanup()
    mqtt_client.disconnect()
    logger.info("制御デーモン停止")
```

---

### Step 8: Grafanaにポンプ稼働状態表示

ダッシュボードにポンプ状態パネルを追加する。

#### パネル構成

| パネル | 種類 | データソース |
|--------|------|-------------|
| 循環ポンプ状態 | Stat（ON/OFF） | InfluxDB |
| ポンプ稼働時間 | Time series | InfluxDB |
| 緊急停止履歴 | Table | InfluxDB |

---

## config.yaml 完全版（Phase 3）

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
    gpio_pin: 5          # Phase 2で GPIO17→5 に変更（リレーと競合解決）
    interval_sec: 60

actuators:
  circulation_pump:
    gpio_pin: 17         # リレー IN1
    active_low: true     # LOW信号でリレーON（一般的な4chリレー）
    schedule:
      day_start: "06:00"
      day_end: "22:00"
      on_minutes: 15     # 日中: 15分ON
      off_minutes: 15    # 日中: 15分OFF

safety:
  emergency_stop:
    water_temp_max: 30.0     # この温度を超えたら緊急停止
    manual_reset_required: true  # 緊急停止後に手動リセット必須
```

---

## テスト計画

### 1. リレー動作テスト（tests/test_relay.py）

```python
#!/usr/bin/env python3
"""リレーモジュール動作確認スクリプト

CH1のリレーをON/OFFして、カチッと音が鳴ることを確認する。
"""

import RPi.GPIO as GPIO
import time

PUMP_PIN = 17

GPIO.setmode(GPIO.BCM)
GPIO.setup(PUMP_PIN, GPIO.OUT)
GPIO.output(PUMP_PIN, GPIO.HIGH)  # 初期状態: OFF

print("リレー動作テスト\n")
print(f"  CH1 (GPIO{PUMP_PIN}): ON...", end="", flush=True)
GPIO.output(PUMP_PIN, GPIO.LOW)   # ACTIVE LOW: LOWでON
time.sleep(2)
GPIO.output(PUMP_PIN, GPIO.HIGH)  # OFF
print(" OFF")

GPIO.cleanup()
print("\nテスト完了")
```

### 2. ポンプ制御ユニットテスト（tests/test_pump.py）

GPIO の mock を使い、CirculationPump クラスの動作を確認する。

- `on()` 呼び出しで GPIO が LOW になること
- `off()` 呼び出しで GPIO が HIGH になること
- `status()` が正しい値を返すこと
- `runtime_hours()` が正しく累積されること
- `cleanup()` で OFF + GPIO 解放されること

### 3. 統合テスト（tests/test_integration_phase3.py）

リレー→ポンプ→水流を実際に確認する手動テスト:

```python
#!/usr/bin/env python3
"""Phase 3 統合テスト

実際にポンプを動かして水が流れることを確認する。
※ 配管・水を用意してから実行すること
"""

from actuators.pump import CirculationPump
import time

print("=== Phase 3 統合テスト ===\n")

pump = CirculationPump(gpio_pin=17)

# テスト1: ポンプON
print("[1/2] 循環ポンプ ON（5秒間）...")
pump.on()
time.sleep(5)
print(f"  状態: {'ON' if pump.status() else 'OFF'}")
print(f"  稼働時間: {pump.runtime_hours():.4f} 時間")
pump.off()
print("  → OFF\n")

# テスト2: ON/OFF繰り返し
print("[2/2] ON/OFF繰り返し（3回 x 2秒間）...")
for i in range(3):
    pump.on()
    time.sleep(2)
    pump.off()
    time.sleep(1)
print(f"  累積稼働時間: {pump.runtime_hours():.4f} 時間\n")

pump.cleanup()
print("=== テスト完了 ===")
```

---

## 動作確認チェックリスト

- [ ] リレーモジュールがGPIO制御で動作する（カチッと音が鳴る）
- [ ] 循環ポンプがリレー経由でON/OFF可能
- [ ] タイマースケジュール通りに動作する（日中15分ON/OFF、夜間OFF）
- [ ] 水位低下時にポンプが自動停止する
- [ ] 水位復帰時にスケジュール制御に戻る
- [ ] 緊急停止が正しく発動する（水温30°C超）
- [ ] 緊急停止後、MQTTリセットコマンドで復帰できる
- [ ] Grafanaでポンプ状態が確認できる
- [ ] MQTTコマンドで手動制御可能

---

## トラブルシューティング

| 症状 | 考えられる原因 | 対処法 |
|------|--------------|--------|
| リレーがカチッと鳴らない | VCCかGNDが未接続 | 5V/GND配線を確認。テスターで導通チェック |
| GPIOをLOWにしてもリレーが動かない | ACTIVE HIGHタイプのリレー | config.yamlで `active_low: false` に変更 |
| ポンプが回らない | COM/NO接続が逆、またはNC端子に接続 | テスターでNO-COM間の導通を確認。NO端子に接続し直す |
| Pi起動時にポンプが一瞬動く | GPIO初期化前のグリッチ | `/boot/config.txt` に `gpio=17=op,dh` を追加して起動時HIGHを強制 |
| ポンプの回転が弱い | 電源容量不足 | 12V電源の出力アンペアを確認。ポンプの消費電力を計算 |
| リレーが勝手にON/OFFする | ノイズ、GPIO浮き | JD-VCCジャンパーを外して電源を分離。プルアップ抵抗を追加 |

---

## ファイル構成（Phase 3 完了後）

```
controller/
├── main.py                    # Phase 3版に更新
├── config.yaml                # actuatorsセクション追加
├── mqtt_client.py             # subscribe機能追加
├── sensors/
│   ├── __init__.py
│   ├── temperature.py         # Phase 1
│   ├── water_level.py         # Phase 2
│   └── humidity.py            # Phase 2 (GPIO5に変更)
├── actuators/
│   ├── __init__.py
│   └── pump.py                # 新規: 循環ポンプ制御
├── scheduler.py               # 新規: タイマー制御
├── interlock.py               # 新規: 水位連動ロジック
└── safety.py                  # 新規: 緊急停止ロジック
```

---

## 関連図面

- [docs/diagrams/phase3_breadboard.svg](../diagrams/phase3_breadboard.svg) — ブレッドボード＋リレー配線図

---

## 次のフェーズ

Phase 4 では UV殺菌灯の制御と藻対策機能を追加する。
リレーCH3 (GPIO23) を使用し、循環ポンプ連動モードまたはタイマーモードで制御する。
