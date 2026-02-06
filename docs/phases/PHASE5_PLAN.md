# Phase 5 実行計画書: pH自動調整（オプション）

> ⚠️ **このフェーズはオプションです**
> Phase 1-4が完了していれば水耕栽培システムは十分に機能します。
> pH自動調整は「さらに自動化したい場合」の追加機能です。

> **ゴール**: pHセンサーとペリスタルティックポンプでpH自動調整を実現
>
> **前提条件**:
> - Phase 1-4 完了済み（センサー + ポンプ制御 + 藻対策 稼働中）
> - Raspberry Pi 4 Model B 1台構成
> - フルスクラッチ開発（Mycodo等の既存OSSは利用しない）

---

## フェーズ5で購入が必要なもの

| 品名 | 型番 | 概算価格 | 購入先 | 備考 |
|------|------|---------|--------|------|
| pHセンサー | PH-4502C | 約2,000円 | Amazon | アナログ出力 |
| ADS1115 ADC | 16bit 4ch | 約500円 | Amazon/秋月 | I2C接続 |
| ペリスタルティックポンプ | DC12V | 約2,000円 | Amazon | pH調整液投与用 |
| pH標準液セット | 4.0/7.0 | 約1,000円 | Amazon | キャリブレーション用 |
| pH調整液 | pH up/down | 約1,500円 | Amazon | 水耕栽培用 |
| **合計** | | **約7,000円** | | |

---

## Step 1: ADS1115 ADC接続（I2C）

pHセンサーはアナログ出力のため、ADC（アナログ-デジタル変換器）が必要。ADS1115は16bit精度の4チャンネルADCで、I2C接続。

### 配線図

```
Pi 4 GPIO               ADS1115
┌──────────┐            ┌──────────┐
│ Pin 1    │            │          │
│ 3.3V     ├────────────┤ VDD      │
│          │            │          │
│ Pin 3    │            │          │
│ GPIO2    ├────────────┤ SDA      │
│ (SDA)    │            │          │
│          │            │          │
│ Pin 5    │            │          │
│ GPIO3    ├────────────┤ SCL      │
│ (SCL)    │            │          │
│          │            │          │
│ Pin 9    │            │          │
│ GND      ├────┬───────┤ GND      │
│          │    │       │          │
│          │    └───────┤ ADDR     │  ← GND接続でアドレス0x48
│          │            │          │
└──────────┘            │ A0 ◄────┼── pHセンサー出力
                        │ A1       │  （空き）
                        │ A2       │  （空き）
                        │ A3       │  （空き）
                        └──────────┘
```

### I2C認識確認

```bash
# I2Cが有効化されていることを確認
sudo raspi-config
# Interface Options → I2C → Enable

# デバイス認識確認
i2cdetect -y 1
```

出力例:
```
     0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
00:          -- -- -- -- -- -- -- -- -- -- -- -- --
10: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
20: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
30: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
40: -- -- -- -- -- -- -- -- 48 -- -- -- -- -- -- --
50: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
60: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
70: -- -- -- -- -- -- -- --
```

`48` が表示されればADS1115が認識されている。

### Pythonライブラリインストール

```bash
pip install adafruit-circuitpython-ads1x15
```

### 動作テスト

```python
#!/usr/bin/env python3
"""test_ads1115.py - ADS1115動作確認スクリプト"""

import board
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn

# I2Cバス初期化
i2c = busio.I2C(board.SCL, board.SDA)

# ADS1115初期化
ads = ADS.ADS1115(i2c, address=0x48)

# チャンネル0を読み取り
chan = AnalogIn(ads, ADS.P0)

print(f"電圧: {chan.voltage:.4f} V")
print(f"Raw値: {chan.value}")
```

実行:
```bash
python3 test_ads1115.py
```

---

## Step 2: pHセンサー接続

### PH-4502Cモジュールの接続

