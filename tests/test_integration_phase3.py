#!/usr/bin/env python3
"""Phase 3 統合テスト

実際にポンプを動かして水が流れることを確認する。
※ 配管・水を用意してから実行すること
"""

import sys
import time
from pathlib import Path

# controllerディレクトリをモジュール検索パスに追加
controller_dir = Path(__file__).parent.parent / "controller"
sys.path.insert(0, str(controller_dir))

from actuators.pump import CirculationPump

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
