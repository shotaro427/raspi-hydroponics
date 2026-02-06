# Phase 4 実行計画書: 藻対策（UV殺菌・水温管理・完全遮光）

> **ゴール**: インラインUVステライザーで藻対策、水温管理（高温時アラート）、完全遮光
>
> **前提条件**:
> - Phase 1-3 完了済み（センサー + ポンプ制御 稼働中）
> - Raspberry Pi 4 Model B 1台構成
> - フルスクラッチ開発（Mycodo等の既存OSSは利用しない）

---

## フェーズ4で購入が必要なもの

| 品名 | 型番 | 概算価格 | 購入先 | 備考 |
|------|------|---------|--------|------|
| インラインUVステライザー | アクアリウム用 15-25W | 約5,000円 | Amazon | 配管インライン式 |
| 水槽用ヒーター | 50-100W | 約2,000円 | Amazon | 冬季用、オプション |
| 追加遮光材料 | アルミテープ等 | 約500円 | ダイソー | 百均で調達可 |
| **合計** | | **約7,500円** | | ※ヒーターはオプション |

---

## Step 1: UVステライザーの配管への組み込み（物理作業）

### 設置位置

UVステライザーはポンプ吐出口の直後、T字分岐の前に設置する。

```
配管経路（水の流れ）:

リザーバー
    │
    ▼
┌──────────┐
│ 循環ポンプ │
└────┬─────┘
     │ 吐出口（6mm）
     ▼
┌──────────────────┐
│ UVステライザー    │  ← ここに挿入
│ （インライン式）   │
└────┬─────────────┘
     │
     ▼
┌──────────┐
│ T字分岐  │
└──┬───┬──┘
   │   │
   ▼   ▼
チャンネルA  チャンネルB
（上段）    （中段）
```

### 配管作業手順

1. **システム停止**: ポンプOFF、電源を切る
2. **水抜き**: リザーバーの水を別容器に移す
3. **チューブカット**: ポンプ吐出口〜T字分岐間のチューブを切断
4. **UV接続**:
   - IN側（入口）をポンプ吐出口に接続
   - OUT側（出口）をT字分岐に接続
   - **重要**: 水流方向を示す矢印を確認すること
5. **ホース径確認**: UV機器のホース接続部と既存チューブの径を確認
   - 不一致の場合は変換アダプタ（ホースニップル）を使用
6. **結束バンド固定**: 接続部を結束バンドで締める
7. **漏れ確認**: 水を入れて漏れがないか確認

### 注意事項

- **水流方向**: UVステライザー本体に矢印がある。逆接続すると効果が出ない
- **ホース径**: 一般的なアクアリウム用は内径12-16mm。水耕用6-10mmチューブとは変換が必要
- **電源防水**: UVの電源コードは水場から離す。防水コンセントカバー推奨
- **設置位置**: 配管の途中で垂直に設置（空気溜まり防止）

### 配管組込図

詳細な配管図は [docs/diagrams/phase4_uv_plumbing.svg](../diagrams/phase4_uv_plumbing.svg) を参照。

---

## Step 2: UVのリレー制御

### GPIO配線

Phase 3で追加したリレーモジュールのCH3を使用:

```
Pi 4 GPIO               4chリレーモジュール
┌──────────┐            ┌────────────────────┐
│ GPIO17   ├────────────┤ IN1 (ポンプ)       │
│ GPIO27   ├────────────┤ IN2 (エアポンプ)   │
│ GPIO23   ├────────────┤ IN3 (UV)          │  ← 今回追加
│ GPIO24   ├────────────┤ IN4 (予備)        │
│ 5V       ├────────────┤ VCC               │
│ GND      ├────────────┤ GND               │
└──────────┘            └────────────────────┘

リレーCH3 ──→ UVステライザー電源（AC100V）
```

### 制御モード

| モード | 説明 | 用途 |
|--------|------|------|
| `pump_linked` | 循環ポンプON時のみUV ON | 推奨（水流がある時のみ殺菌） |
| `timer` | 30分ON / 30分OFF の独立タイマー | ポンプと別制御したい場合 |
| `always_on` | ポンプ稼働中は常にON | 最大限の殺菌効果 |

### config.yaml 設定追加