```
PH-4502Cモジュール          ADS1115 / Pi
┌────────────────┐
│                │
│  V+ ───────────┼─────────── Pi 5V (Pin 2)
│                │
│  G  ───────────┼─────────── Pi GND (Pin 6)
│                │
│  Po ───────────┼─────────── ADS1115 A0
│  (アナログ出力)  │
│                │
│  Do            │  （デジタル出力、今回は未使用）
│                │
│  To            │  （温度補正、オプション）
│                │
│  ┌──────────┐  │
│  │BNCコネクタ│←── pHプローブ接続
│  └──────────┘  │
└────────────────┘
```

**注意**: PH-4502Cは5V動作。ADS1115のVDDは3.3Vだが、入力は5Vを許容。

### ディレクトリ構成

```
controller/
├── sensors/
│   ├── temperature.py
│   └── ph.py              ← 今回作成
```

### controller/sensors/ph.py

```python
"""pHセンサー読取モジュール（ADS1115経由）"""

import logging
import board
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn

logger = logging.getLogger(__name__)


class PHSensor:
    """PH-4502C pHセンサークラス"""

    def __init__(self, address=0x48, channel=0, calibration=None):
        """
        Args:
            address: ADS1115のI2Cアドレス
            channel: ADCチャンネル (0-3)
            calibration: キャリブレーション値 {"slope": float, "intercept": float}
        """
        self.i2c = busio.I2C(board.SCL, board.SDA)
        self.ads = ADS.ADS1115(self.i2c, address=address)

        # チャンネル選択
        channel_map = {0: ADS.P0, 1: ADS.P1, 2: ADS.P2, 3: ADS.P3}
        self.chan = AnalogIn(self.ads, channel_map[channel])

        # キャリブレーション値（デフォルトは未校正）
        if calibration:
            self.slope = calibration["slope"]
            self.intercept = calibration["intercept"]
        else:
            # 未校正時のデフォルト値（PH-4502C標準）
            # pH 7.0 = 2.5V, 感度 = -0.18V/pH
            self.slope = -5.56  # 1/(-0.18)
            self.intercept = 21.9  # 7.0 - (2.5 * slope)

        logger.info(f"pHセンサー初期化: アドレス=0x{address:02x}, チャンネル={channel}")
        logger.info(f"キャリブレーション: slope={self.slope:.4f}, intercept={self.intercept:.4f}")

    def read_voltage(self):
        """生の電圧値を読み取り"""
        return self.chan.voltage

    def read(self):
        """pH値を読み取り（キャリブレーション適用）"""
        voltage = self.read_voltage()
        ph = self.slope * voltage + self.intercept

        # 範囲チェック（0-14）
        ph = max(0.0, min(14.0, ph))

        logger.debug(f"pH読取: 電圧={voltage:.4f}V, pH={ph:.2f}")
        return round(ph, 2)

    def read_average(self, samples=10, delay_ms=100):
        """複数サンプルの平均を取得（ノイズ対策）"""
        import time
        readings = []
        for _ in range(samples):
            readings.append(self.read())
            time.sleep(delay_ms / 1000)

        avg = sum(readings) / len(readings)
        logger.debug(f"pH平均値: {avg:.2f} ({samples}サンプル)")
        return round(avg, 2)
```

### config.yaml 設定追加

```yaml
sensors:
  temperature:
    pin: 4
    interval_sec: 60

  ph:
    enabled: true
    adc_address: 0x48
    adc_channel: 0
    interval_sec: 120  # pH測定は2分間隔（プローブ寿命のため）
    samples: 10        # 平均化するサンプル数
    calibration:
      slope: -5.56
      intercept: 21.9
```

---

## Step 3: pHセンサーキャリブレーション

pHセンサーは定期的なキャリブレーションが必要。2点校正を行う。

### 必要なもの

- pH 4.0 標準液（酸性側基準点）
- pH 7.0 標準液（中性基準点）
- 蒸留水（プローブ洗浄用）

### キャリブレーション手順

#### 1. pH 7.0 標準液で測定

