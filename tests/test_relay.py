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
