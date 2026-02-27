"""タイマー制御スケジューラ"""

import logging
from datetime import datetime, time as dt_time, timedelta

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
            config: config.yaml の actuators.circulation_pump セクション
        """
        self.pump = pump
        self.config = config["circulation_pump"]
        self.schedule_config = self.config["schedule"]

        self.scheduler = BackgroundScheduler()
        self._paused = False
        self._is_day_mode = False
        self._toggle_job = None

        # 日中/夜間の切り替え時刻を登録
        day_start = self.schedule_config["day_start"]
        day_end = self.schedule_config["day_end"]

        self.scheduler.add_job(
            self._enter_day_mode,
            'cron',
            hour=int(day_start.split(':')[0]),
            minute=int(day_start.split(':')[1]),
            id='day_mode_start'
        )

        self.scheduler.add_job(
            self._enter_night_mode,
            'cron',
            hour=int(day_end.split(':')[0]),
            minute=int(day_end.split(':')[1]),
            id='night_mode_start'
        )

        logger.info(f"スケジューラ初期化: 日中={day_start}-{day_end}")

    def start(self) -> None:
        """スケジューラを開始する"""
        self.scheduler.start()

        # 現在の時刻に応じて初期モードを設定
        now = datetime.now().time()
        day_start = dt_time(*map(int, self.schedule_config["day_start"].split(':')))
        day_end = dt_time(*map(int, self.schedule_config["day_end"].split(':')))

        if day_start <= now < day_end:
            self._enter_day_mode()
        else:
            self._enter_night_mode()

        logger.info("スケジューラ開始")

    def _remove_toggle_job(self) -> None:
        """トグルジョブを安全に削除する（実行済みでも例外を出さない）"""
        if self._toggle_job:
            try:
                self._toggle_job.remove()
            except Exception:
                pass
            self._toggle_job = None

    def stop(self) -> None:
        """スケジューラを停止する（グレースフルシャットダウン時）"""
        self._remove_toggle_job()
        self.scheduler.shutdown()
        logger.info("スケジューラ停止")

    def pause(self) -> None:
        """一時停止（水位低下時にinterlockから呼ばれる）
        循環ポンプを即座にOFFにし、スケジュールを一時停止する。
        """
        if self._paused:
            return

        self._paused = True
        self.pump.off()
        self._remove_toggle_job()

        logger.warning("スケジューラ一時停止（水位低下）")

    def resume(self) -> None:
        """再開（水位復帰時にinterlockから呼ばれる）
        スケジュールを再開し、現在のモードに応じてポンプ制御を復帰する。
        """
        if not self._paused:
            return

        self._paused = False

        # 日中モードの場合はポンプONで再開し、トグルを再スケジュール
        if self._is_day_mode:
            self.pump.on()
            on_minutes = self.schedule_config["on_minutes"]
            next_run = datetime.now() + timedelta(minutes=on_minutes)
            self._toggle_job = self.scheduler.add_job(
                self._toggle_pump,
                'date',
                run_date=next_run,
                id='pump_toggle'
            )

        logger.info("スケジューラ再開")

    def schedule_status(self) -> dict:
        """スケジューラの現在の状態を返す（MQTT送信用）"""
        remaining_sec = -1
        if self._toggle_job is not None:
            try:
                next_run = self._toggle_job.next_run_time
                if next_run is not None:
                    now = datetime.now(tz=next_run.tzinfo)
                    delta = (next_run - now).total_seconds()
                    remaining_sec = max(0, int(delta))
            except Exception:
                remaining_sec = -1

        return {
            "remaining_sec": remaining_sec,
            "day_mode": 1 if self._is_day_mode else 0,
            "paused": 1 if self._paused else 0,
        }

    def _toggle_pump(self) -> None:
        """循環ポンプのON/OFFをトグルする"""
        if self._paused:
            return

        on_minutes = self.schedule_config["on_minutes"]
        off_minutes = self.schedule_config["off_minutes"]

        if self.pump.status():
            # 現在ON → OFFにして、off_minutes後にONする
            self.pump.off()
            next_run = datetime.now() + timedelta(minutes=off_minutes)
        else:
            # 現在OFF → ONにして、on_minutes後にOFFする
            self.pump.on()
            next_run = datetime.now() + timedelta(minutes=on_minutes)

        # 次回のトグルをスケジュール（dateトリガーは実行後に削除されるため新規登録）
        self._toggle_job = self.scheduler.add_job(
            self._toggle_pump,
            'date',
            run_date=next_run,
            id='pump_toggle'
        )

    def _enter_day_mode(self) -> None:
        """日中モードに入る（day_startの時刻に呼ばれる）
        循環ポンプのインターバル制御を開始する。
        """
        self._is_day_mode = True

        # 既存のトグルジョブがあれば削除
        self._remove_toggle_job()

        on_minutes = self.schedule_config["on_minutes"]
        off_minutes = self.schedule_config["off_minutes"]

        # ポンプONで開始
        if not self._paused:
            self.pump.on()

        # on_minutes 後に最初のトグル（OFF）をスケジュール
        next_run = datetime.now() + timedelta(minutes=on_minutes)
        self._toggle_job = self.scheduler.add_job(
            self._toggle_pump,
            'date',
            run_date=next_run,
            id='pump_toggle'
        )

        logger.info(f"日中モード開始: {on_minutes}分ON / {off_minutes}分OFF")

    def _enter_night_mode(self) -> None:
        """夜間モードに入る（day_endの時刻に呼ばれる）
        循環ポンプをOFFにする。
        """
        self._is_day_mode = False

        # トグルジョブを削除
        self._remove_toggle_job()

        # ポンプOFF
        self.pump.off()

        logger.info("夜間モード開始: ポンプOFF")