```bash
python3 scripts/calibrate_ph.py --step 7
```

プローブを pH 7.0 標準液に浸し、電圧値を記録。

#### 2. pH 4.0 標準液で測定

```bash
python3 scripts/calibrate_ph.py --step 4
```

プローブを蒸留水で洗浄後、pH 4.0 標準液に浸し、電圧値を記録。

#### 3. キャリブレーション値を計算

2点を結ぶ直線の傾き（slope）と切片（intercept）を計算:

```
slope = (pH2 - pH1) / (V2 - V1)
intercept = pH1 - (slope * V1)
```

例:
- pH 7.0 → 2.52V
- pH 4.0 → 3.05V

```
slope = (4.0 - 7.0) / (3.05 - 2.52) = -5.66
intercept = 7.0 - (-5.66 * 2.52) = 21.26
```

### scripts/calibrate_ph.py

```python
#!/usr/bin/env python3
"""pHセンサーキャリブレーションスクリプト"""

import argparse
import time
import yaml
import board
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn


def read_voltage_average(chan, samples=20, delay=0.5):
    """複数サンプルの平均電圧を取得"""
    readings = []
    for i in range(samples):
        readings.append(chan.voltage)
        print(f"  サンプル {i+1}/{samples}: {chan.voltage:.4f}V")
        time.sleep(delay)
    return sum(readings) / len(readings)


def main():
    parser = argparse.ArgumentParser(description="pHセンサーキャリブレーション")
    parser.add_argument("--step", type=float, required=True,
                        help="校正するpH値 (4.0 or 7.0)")
    parser.add_argument("--config", default="controller/config.yaml",
                        help="設定ファイルパス")
    args = parser.parse_args()

    # ADS1115初期化
    i2c = busio.I2C(board.SCL, board.SDA)
    ads = ADS.ADS1115(i2c, address=0x48)
    chan = AnalogIn(ads, ADS.P0)

    print(f"\n=== pH {args.step} キャリブレーション ===")
    print(f"プローブを pH {args.step} 標準液に浸してください。")
    print("安定したら Enter を押してください...")
    input()

    print("\n電圧を測定中...")
    voltage = read_voltage_average(chan)
    print(f"\n結果: pH {args.step} = {voltage:.4f}V")

    # 結果をファイルに保存
    cal_file = "calibration_data.yaml"
    try:
        with open(cal_file, "r") as f:
            cal_data = yaml.safe_load(f) or {}
    except FileNotFoundError:
        cal_data = {}

    cal_data[f"ph_{args.step}"] = {"voltage": voltage, "ph": args.step}

    with open(cal_file, "w") as f:
        yaml.dump(cal_data, f)
    print(f"\n保存: {cal_file}")

    # 両方のデータが揃ったら傾きと切片を計算
    if "ph_4.0" in cal_data and "ph_7.0" in cal_data:
        v1 = cal_data["ph_7.0"]["voltage"]
        v2 = cal_data["ph_4.0"]["voltage"]
        ph1 = 7.0
        ph2 = 4.0

        slope = (ph2 - ph1) / (v2 - v1)
        intercept = ph1 - (slope * v1)

        print("\n=== キャリブレーション完了 ===")
        print(f"slope: {slope:.4f}")
        print(f"intercept: {intercept:.4f}")
        print("\nconfig.yaml に以下を設定してください:")
        print(f"""
sensors:
  ph:
    calibration:
      slope: {slope:.4f}
      intercept: {intercept:.4f}
""")


if __name__ == "__main__":
    main()
```

### キャリブレーション頻度

| 状況 | 推奨頻度 |
|------|---------|
| 初期セットアップ | 必須 |
| 通常運用 | 月1回 |
| 精度に疑問がある時 | 即時 |
| プローブ交換後 | 必須 |

---

## Step 4: ペリスタルティックポンプ接続

### 配線図

