"""The camera aiming law, mirrored from firmware/stm32/App/pantilt.c (angles in tenths of a degree,
integer arithmetic that truncates like C)."""

from herd_ai.pantilt import LEFT, RIGHT, PanTilt


def test_pulse_widths_match_the_firmware():
    pt = PanTilt()
    assert pt.angle_to_us(0) == 1500
    assert pt.angle_to_us(900) == 2000
    assert pt.angle_to_us(-900) == 1000
    assert pt.angle_to_us(5000) == 2000
    assert pt.angle_to_us(-334) == 1315  # -334000/1800 = -185.56: C truncates to -185 (Python floor would give 1314)


def test_follow_moves_a_fraction_of_the_error_toward_the_box():
    pt = PanTilt(hfov_deg=60, vfov_deg=45, follow_gain_pct=30)
    pt.update(0)
    pt.follow(750, 500)  # 25 % of the frame right of center = 15 deg
    assert pt.pan_target_x10 == 150 * 30 // 100  # 45 -> 4.5 deg
    pt.follow(500, 250)  # above center: positive tilt (look up)
    assert pt.tilt_target_x10 == (250 * 45 * 10 // 1000) * 30 // 100


def test_speed_limit_and_turn_limit_like_the_c_test():
    pt = PanTilt(max_speed_dps=120, pan_max_deg=80)
    pt.update(0)
    max_seen = 0
    t = 0
    for _ in range(300):  # box stuck at the right edge for 3 s
        pt.follow(950, 500)
        t += 10
        before = pt.pan_x10
        pt.update(t)
        assert pt.pan_x10 - before <= 120 * 10 * 10 // 1000
        max_seen = max(max_seen, pt.pan_x10)
    assert max_seen == 800
    assert pt.at_limit(RIGHT) and not pt.at_limit(LEFT)
    assert pt.servo_us[0] == pt.angle_to_us(800)


def test_update_keeps_the_remainder_when_not_enough_time_passed():
    pt = PanTilt(max_speed_dps=10)
    pt.update(0)
    pt.follow(1000, 500)
    assert pt.update(3) is False  # 10 dps * 3 ms = 0.3 tenths: no move yet, clock not advanced
    assert pt.update(10) is True   # 10 ms since the last move -> 10 tenths


def test_look_toward_and_home():
    pt = PanTilt(expect_pan_deg=60)
    pt.look_toward(LEFT)
    assert pt.pan_target_x10 == -600 and pt.tilt_target_x10 == 0
    pt.home()
    assert pt.pan_target_x10 == 0


def test_deadband_ignores_small_errors():
    pt = PanTilt(follow_deadband=50)
    pt.update(0)
    pt.follow(540, 470)  # 40 and 30 thousandths off center: inside the band
    assert pt.pan_target_x10 == 0 and pt.tilt_target_x10 == 0
    pt.follow(560, 500)
    assert pt.pan_target_x10 > 0