```yaml
actuators:
  pump:
    gpio: 17
    # ... 既存設定

  air_pump:
    gpio: 27
    # ... 既存設定

  uv_sterilizer:
    gpio: 23
    mode: pump_linked  # pump_linked, timer, always_on
    timer_minutes_on: 30
    timer_minutes_off: 30
    # UVランプ寿命管理
    lamp_lifetime_hours: 8000  # 一般的なUVランプ寿命
```

---

## Step 3: controller/actuators/uv.py 作成

### ファイル配置

```
controller/
├── actuators/
│   ├── pump.py
│   ├── air_pump.py
│   └── uv.py          ← 今回作成
```

### uv.py

```python
"""UVステライザー制御モジュール"""

import logging
import time
import threading
from gpiozero import OutputDevice

logger = logging.getLogger(__name__)


class UVSterilizer:
    """インラインUVステライザーの制御クラス"""

    def __init__(self, gpio_pin, mode="pump_linked", timer_on=30, timer_off=30):
        """
        Args:
            gpio_pin: GPIO番号
            mode: 制御モード（pump_linked, timer, always_on）
            timer_on: タイマーモード時のON時間（分）
            timer_off: タイマーモード時のOFF時間（分）
        """
        self.relay = OutputDevice(gpio_pin, active_high=False, initial_value=False)
        self.mode = mode
        self.timer_on = timer_on
        self.timer_off = timer_off
        self.is_on = False
        self.runtime_seconds = 0  # 累積稼働時間
        self._timer_thread = None
        self._stop_timer = threading.Event()

        logger.info(f"UVステライザー初期化: GPIO{gpio_pin}, モード={mode}")

    def on(self):
        """UV点灯"""
        if not self.is_on:
            self.relay.on()
            self.is_on = True
            self._start_runtime_counter()
            logger.info("UVステライザー: ON")

    def off(self):
        """UV消灯"""
        if self.is_on:
            self.relay.off()
            self.is_on = False
            logger.info("UVステライザー: OFF")

    def _start_runtime_counter(self):
        """稼働時間カウント開始"""
        self._runtime_start = time.time()

    def get_runtime_hours(self):
        """累積稼働時間を時間単位で取得"""
        if self.is_on:
            current_session = time.time() - self._runtime_start
            return (self.runtime_seconds + current_session) / 3600
        return self.runtime_seconds / 3600

    def update_runtime(self):
        """稼働時間を更新（OFF時に呼び出し）"""
        if hasattr(self, '_runtime_start'):
            self.runtime_seconds += time.time() - self._runtime_start

    def sync_with_pump(self, pump_is_on):
        """ポンプ連動モード: ポンプの状態に同期"""
        if self.mode != "pump_linked":
            return

        if pump_is_on:
            self.on()
        else:
            self.update_runtime()
            self.off()

    def start_timer_mode(self):
        """タイマーモード開始"""
        if self.mode != "timer":
            logger.warning("タイマーモードではありません")
            return

        self._stop_timer.clear()
        self._timer_thread = threading.Thread(target=self._timer_loop, daemon=True)
        self._timer_thread.start()
        logger.info(f"UVタイマーモード開始: {self.timer_on}分ON / {self.timer_off}分OFF")

    def _timer_loop(self):
        """タイマーループ"""
        while not self._stop_timer.is_set():
            # ON期間
            self.on()
            if self._stop_timer.wait(self.timer_on * 60):
                break
            # OFF期間
            self.update_runtime()
            self.off()
            if self._stop_timer.wait(self.timer_off * 60):
                break

    def stop_timer_mode(self):
        """タイマーモード停止"""
        self._stop_timer.set()
        self.off()
        if self._timer_thread:
            self._timer_thread.join(timeout=5)

    def get_status(self):
        """現在の状態を辞書で返す"""
        return {
            "is_on": self.is_on,
            "mode": self.mode,
            "runtime_hours": round(self.get_runtime_hours(), 2)
        }

    def cleanup(self):
        """終了処理"""
        self.stop_timer_mode()
        self.update_runtime()
        self.off()
        self.relay.close()
```

### main.py への統合

```python
# main.py に追加

from actuators.uv import UVSterilizer

# 初期化部分
uv_conf = config["actuators"]["uv_sterilizer"]
uv = UVSterilizer(
    gpio_pin=uv_conf["gpio"],
    mode=uv_conf["mode"],
    timer_on=uv_conf.get("timer_minutes_on", 30),
    timer_off=uv_conf.get("timer_minutes_off", 30)
)

# タイマーモードの場合は開始
if uv_conf["mode"] == "timer":
    uv.start_timer_mode()

# メインループ内（ポンプ連動の場合）
if uv_conf["mode"] == "pump_linked":
    uv.sync_with_pump(pump.is_on)

# 状態をMQTT送信
mqtt_client.publish("actuators/uv/status", uv.get_status())
```