```
Pi 4 GPIO               4chリレーモジュール
┌──────────┐            ┌────────────────────┐
│ GPIO17   ├────────────┤ IN1 (循環ポンプ)   │
│ GPIO27   ├────────────┤ IN2 (エアポンプ)   │
│ GPIO23   ├────────────┤ IN3 (UV)          │
│ GPIO25   ├────────────┤ IN4 (pHポンプ)    │  ← 今回追加
│ 5V       ├────────────┤ VCC               │
│ GND      ├────────────┤ GND               │
└──────────┘            └────────────────────┘

リレーCH4 ──→ ペリスタルティックポンプ（DC12V）
               │
               ▼
         12V電源から供給
```

### ペリスタルティックポンプの特性

- **流量**: 通常 0.5-10 mL/min（製品による）
- **電圧**: DC12V
- **用途**: pH調整液の精密投与

### controller/actuators/ph_pump.py

```python
"""ペリスタルティックポンプ制御モジュール（pH調整用）"""

import logging
import time
import threading
from gpiozero import OutputDevice

logger = logging.getLogger(__name__)


class PHPump:
    """pH調整液投与用ペリスタルティックポンプ"""

    def __init__(self, gpio_pin, flow_rate_ml_per_min=2.0):
        """
        Args:
            gpio_pin: GPIO番号
            flow_rate_ml_per_min: 流量（mL/分）
        """
        self.relay = OutputDevice(gpio_pin, active_high=False, initial_value=False)
        self.flow_rate = flow_rate_ml_per_min
        self.is_running = False
        self.total_dispensed_ml = 0.0
        self._lock = threading.Lock()

        logger.info(f"pHポンプ初期化: GPIO{gpio_pin}, 流量={flow_rate_ml_per_min}mL/min")

    def dispense(self, volume_ml):
        """指定量を投与"""
        with self._lock:
            if self.is_running:
                logger.warning("ポンプは既に動作中")
                return False

            # 投与時間を計算
            duration_sec = (volume_ml / self.flow_rate) * 60

            logger.info(f"pH調整液投与開始: {volume_ml}mL ({duration_sec:.1f}秒)")

            self.is_running = True
            self.relay.on()

            time.sleep(duration_sec)

            self.relay.off()
            self.is_running = False
            self.total_dispensed_ml += volume_ml

            logger.info(f"pH調整液投与完了: {volume_ml}mL (累計: {self.total_dispensed_ml:.1f}mL)")
            return True

    def dispense_async(self, volume_ml, callback=None):
        """非同期で投与（メインループをブロックしない）"""
        def _dispense():
            result = self.dispense(volume_ml)
            if callback:
                callback(result, volume_ml)

        thread = threading.Thread(target=_dispense, daemon=True)
        thread.start()
        return thread

    def stop(self):
        """緊急停止"""
        self.relay.off()
        self.is_running = False
        logger.warning("pHポンプ緊急停止")

    def get_status(self):
        """ステータス取得"""
        return {
            "is_running": self.is_running,
            "total_dispensed_ml": round(self.total_dispensed_ml, 2),
            "flow_rate_ml_per_min": self.flow_rate
        }

    def cleanup(self):
        """終了処理"""
        self.stop()
        self.relay.close()
```

### config.yaml 設定追加

```yaml
actuators:
  pump:
    gpio: 17
  air_pump:
    gpio: 27
  uv_sterilizer:
    gpio: 23
    mode: pump_linked

  ph_pump:
    gpio: 25
    flow_rate_ml_per_min: 2.0  # ポンプの流量（製品仕様を確認）
    min_dispense_ml: 0.5       # 最小投与量
    max_dispense_ml: 5.0       # 最大投与量（安全制限）
```

---

## Step 5: pH自動調整ロジック

### 制御フロー

