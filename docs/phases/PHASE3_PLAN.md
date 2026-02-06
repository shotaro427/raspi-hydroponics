# Phase 3: アクチュエーター制御

> **Status**: 計画中
> **前提**: Phase 1-2 完了済み（全センサー稼働中）
> **Last Updated**: 2026-02-06

## ゴール

**循環ポンプとエアポンプをリレー制御し、タイマー＋水位連動で自動運転する**

---

## 前提条件

- Phase 1-2 完了済み（DS18B20, pH, EC, フロートスイッチ全て稼働中）
- Pi 4 Model B 1台構成
- フルスクラッチ開発（既存OSSは利用しない）

---

## 購入品リスト

| 品名 | 型番 | 概算価格 | 購入先 | 備考 |
|------|------|---------|--------|------|
| 4chリレーモジュール | 5V駆動 | 約500円 | Amazon/秋月電子 | 光アイソレータ付き推奨 |
| DC12V水中ポンプ | - | 約1,500円 | Amazon | 流量200-400L/h |
| エアポンプ | アクアリウム用 | 約1,500円 | Amazon | 静音タイプ推奨 |
| AC-DC 12V電源 | 5A | 約1,500円 | Amazon | ポンプ・リレー用 |
| 電源分岐ケーブル | - | 約300円 | Amazon | 12V分配用 |
| **合計** | | **約5,300円** | | |

> **Note**: USB水中ポンプ（BOM記載）を使う場合は12V電源不要だが、流量が弱い

---

## ステップ一覧

### Step 1: リレーモジュール接続

4chリレーモジュールをPi 4に接続する。

#### 配線

| リレー側 | 接続先 | 用途 |
|---------|--------|------|
| VCC | 5V | 電源 |
| GND | GND | グランド |
| IN1 | GPIO17 | 循環ポンプ |
| IN2 | GPIO27 | エアポンプ |
| IN3 | GPIO23 | UV殺菌灯（Phase 4用、予約） |
| IN4 | GPIO24 | 予備 |

#### リレー出力側

- **NO/COM端子**を使用（通常OFF、信号でON）
- NO = Normally Open（通常開放）
- COM = Common（共通端子）

#### 動作確認

```bash
# GPIOを手動でHIGH/LOWしてリレー動作を確認
# カチッという音が鳴ればOK
python3 -c "
import RPi.GPIO as GPIO
import time
GPIO.setmode(GPIO.BCM)
GPIO.setup(17, GPIO.OUT)
GPIO.output(17, GPIO.HIGH)
time.sleep(1)
GPIO.output(17, GPIO.LOW)
GPIO.cleanup()
"
```

---

### Step 2: controller/actuators/pump.py 作成

循環ポンプのON/OFF制御を実装する。

#### クラス設計

```python
class CirculationPump:
    """循環ポンプ制御クラス"""

    def __init__(self, gpio_pin: int):
        """初期化（GPIOピン設定）"""
        pass

    def on(self) -> None:
        """ポンプをONにする"""
        pass

    def off(self) -> None:
        """ポンプをOFFにする"""
        pass

    def status(self) -> bool:
        """現在の状態を返す（True=ON, False=OFF）"""
        pass
```

#### MQTTトピック

| 方向 | トピック | ペイロード |
|------|---------|-----------|
| コマンド受信 | `hydroponics/commands/pump/set` | `{"state": "on"}` or `{"state": "off"}` |
| ステータス送信 | `hydroponics/actuators/pump/status` | `{"state": "on", "timestamp": "..."}` |

---

### Step 3: controller/actuators/air_pump.py 作成

エアポンプのON/OFF制御を実装する。

#### クラス設計

pump.py と同じ構造で `AirPump` クラスを作成。

#### MQTTトピック

| 方向 | トピック | ペイロード |
|------|---------|-----------|
| コマンド受信 | `hydroponics/commands/air_pump/set` | `{"state": "on"}` or `{"state": "off"}` |
| ステータス送信 | `hydroponics/actuators/air_pump/status` | `{"state": "on", "timestamp": "..."}` |

---

### Step 4: タイマー制御ロジック

スケジュールに従ってポンプを自動制御する。

#### config.yaml 設定例

```yaml
actuators:
  circulation_pump:
    gpio: 17
    schedule:
      - start: "06:00"
        end: "22:00"
        interval_minutes: 15  # 15分ON/15分OFF
  air_pump:
    gpio: 27
    mode: always_on  # または schedule
```

#### 実装

- `controller/scheduler.py` を新規作成
- **APScheduler** または **asyncio** を使用
- 日の出〜日没（6:00-22:00）は15分間隔でON/OFF
- 夜間は循環ポンプOFF、エアポンプは常時ON

---

### Step 5: 水位連動ロジック

水位センサーと連動してポンプを制御する。

#### 水位低下時

1. 循環ポンプを**即座に停止**
2. エアポンプは継続可
3. アラート発報（MQTT + Grafana）

#### 水位復帰時

1. ポンプ制御を**スケジュールに戻す**
2. ログ記録

#### 実装

- `controller/interlock.py` を新規作成
- `water_level.py` からのコールバックを受け取る

---

### Step 6: 緊急停止ロジック（safety.py）

安全を確保するための緊急停止機能を実装する。

#### 緊急停止条件

| 条件 | 閾値 |
|------|------|
| 水位最低レベル以下 | フロートスイッチ LOW |
| 水温異常 | 30°C 超 |
| pH異常 | 4.0 以下 or 8.0 以上 |

#### 緊急停止時のアクション

1. **全ポンプ停止**（循環・エア両方）
2. アラート発報（MQTT `hydroponics/alerts/emergency_stop`）
3. ログ記録（タイムスタンプ + 理由）
4. **手動リセットまで自動復帰しない**

#### 手動リセット

```bash
# MQTTコマンドでリセット
mosquitto_pub -t "hydroponics/commands/safety/reset" -m '{"confirm": true}'
```

---

### Step 7: Grafanaにポンプ稼働状態表示

ダッシュボードにポンプ状態を追加する。

#### パネル構成

| パネル | 種類 | データソース |
|--------|------|-------------|
| 循環ポンプ状態 | Stat（ON/OFF） | InfluxDB |
| エアポンプ状態 | Stat（ON/OFF） | InfluxDB |
| ポンプ稼働時間 | Time series | InfluxDB |
| 緊急停止履歴 | Table | InfluxDB |

---

## 動作確認チェックリスト

- [ ] リレーモジュールがGPIO制御で動作する
- [ ] 循環ポンプがリレー経由でON/OFF可能
- [ ] エアポンプがリレー経由でON/OFF可能
- [ ] タイマースケジュール通りに動作する
- [ ] 水位低下時にポンプが自動停止する
- [ ] 水位復帰時にスケジュール制御に戻る
- [ ] Grafanaでポンプ状態が確認できる
- [ ] MQTTコマンドで手動制御可能

---

## ファイル構成（Phase 3 完了後）

```
controller/
├── actuators/
│   ├── pump.py           # 循環ポンプ制御
│   └── air_pump.py       # エアポンプ制御
├── scheduler.py          # タイマー制御
├── interlock.py          # 水位連動ロジック
└── safety.py             # 緊急停止ロジック（更新）
```

---

## 関連図面

- [docs/diagrams/phase3_breadboard.svg](../diagrams/phase3_breadboard.svg) — ブレッドボード＋リレー配線図

---

## 次のフェーズ

Phase 4 では UV殺菌灯の制御と藻対策機能を追加する。