### MQTTトピック

| トピック | 方向 | ペイロード例 |
|---------|------|-------------|
| `hydroponics/actuators/uv/status` | Pub | `{"is_on": true, "mode": "pump_linked", "runtime_hours": 123.5}` |
| `hydroponics/commands/uv/set` | Sub | `{"action": "on"}` or `{"action": "off"}` |

---

## Step 4: 水温監視アラート

### 閾値設定

| 温度範囲 | ステータス | アクション |
|---------|----------|-----------|
| 18-25°C | 正常（緑） | なし |
| 25-28°C | 注意（黄） | ログ記録 |
| 28°C超 | 危険（赤） | **アラート発報** |
| 15°C以下 | 低温警告（青） | アラート発報、ヒーター検討 |

### controller/alerts.py 作成

```python
"""アラート送信モジュール"""

import logging
import requests
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class AlertLevel(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertManager:
    """アラート管理クラス"""

    def __init__(self, discord_webhook=None, line_token=None):
        self.discord_webhook = discord_webhook
        self.line_token = line_token
        self.alert_history = []
        self.cooldown_minutes = 10  # 同一アラートの再送信間隔
        self._last_alerts = {}

    def send_alert(self, alert_type, message, level=AlertLevel.WARNING, value=None):
        """アラート送信"""
        # クールダウンチェック
        if self._is_in_cooldown(alert_type):
            logger.debug(f"アラート {alert_type} はクールダウン中")
            return False

        timestamp = datetime.now().isoformat()
        alert_data = {
            "type": alert_type,
            "message": message,
            "level": level.value,
            "value": value,
            "timestamp": timestamp
        }

        # 履歴に追加
        self.alert_history.append(alert_data)
        self._last_alerts[alert_type] = datetime.now()

        # Discord送信
        if self.discord_webhook:
            self._send_discord(alert_data)

        # LINE送信
        if self.line_token:
            self._send_line(alert_data)

        logger.warning(f"アラート送信: {alert_type} - {message}")
        return True

    def _is_in_cooldown(self, alert_type):
        """クールダウン中かチェック"""
        if alert_type not in self._last_alerts:
            return False
        elapsed = (datetime.now() - self._last_alerts[alert_type]).total_seconds()
        return elapsed < (self.cooldown_minutes * 60)

    def _send_discord(self, alert_data):
        """Discord Webhook送信"""
        color_map = {
            "info": 0x00FF00,      # 緑
            "warning": 0xFFFF00,   # 黄
            "critical": 0xFF0000   # 赤
        }

        embed = {
            "title": f"🌿 水耕栽培アラート: {alert_data['type']}",
            "description": alert_data["message"],
            "color": color_map.get(alert_data["level"], 0xFFFFFF),
            "fields": [
                {"name": "値", "value": str(alert_data.get("value", "N/A")), "inline": True},
                {"name": "レベル", "value": alert_data["level"], "inline": True}
            ],
            "timestamp": alert_data["timestamp"]
        }

        payload = {"embeds": [embed]}

        try:
            response = requests.post(self.discord_webhook, json=payload, timeout=10)
            response.raise_for_status()
            logger.info("Discord通知送信成功")
        except Exception as e:
            logger.error(f"Discord通知失敗: {e}")

    def _send_line(self, alert_data):
        """LINE Notify送信"""
        headers = {
            "Authorization": f"Bearer {self.line_token}"
        }
        message = f"\n🌿 {alert_data['type']}\n{alert_data['message']}\n値: {alert_data.get('value', 'N/A')}"
        payload = {"message": message}

        try:
            response = requests.post(
                "https://notify-api.line.me/api/notify",
                headers=headers,
                data=payload,
                timeout=10
            )
            response.raise_for_status()
            logger.info("LINE通知送信成功")
        except Exception as e:
            logger.error(f"LINE通知失敗: {e}")

    def check_temperature(self, temp_c):
        """水温チェックしてアラート判定"""
        if temp_c > 28:
            self.send_alert(
                "高温警告",
                f"水温が危険域です！藻の繁殖リスクが高まっています。",
                AlertLevel.CRITICAL,
                f"{temp_c:.1f}°C"
            )
        elif temp_c > 25:
            self.send_alert(
                "水温注意",
                f"水温が上昇しています。",
                AlertLevel.WARNING,
                f"{temp_c:.1f}°C"
            )
        elif temp_c < 15:
            self.send_alert(
                "低温警告",
                f"水温が低すぎます。植物の成長が遅れる可能性があります。",
                AlertLevel.WARNING,
                f"{temp_c:.1f}°C"
            )

    def get_history(self, limit=50):
        """アラート履歴取得"""
        return self.alert_history[-limit:]
```