```
┌─────────────────────────────────────────────────────────┐
│                   メインループ                          │
│                                                         │
│   ┌──────────┐     ┌──────────────┐     ┌───────────┐  │
│   │ pH測定   │────►│ 範囲チェック  │────►│ 調整判定  │  │
│   └──────────┘     └──────────────┘     └─────┬─────┘  │
│                                               │        │
│                    ┌──────────────────────────┤        │
│                    │                          │        │
│                    ▼                          ▼        │
│            ┌──────────────┐          ┌──────────────┐  │
│            │ pH up 投与   │          │ pH down 投与 │  │
│            │ (低い場合)   │          │ (高い場合)   │  │
│            └──────┬───────┘          └──────┬───────┘  │
│                   │                          │        │
│                   └──────────┬───────────────┘        │
│                              ▼                        │
│                      ┌──────────────┐                 │
│                      │ 混合待機     │                 │
│                      │ (5-10分)     │                 │
│                      └──────────────┘                 │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 目標pH範囲

| 状態 | pH範囲 | アクション |
|------|--------|-----------|
| 正常 | 5.5 - 6.5 | なし |
| やや低い | 5.0 - 5.5 | pH up 少量投与 |
| 低すぎ | < 5.0 | pH up 投与 + アラート |
| やや高い | 6.5 - 7.0 | pH down 少量投与 |
| 高すぎ | > 7.0 | pH down 投与 + アラート |

### ディレクトリ構成

```
controller/
├── automation/
│   └── ph_controller.py   ← 今回作成
```

### controller/automation/ph_controller.py

```python
"""pH自動調整コントローラー"""

import logging
import time
from enum import Enum
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


class PHAction(Enum):
    NONE = "none"
    UP = "up"
    DOWN = "down"


@dataclass
class PHControlResult:
    action: PHAction
    amount_ml: float
    before_ph: float
    target_range: tuple


class PHController:
    """pH自動調整コントローラー"""

    def __init__(self, ph_sensor, ph_up_pump, ph_down_pump=None, config=None):
        """
        Args:
            ph_sensor: PHSensorインスタンス
            ph_up_pump: pH上昇用ペリスタルティックポンプ
            ph_down_pump: pH下降用ペリスタルティックポンプ（オプション）
            config: 設定辞書
        """
        self.ph_sensor = ph_sensor
        self.ph_up_pump = ph_up_pump
        self.ph_down_pump = ph_down_pump

        # デフォルト設定
        self.config = config or {}
        self.target_min = self.config.get("target_min", 5.5)
        self.target_max = self.config.get("target_max", 6.5)
        self.dose_ml = self.config.get("dose_ml", 1.0)
        self.mix_wait_sec = self.config.get("mix_wait_sec", 300)  # 5分
        self.max_adjustments_per_hour = self.config.get("max_adjustments_per_hour", 4)

        self.last_adjustment_time = 0
        self.adjustments_this_hour = 0
        self.enabled = True

        logger.info(f"pH自動調整初期化: 目標範囲={self.target_min}-{self.target_max}")

    def check_and_adjust(self) -> Optional[PHControlResult]:
        """pHをチェックし、必要なら調整"""
        if not self.enabled:
            logger.debug("pH自動調整は無効")
            return None

        # レート制限チェック
        if not self._check_rate_limit():
            logger.warning("調整頻度制限に達しています")
            return None

        # pH測定
        current_ph = self.ph_sensor.read_average(samples=5)
        logger.info(f"現在のpH: {current_ph}")

        # 範囲内なら何もしない
        if self.target_min <= current_ph <= self.target_max:
            logger.debug(f"pH {current_ph} は目標範囲内")
            return PHControlResult(
                action=PHAction.NONE,
                amount_ml=0,
                before_ph=current_ph,
                target_range=(self.target_min, self.target_max)
            )

        # 調整が必要
        if current_ph < self.target_min:
            return self._adjust_up(current_ph)
        else:
            return self._adjust_down(current_ph)

    def _adjust_up(self, current_ph) -> PHControlResult:
        """pHを上げる"""
        logger.info(f"pH {current_ph} が低いため、pH up液を投与")

        if self.ph_up_pump:
            self.ph_up_pump.dispense(self.dose_ml)
            self._record_adjustment()

            return PHControlResult(
                action=PHAction.UP,
                amount_ml=self.dose_ml,
                before_ph=current_ph,
                target_range=(self.target_min, self.target_max)
            )
        else:
            logger.warning("pH upポンプが設定されていません")
            return None

    def _adjust_down(self, current_ph) -> PHControlResult:
        """pHを下げる"""
        logger.info(f"pH {current_ph} が高いため、pH down液を投与")

        if self.ph_down_pump:
            self.ph_down_pump.dispense(self.dose_ml)
            self._record_adjustment()

            return PHControlResult(
                action=PHAction.DOWN,
                amount_ml=self.dose_ml,
                before_ph=current_ph,
                target_range=(self.target_min, self.target_max)
            )
        else:
            logger.warning("pH downポンプが設定されていません")
            return None

    def _check_rate_limit(self) -> bool:
        """調整頻度をチェック"""
        current_time = time.time()

        # 1時間経過したらカウントをリセット
        if current_time - self.last_adjustment_time > 3600:
            self.adjustments_this_hour = 0

        return self.adjustments_this_hour < self.max_adjustments_per_hour

    def _record_adjustment(self):
        """調整を記録"""
        self.last_adjustment_time = time.time()
        self.adjustments_this_hour += 1

    def wait_for_mixing(self):
        """混合待機"""
        logger.info(f"混合待機中... ({self.mix_wait_sec}秒)")
        time.sleep(self.mix_wait_sec)

    def enable(self):
        """自動調整を有効化"""
        self.enabled = True
        logger.info("pH自動調整: 有効")

    def disable(self):
        """自動調整を無効化"""
        self.enabled = False
        logger.info("pH自動調整: 無効")

    def get_status(self):
        """ステータス取得"""
        return {
            "enabled": self.enabled,
            "target_range": [self.target_min, self.target_max],
            "dose_ml": self.dose_ml,
            "adjustments_this_hour": self.adjustments_this_hour,
            "max_adjustments_per_hour": self.max_adjustments_per_hour
        }
