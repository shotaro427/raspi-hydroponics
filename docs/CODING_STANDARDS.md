# コーディング規約・通信規約

## 1. コーディング規約

### Python スタイル

- PEP 8 準拠
- 型ヒント必須
- docstring は Google スタイル

### ログ

- `logging` モジュール使用（print禁止）

### GPIO

- ピン番号は `config.yaml` で一元管理、ハードコード禁止

### バリデーション

- センサー読取値は必ずバリデーション（異常値フィルタ）

## 2. MQTTトピック規約

### トピック構成

```
hydroponics/
├── sensors/{sensor_name}      # センサーデータ（JSON）
├── actuators/{name}/status    # アクチュエーター状態
├── alerts/{alert_type}        # アラート
└── commands/{target}          # 制御コマンド
```

### ペイロード形式

- ペイロードは全てJSON形式

### タイムスタンプ

- ISO 8601 形式