### config.yaml 設定追加

```yaml
alerts:
  enabled: true
  cooldown_minutes: 10
  discord_webhook: "https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN"
  line_token: null  # LINE Notifyトークン（オプション）

  thresholds:
    temperature:
      normal_min: 18
      normal_max: 25
      warning_max: 28
      critical_max: 30
      low_warning: 15
```

### Discord Webhook 設定手順

1. Discordサーバーで通知用チャンネルを作成
2. チャンネル設定 → 連携サービス → ウェブフック → 新しいウェブフック
3. 名前を「水耕栽培アラート」等に設定
4. 「ウェブフックURLをコピー」
5. config.yaml の `discord_webhook` に貼り付け

### main.py への統合

```python
from alerts import AlertManager

# 初期化
alert_conf = config["alerts"]
alert_manager = AlertManager(
    discord_webhook=alert_conf.get("discord_webhook"),
    line_token=alert_conf.get("line_token")
)

# メインループ内
temp = temp_sensor.read()
if alert_conf["enabled"]:
    alert_manager.check_temperature(temp)
```

---

## Step 5: Node-REDでアラートフロー構築（オプション）

Node-REDを使用する場合の設定。Pythonで直接実装（Step 4）済みなら不要。

### フロー概要

```
[MQTT In] → [Function] → [Switch] → [HTTP Request] → [Debug]
   │            │           │              │
hydroponics/  閾値判定   レベル分岐    Discord/LINE送信
sensors/#
```

### フローJSON（インポート用）

```json
[
    {
        "id": "mqtt_alerts_in",
        "type": "mqtt in",
        "topic": "hydroponics/sensors/water_temp",
        "broker": "localhost:1883"
    },
    {
        "id": "check_temp",
        "type": "function",
        "func": "var temp = msg.payload.value;\nif (temp > 28) {\n    msg.alertLevel = 'critical';\n    msg.alertMessage = '水温危険: ' + temp + '°C';\n} else if (temp > 25) {\n    msg.alertLevel = 'warning';\n    msg.alertMessage = '水温注意: ' + temp + '°C';\n} else {\n    return null;\n}\nreturn msg;"
    },
    {
        "id": "discord_out",
        "type": "http request",
        "method": "POST",
        "url": "YOUR_DISCORD_WEBHOOK_URL"
    }
]
```

### フローのバックアップ

Node-REDの設定 → Export → Download で flows.json を保存。

---

## Step 6: 遮光チェックリスト

藻は「光 + 栄養素 + 適温の水」で繁殖する。光を完全に遮断することが最も効果的。

### 遮光確認箇所

| 箇所 | 確認項目 | 対策 | チェック |
|------|---------|------|:--------:|
| リザーバー本体 | 不透明か | 透明なら黒ビニール袋 or アルミシート | [ ] |
| リザーバーフタ | 隙間がないか | アルミテープで塞ぐ | [ ] |
| チャンネルA | プラダンフタの隙間 | アルミテープ | [ ] |
| チャンネルB | プラダンフタの隙間 | アルミテープ | [ ] |
| ネットポット周辺 | 穴の隙間 | ネオプレンディスク or アルミテープ | [ ] |
| 給水チューブ | 透明部分がないか | 黒チューブに交換 or アルミテープ巻き | [ ] |
| 排水チューブ | 透明部分がないか | 黒チューブに交換 or アルミテープ巻き | [ ] |
| 配管接続部 | 光が入る隙間 | テープで塞ぐ | [ ] |
| UVステライザー接続部 | ホース接続部の隙間 | テープで塞ぐ | [ ] |

### 確認方法

1. **暗所確認**: 夜間または部屋を暗くする
2. **ライト照射**: スマホのライトをリザーバー・チャンネルの外側から当てる
3. **内部確認**: 内部から光漏れがないか確認
4. **記録**: 発見した箇所を写真で記録し、対策後に再確認