```

### config.yaml 設定追加

```yaml
automation:
  ph_control:
    enabled: true
    target_min: 5.5
    target_max: 6.5
    dose_ml: 1.0              # 1回の投与量
    mix_wait_sec: 300         # 投与後の待機時間（5分）
    max_adjustments_per_hour: 4  # 1時間あたりの最大調整回数
```

### main.py への統合

```python
from sensors.ph import PHSensor
from actuators.ph_pump import PHPump
from automation.ph_controller import PHController

# 初期化
ph_sensor = PHSensor(
    address=config["sensors"]["ph"]["adc_address"],
    channel=config["sensors"]["ph"]["adc_channel"],
    calibration=config["sensors"]["ph"]["calibration"]
)

ph_up_pump = PHPump(
    gpio_pin=config["actuators"]["ph_pump"]["gpio"],
    flow_rate_ml_per_min=config["actuators"]["ph_pump"]["flow_rate_ml_per_min"]
)

ph_controller = PHController(
    ph_sensor=ph_sensor,
    ph_up_pump=ph_up_pump,
    config=config["automation"]["ph_control"]
)

# メインループ内（pH測定間隔ごと）
ph_value = ph_sensor.read_average()
mqtt_client.publish("sensors/ph", ph_value)

# 自動調整チェック
result = ph_controller.check_and_adjust()
if result and result.action != PHAction.NONE:
    mqtt_client.publish("automation/ph_adjustment", {
        "action": result.action.value,
        "amount_ml": result.amount_ml,
        "before_ph": result.before_ph
    })
    ph_controller.wait_for_mixing()
```

---

## Step 6: Grafanaダッシュボード

### pHパネル: ゲージ

1. Add Panel → Stat または Gauge
2. Query (Flux):

```flux
from(bucket: "hydroponics")
  |> range(start: -5m)
  |> filter(fn: (r) => r.topic == "hydroponics/sensors/ph")
  |> filter(fn: (r) => r._field == "value")
  |> last()
