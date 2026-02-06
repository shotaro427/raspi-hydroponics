# raspi-hydroponics

Raspberry Pi 4 Model B を使った家庭用ハーブ水耕栽培の自動化システム。

## プロジェクト概要
- **目的**: 水耕栽培の水循環・藻防止・水質監視を自動化
- **方式**: NFT（薄膜水耕法）
- **設置場所**: 寝室の窓際、3段金網ラック（ダイソーメタルラック）
- **材料方針**: ラズパイ・センサー・ポンプ以外は百均（ダイソー等）で調達
- **開発方針**: フルスクラッチで開発する（Mycodo等の既存OSSは利用しない）

## アーキテクチャ
Raspberry Pi 4 Model B 1台で全機能を担当:
- **制御デーモン（Python）**: センサー読取 + ポンプ制御 + MQTT送信
- **Docker Compose**: Mosquitto + InfluxDB + Grafana（同一マシン上）
- 通信: MQTT（localhost:1883）。Dockerサービス停止時もPythonデーモンはローカルフォールバックで動作
- 将来、2台構成に分離する場合はMQTT通信で分けるだけ

## ディレクトリ構成
```
raspi-hydroponics/
├── CLAUDE.md
├── docs/
│   ├── SYSTEM_DESIGN.md
│   ├── CODING_STANDARDS.md
│   ├── BOM.md
│   ├── DAISO_MATERIALS.md
│   ├── RACK_SETUP.md
│   ├── diagrams/              # SVG設計図
│   └── REFERENCES.md
├── controller/                # センサー読取・ポンプ制御（Python）
│   ├── main.py
│   ├── sensors/               # ph, ec, temperature, water_level
│   ├── actuators/             # pump, dosing, uv, air_pump
│   ├── mqtt_client.py
│   ├── safety.py
│   └── config.yaml
├── server/                    # Docker Compose（Mosquitto + InfluxDB + Grafana）
│   ├── docker-compose.yml
│   ├── mosquitto/
│   ├── grafana/
│   └── nodered/
├── scripts/
│   └── setup.sh                # セットアップスクリプト
└── tests/
    ├── test_sensors.py
    └── test_mqtt.py
```

## ドキュメント索引
| ドキュメント | 内容 | 参照タイミング |
|-------------|------|---------------|
| [docs/SYSTEM_DESIGN.md](./docs/SYSTEM_DESIGN.md) | システム全体設計・安全ルール・技術スタック・ロードマップ | アーキテクチャ理解、実装方針確認 |
| [docs/CODING_STANDARDS.md](./docs/CODING_STANDARDS.md) | コーディング規約・MQTT規約 | コード実装時 |
| [docs/BOM.md](./docs/BOM.md) | 全材料一覧・部品表（百均・Amazon・電子部品） | 材料調達・予算確認時 |
| [docs/DAISO_MATERIALS.md](./docs/DAISO_MATERIALS.md) | 百均材料リスト・DIY手順 | 材料調達・物理構造製作時 |
| [docs/RACK_SETUP.md](./docs/RACK_SETUP.md) | 3段ラック設置図・組立手順・配線図 | 設置・組立時 |
| [docs/PHASE1_PLAN.md](./docs/PHASE1_PLAN.md) | フェーズ1実行計画（DS18B20→Grafana表示） | フェーズ1着手時 |
| [docs/diagrams/](./docs/diagrams/) | SVG設計図（配置図・配線図・配管図） | 物理設計・配線確認時 |
| [docs/REFERENCES.md](./docs/REFERENCES.md) | 先行事例・参考リンク集 | 調査・比較検討時 |

## 開発フロー
1. ドキュメントは `docs/` 配下に
2. 実装は Phase 順に進める（SYSTEM_DESIGN.md のロードマップ参照）
3. センサー追加時は `controller/sensors/` に新ファイル、config.yaml にピン定義を追加
4. テストは `tests/` に配置
5. 安全設計ルールは絶対に守ること。詳細は docs/SYSTEM_DESIGN.md を参照。