### 遮光材料（百均で調達可能）

| 材料 | 用途 | 価格目安 |
|------|------|---------|
| アルミテープ | 隙間塞ぎ、チューブ巻き | 110円 |
| 黒ビニール袋 | 容器の遮光 | 110円 |
| 黒プラダン | チャンネルカバー | 110円 |
| アルミシート（保温用） | 大面積の遮光 | 110円 |

---

## Step 7: Grafanaにアラート履歴表示

### アラートログをInfluxDBに記録

alerts.py に追記:

```python
def log_to_influxdb(self, alert_data):
    """InfluxDBにアラートを記録"""
    payload = {
        "alert_type": alert_data["type"],
        "level": alert_data["level"],
        "value": alert_data.get("value", ""),
        "message": alert_data["message"]
    }
    # MQTTでTelegraf経由で記録
    self.mqtt_client.publish("hydroponics/alerts/log", payload)
```

### Telegraf設定追加

telegraf.conf に追記:

```toml
[[inputs.mqtt_consumer]]
  servers = ["tcp://mosquitto:1883"]
  topics = ["hydroponics/alerts/log"]
  data_format = "json"
  topic_tag = "topic"
  json_string_fields = ["alert_type", "level", "message", "value"]
```

### Grafanaダッシュボード設定

#### テーブルパネル: アラート履歴

1. Add Panel → Table
2. Query (Flux):

```flux
from(bucket: "hydroponics")
  |> range(start: -7d)
  |> filter(fn: (r) => r.topic == "hydroponics/alerts/log")
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> sort(columns: ["_time"], desc: true)
  |> limit(n: 50)
```

3. カラム設定:
   - `_time` → "発生時刻"
   - `alert_type` → "種別"
   - `level` → "レベル"（色分け設定）
   - `value` → "値"
   - `message` → "メッセージ"

4. レベル色分け:
   - `info` → 緑
   - `warning` → 黄
   - `critical` → 赤

#### Statパネル: UVランプ稼働時間

```flux
from(bucket: "hydroponics")
  |> range(start: -1h)
  |> filter(fn: (r) => r.topic == "hydroponics/actuators/uv/status")
  |> filter(fn: (r) => r._field == "runtime_hours")
  |> last()
```

表示形式: `XXX.X 時間` / 閾値: 7000時間で黄、8000時間で赤（交換推奨）

---

## 動作確認チェックリスト

### 物理設置
- [ ] UVステライザーが配管に正しく組み込まれている
- [ ] 水流方向（矢印）が正しい
- [ ] ホース接続部から漏れがない
- [ ] UV電源ケーブルが水場から離れている

### ソフトウェア制御
- [ ] UVがリレー経由でON/OFF可能（GPIO23）
- [ ] `pump_linked` モードでポンプと連動する
- [ ] `timer` モードで30分ON/30分OFFが動作する
- [ ] MQTT `hydroponics/actuators/uv/status` に状態がpublishされる
- [ ] UVランプ稼働時間がカウントされている

### アラート
- [ ] 水温25°C超で警告アラートが発報される
- [ ] 水温28°C超で危険アラートが発報される
- [ ] Discord Webhookに通知が届く
- [ ] LINE Notify に通知が届く（設定時）
- [ ] クールダウン（10分）が機能する

### 遮光
- [ ] リザーバー本体の遮光完了
- [ ] リザーバーフタの隙間対策完了
- [ ] チャンネルA/Bの遮光完了
- [ ] ネットポット周辺の隙間対策完了
- [ ] 全チューブの遮光完了
- [ ] 暗所テストで光漏れなし

### Grafana
- [ ] アラート履歴テーブルが表示される
- [ ] UVランプ稼働時間が表示される
- [ ] 水温グラフに閾値ラインが表示される

---

## トラブルシューティング

### UVが点灯しない

1. リレーの配線確認（GPIO23）
2. `gpio readall` でGPIO状態確認
3. リレーモジュールのLED確認
4. UV本体の電源確認

### アラートが送信されない

1. Discord Webhook URLの確認
2. `requests` ライブラリのインストール確認: `pip install requests`
3. ネットワーク接続確認
4. ログで `AlertManager` のエラーメッセージを確認

### 藻が発生する

1. 遮光チェックリストを再確認
2. 水温が25°C以下に保たれているか確認
3. UVステライザーが正常稼働しているか確認
4. UV ランプの寿命（8000時間）を確認