```

3. 設定:
   - Unit: none
   - Decimals: 2
   - Min: 0, Max: 14
   - Thresholds:
     - 5.5: 緑
     - 5.0: 黄
     - 0: 赤

### pHパネル: 折れ線グラフ

1. Add Panel → Time series
2. Query (Flux):

```flux
from(bucket: "hydroponics")
  |> range(start: -24h)
  |> filter(fn: (r) => r.topic == "hydroponics/sensors/ph")
  |> filter(fn: (r) => r._field == "value")
  |> aggregateWindow(every: 5m, fn: mean)
```

3. 設定:
   - Y軸: Min=4, Max=9
   - 閾値ライン:
     - 5.5 (緑帯の下限)
     - 6.5 (緑帯の上限)
   - Fill below to: 目標範囲を緑で塗りつぶし

### pH調整履歴パネル

1. Add Panel → Table
2. Query (Flux):

```flux
from(bucket: "hydroponics")
  |> range(start: -7d)
  |> filter(fn: (r) => r.topic == "hydroponics/automation/ph_adjustment")
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> sort(columns: ["_time"], desc: true)
  |> limit(n: 50)
```

3. カラム:
   - `_time` → "日時"
   - `action` → "アクション" (up/down)
   - `amount_ml` → "投与量(mL)"
   - `before_ph` → "調整前pH"

---

## 動作確認チェックリスト

### ハードウェア
- [ ] ADS1115がI2Cで認識される（`i2cdetect -y 1` で 0x48）
- [ ] `test_ads1115.py` で電圧が読める
- [ ] pHセンサーがキャリブレーション済み
- [ ] キャリブレーション値が config.yaml に保存されている

### ソフトウェア
- [ ] pHセンサーから正しい値が読める
- [ ] pH値がMQTT `hydroponics/sensors/ph` にpublishされる
- [ ] ペリスタルティックポンプがリレー制御で動作する
- [ ] 指定量の液が投与される

### 自動調整
- [ ] pH 5.5未満で pH up が投与される
- [ ] pH 6.5超で pH down が投与される（ポンプ設置時）
- [ ] 投与後に混合待機時間がある
- [ ] 1時間あたりの調整回数制限が機能する

### Grafana
- [ ] pHゲージパネルが表示される
- [ ] pH履歴グラフが表示される
- [ ] 目標範囲（5.5-6.5）が緑で表示される
- [ ] pH調整履歴テーブルが表示される

---

## トラブルシューティング

### ADS1115が認識されない

1. 配線確認（SDA/SCL/VDD/GND）
2. I2Cが有効か確認: `sudo raspi-config`
3. アドレス設定確認（ADDRピンがGND接続で0x48）

### pH値が不安定

1. プローブを蒸留水で洗浄
2. キャリブレーションを再実行
3. サンプル数を増やす（`samples: 20`）
4. プローブの寿命確認（通常1-2年）

### 投与量が不正確

1. ポンプの流量をキャリブレーション
   - 実際に1分間動かして出た量を計測
   - `flow_rate_ml_per_min` を更新
2. チューブの詰まりを確認
3. 12V電源の電圧を確認

### pH調整が効かない

1. pH調整液の濃度を確認
2. 投与量を増やす（`dose_ml`）
3. 混合待機時間を延ばす（`mix_wait_sec`）
4. 養液量に対して投与量が少なすぎないか確認

---

## 安全に関する注意事項

### pH調整液の取り扱い

- **pH up液**: 強アルカリ性。皮膚・目に触れないよう注意
- **pH down液**: 強酸性。皮膚・目に触れないよう注意
- 保管は子供の手の届かない場所に
- 使用時はゴム手袋推奨

### 過剰投与防止

- `max_adjustments_per_hour` で調整回数を制限
- `max_dispense_ml` で1回の最大投与量を制限
- 異常なpH値（<3.0 または >10.0）では自動調整を停止
