"""The camera aiming law, a mirror of firmware/stm32/App/pantilt.c.

Angles are tenths of a degree. `follow(x, y)` moves the target a fraction (follow_gain_pct) of the
aiming error toward a box center given in thousandths of the frame; `update(now_ms)` steps the
servos toward the target no faster than max_speed_dps. Integer arithmetic truncates toward zero the
way C does, so the numbers here are the numbers the board will produce.

`follow_deadband` (thousandths, default 0 = the firmware as merged) is the week 9 addition under
test: errors inside the band are ignored so box jitter does not twitch the servos.
"""

from __future__ import annotations

LEFT, RIGHT = 0, 1
LIMIT_SLACK_X10 = 10


def _tdiv(a: int, b: int) -> int:
    """C integer division: truncates toward zero."""
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b > 0) else -q


def _clamp(v: int, lo: int, hi: int) -> int:
    return lo if v < lo else hi if v > hi else v


class PanTilt:
    def __init__(self, hfov_deg: int = 60, vfov_deg: int = 45, pan_min_deg: int = -80, pan_max_deg: int = 80,
                 tilt_min_deg: int = -30, tilt_max_deg: int = 30, follow_gain_pct: int = 30, max_speed_dps: int = 120,
                 expect_pan_deg: int = 60, servo_min_us: int = 1000, servo_max_us: int = 2000, follow_deadband: int = 0,
                 pan_reversed: bool = False, tilt_reversed: bool = False):
        self.hfov_deg, self.vfov_deg = int(hfov_deg), int(vfov_deg)
        self.pan_min_x10, self.pan_max_x10 = int(pan_min_deg) * 10, int(pan_max_deg) * 10
        self.tilt_min_x10, self.tilt_max_x10 = int(tilt_min_deg) * 10, int(tilt_max_deg) * 10
        self.follow_gain_pct, self.max_speed_dps = int(follow_gain_pct), int(max_speed_dps)
        self.expect_pan_deg = int(expect_pan_deg)
        self.servo_min_us, self.servo_max_us = int(servo_min_us), int(servo_max_us)
        self.follow_deadband = int(follow_deadband)
        self.pan_reversed, self.tilt_reversed = pan_reversed, tilt_reversed
        self.pan_x10 = self.tilt_x10 = 0
        self.pan_target_x10 = self.tilt_target_x10 = 0
        self.started = False
        self.last_update_ms = 0
        self.servo_us = [0, 0]
        self._write_servos()

    # --- pantilt.c, function by function ---
    def angle_to_us(self, angle_x10: int) -> int:
        mid = (self.servo_min_us + self.servo_max_us) // 2
        span = self.servo_max_us - self.servo_min_us
        return _clamp(mid + _tdiv(int(angle_x10) * span, 1800), self.servo_min_us, self.servo_max_us)

    def _write_servos(self) -> None:
        pan = -self.pan_x10 if self.pan_reversed else self.pan_x10
        tilt = -self.tilt_x10 if self.tilt_reversed else self.tilt_x10
        self.servo_us = [self.angle_to_us(pan), self.angle_to_us(tilt)]

    def home(self) -> None:
        self.pan_target_x10 = self.tilt_target_x10 = 0

    def follow(self, x: int, y: int) -> None:
        ex, ey = int(x) - 500, 500 - int(y)  # up is positive
        if abs(ex) <= self.follow_deadband:
            ex = 0
        if abs(ey) <= self.follow_deadband:
            ey = 0
        err_pan = _tdiv(ex * self.hfov_deg * 10, 1000)
        err_tilt = _tdiv(ey * self.vfov_deg * 10, 1000)
        self.pan_target_x10 = _clamp(self.pan_x10 + _tdiv(err_pan * self.follow_gain_pct, 100), self.pan_min_x10, self.pan_max_x10)
        self.tilt_target_x10 = _clamp(self.tilt_x10 + _tdiv(err_tilt * self.follow_gain_pct, 100), self.tilt_min_x10, self.tilt_max_x10)

    def look_toward(self, side: int) -> None:
        self.pan_target_x10 = self.expect_pan_deg * 10 if side == RIGHT else -self.expect_pan_deg * 10
        self.tilt_target_x10 = 0

    def at_limit(self, side: int) -> bool:
        if side == RIGHT:
            return self.pan_x10 >= self.pan_max_x10 - LIMIT_SLACK_X10
        return self.pan_x10 <= self.pan_min_x10 + LIMIT_SLACK_X10

    @staticmethod
    def _step_toward(now: int, target: int, max_step: int) -> int:
        if target > now:
            return now + max_step if target - now > max_step else target
        return now - max_step if now - target > max_step else target

    def update(self, now_ms: int) -> bool:
        """Move the servos a speed-limited step toward the target. Returns True if they moved."""
        now_ms = int(now_ms)
        if not self.started:
            self.started = True
            self.last_update_ms = now_ms
            return False
        dt = now_ms - self.last_update_ms
        max_step = (self.max_speed_dps * 10 * dt) // 1000
        if max_step == 0:
            return False  # not enough time passed to move; keep the remainder
        self.last_update_ms = now_ms
        new_pan = self._step_toward(self.pan_x10, self.pan_target_x10, max_step)
        new_tilt = self._step_toward(self.tilt_x10, self.tilt_target_x10, max_step)
        if new_pan == self.pan_x10 and new_tilt == self.tilt_x10:
            return False
        self.pan_x10, self.tilt_x10 = new_pan, new_tilt
        self._write_servos()
        return True
