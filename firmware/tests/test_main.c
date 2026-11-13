/*
 * test_main.c - laptop tests for the Open Herd unit code.
 *
 * Runs the real app code (everything except board_stm32.c) against the fake
 * board in board_fake.c. Run with:  make -C firmware/tests
 * Add VERBOSE=1 to also print the unit's log.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "app_config.h"
#include "app_main.h"
#include "board_fake.h"
#include "herd_frame.h"
#include "herd_msg.h"
#include "link.h"
#include "pantilt.h"
#include "tracker.h"
#include "unit_fsm.h"

static int failures;
static int checks;

#define CHECK(cond)                                                    \
  do {                                                                 \
    checks++;                                                          \
    if (!(cond)) {                                                     \
      failures++;                                                      \
      printf("  FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond);         \
    }                                                                  \
  } while (0)

/* ---------- helpers ---------- */

static void run_until(uint32_t *t, uint32_t end_ms) {
  for (; *t <= end_ms; *t += 5) {
    fake_set_time(*t);
    app_loop();
  }
}

/* Index of the first sent message matching type (and event code / dst if nonzero), at or after from. */
static long find_sent(size_t from, uint8_t type, uint8_t event_code, uint8_t dst) {
  for (size_t i = from; i < fake_sent_count(); i++) {
    const herd_msg_t *m = &fake_sent(i)->msg;
    if (m->type != type) continue;
    if (event_code && m->u.event.code != event_code) continue;
    if (dst && m->dst != dst) continue;
    return (long)i;
  }
  return -1;
}

static size_t count_sent(uint8_t type, uint16_t seq) {
  size_t n = 0;
  for (size_t i = 0; i < fake_sent_count(); i++) {
    const herd_msg_t *m = &fake_sent(i)->msg;
    if (m->type == type && (seq == 0 || m->seq == seq)) n++;
  }
  return n;
}

static herd_msg_t make_msg(uint8_t type, uint8_t src, uint8_t dst, uint16_t seq) {
  herd_msg_t m;
  memset(&m, 0, sizeof(m));
  m.type = type;
  m.src = src;
  m.dst = dst;
  m.seq = seq;
  return m;
}

static void start_app(void) {
  fake_reset();
  fake_set_time(0);
  app_init();
}

/* ---------- message format ---------- */

static void test_msg_roundtrip(void) {
  printf("message format: pack and unpack every type\n");
  herd_msg_t in[6];
  memset(in, 0, sizeof(in));
  in[0] = make_msg(HERD_MSG_STATUS, 1, HERD_ID_BROADCAST, 7);
  in[0].u.status = (herd_status_t){2, 3, -45, 12};
  in[1] = make_msg(HERD_MSG_EVENT, 1, HERD_ID_STATION, 8);
  in[1].u.event = (herd_event_t){HERD_EVENT_LINGERING, 513};
  in[2] = make_msg(HERD_MSG_HEADING, 1, 2, 65535);
  in[2].u.heading = (herd_heading_t){42, HERD_SIDE_RIGHT, -17};
  in[3] = make_msg(HERD_MSG_TAKEN_OVER, 2, 1, 1);
  in[3].u.track.track_id = 42;
  in[4] = make_msg(HERD_MSG_LOST, 2, HERD_ID_STATION, 2);
  in[4].u.track.track_id = 9;
  in[5] = make_msg(HERD_MSG_ACK, 2, 1, 3);
  in[5].u.ack = (herd_ack_t){65535, HERD_MSG_HEADING};

  for (int i = 0; i < 6; i++) {
    in[i].time_ms = 123456789u + (uint32_t)i;
    uint8_t buf[HERD_MSG_MAX_LEN];
    size_t n = herd_msg_encode(&in[i], buf, sizeof(buf));
    CHECK(n > 0);
    herd_msg_t out;
    CHECK(herd_msg_decode(buf, n, &out));
    CHECK(memcmp(&in[i], &out, sizeof(out)) == 0);
    CHECK(!herd_msg_decode(buf, n - 1, &out)); /* cut short */
    buf[0] = 99;
    CHECK(!herd_msg_decode(buf, n, &out)); /* wrong version */
  }

  herd_msg_t bad = make_msg(77, 1, 2, 1);
  uint8_t buf[HERD_MSG_MAX_LEN];
  CHECK(herd_msg_encode(&bad, buf, sizeof(buf)) == 0); /* unknown type */
  CHECK(herd_msg_encode(&in[2], buf, 5) == 0);         /* doesn't fit */
}

/* ---------- serial framing ---------- */

static void test_framing(void) {
  printf("framing: survives garbage, split delivery and corruption\n");
  herd_msg_t m = make_msg(HERD_MSG_HEADING, 1, 2, 5);
  m.u.heading = (herd_heading_t){3, HERD_SIDE_LEFT, 10};
  uint8_t raw[HERD_MSG_MAX_LEN], frame[HERD_FRAME_MAX_LEN];
  size_t n = herd_msg_encode(&m, raw, sizeof(raw));
  size_t f = herd_frame_encode(raw, n, frame, sizeof(frame));
  CHECK(f == n + HERD_FRAME_OVERHEAD);

  herd_frame_parser_t p;
  herd_frame_parser_init(&p);
  uint8_t out[HERD_MSG_MAX_LEN];
  const uint8_t junk[] = {0x00, 0xA5, 0xA5, 0x13, 0xFF};
  size_t got = 0;
  for (size_t i = 0; i < sizeof(junk); i++) got += herd_frame_parser_feed(&p, junk[i], out, sizeof(out));
  CHECK(got == 0);

  /* Two frames back to back after the junk. */
  int frames = 0;
  for (int rep = 0; rep < 2; rep++) {
    for (size_t i = 0; i < f; i++) {
      size_t r = herd_frame_parser_feed(&p, frame[i], out, sizeof(out));
      if (r) {
        frames++;
        CHECK(r == n && memcmp(out, raw, n) == 0);
      }
    }
  }
  CHECK(frames == 2);

  /* One flipped bit: thrown away and counted. */
  uint32_t bad_before = p.bad_frames;
  frame[6] ^= 0x10;
  got = 0;
  for (size_t i = 0; i < f; i++) got += herd_frame_parser_feed(&p, frame[i], out, sizeof(out));
  CHECK(got == 0);
  CHECK(p.bad_frames == bad_before + 1);
}

/* ---------- servos ---------- */

static void test_pantilt(void) {
  printf("pan/tilt: pulse widths, speed limit and turn limits\n");
  fake_reset();
  CHECK(pantilt_angle_to_us(0) == (SERVO_MIN_US + SERVO_MAX_US) / 2);
  CHECK(pantilt_angle_to_us(900) == SERVO_MAX_US);
  CHECK(pantilt_angle_to_us(-900) == SERVO_MIN_US);
  CHECK(pantilt_angle_to_us(5000) == SERVO_MAX_US);

  pantilt_init();
  uint32_t t = 0;
  pantilt_update(t);
  int32_t max_seen = 0;
  for (int i = 0; i < 300; i++) { /* box stuck at the right edge for 3 s */
    pantilt_follow(950, 500);
    t += 10;
    int32_t before = pantilt_pan_x10();
    pantilt_update(t);
    int32_t step = pantilt_pan_x10() - before;
    CHECK(step <= SERVO_MAX_SPEED_DPS * 10 * 10 / 1000); /* speed limit */
    if (pantilt_pan_x10() > max_seen) max_seen = pantilt_pan_x10();
  }
  CHECK(max_seen == PAN_MAX_DEG * 10); /* stops at the limit */
  CHECK(pantilt_at_limit(HERD_SIDE_RIGHT));
  CHECK(!pantilt_at_limit(HERD_SIDE_LEFT));
  CHECK(fake_servo_us(BOARD_SERVO_PAN) == pantilt_angle_to_us(PAN_MAX_DEG * 10));
}

/* ---------- whole unit, fake person, nobody answers ---------- */

static void test_scenario_no_neighbor_answer(void) {
  printf("scenario: person lingers, walks off right, neighbor never answers\n");
  start_app();
  uint32_t t = 0;
  run_until(&t, 17000);
  CHECK(fsm_state() == UNIT_TRACKING);
  CHECK(pantilt_tilt_x10() > -60 && pantilt_tilt_x10() < 0); /* aimed at the person (-3 deg), not drifting */
  run_until(&t, 35000);

  CHECK(find_sent(0, HERD_MSG_EVENT, HERD_EVENT_BOOT, HERD_ID_STATION) == 0);

  long ling = find_sent(0, HERD_MSG_EVENT, HERD_EVENT_LINGERING, HERD_ID_STATION);
  CHECK(ling >= 0);
  if (ling >= 0) {
    uint32_t at = fake_sent((size_t)ling)->at_ms;
    printf("  lingering flagged at %.1f s\n", at / 1000.0);
    CHECK(at >= 13000 && at <= 16000); /* stands from 6 s, LINGER_TIME_MS = 8 s */
  }

  long head = find_sent(0, HERD_MSG_HEADING, 0, NEIGHBOR_RIGHT_ID);
  CHECK(head > ling);
  if (head >= 0) {
    const fake_sent_t *h = fake_sent((size_t)head);
    printf("  \"heading your way\" sent at %.1f s, speed %d deg/s\n", h->at_ms / 1000.0, h->msg.u.heading.speed_dps);
    CHECK(h->at_ms >= 26000 && h->at_ms <= 31000);
    CHECK(h->msg.u.heading.exit_side == HERD_SIDE_RIGHT);
    CHECK(h->msg.u.heading.speed_dps >= 5 && h->msg.u.heading.speed_dps <= 15); /* walks at 10 deg/s */
    CHECK(count_sent(HERD_MSG_HEADING, h->msg.seq) == 1 + ACK_MAX_RETRIES); /* first try + resends */
  }
  CHECK(find_sent(0, HERD_MSG_EVENT, HERD_EVENT_HANDOFF_FAILED, HERD_ID_STATION) > head);
  CHECK(find_sent((size_t)(head < 0 ? 0 : head), HERD_MSG_LOST, 0, HERD_ID_STATION) > head);
  CHECK(fsm_state() == UNIT_WATCHING);
  CHECK(pantilt_pan_x10() == 0); /* back home */

  size_t statuses = count_sent(HERD_MSG_STATUS, 0);
  CHECK(statuses >= 34 && statuses <= 36); /* one a second */
  CHECK(fake_led_toggles() >= 69);
  CHECK(link_stats()->failed == 1);
}

/* ---------- whole unit, neighbor answers ---------- */

static void test_scenario_handoff_ok(void) {
  printf("scenario: neighbor ACKs and takes over\n");
  start_app();
  uint32_t t = 0;
  long head = -1;
  while (t < 32000 && head < 0) {
    fake_set_time(t);
    app_loop();
    head = find_sent(0, HERD_MSG_HEADING, 0, NEIGHBOR_RIGHT_ID);
    t += 5;
  }
  CHECK(head >= 0);
  if (head < 0) return;
  const herd_msg_t heading = fake_sent((size_t)head)->msg;
  CHECK(fsm_state() == UNIT_HANDING_OFF);

  herd_msg_t ack = make_msg(HERD_MSG_ACK, NEIGHBOR_RIGHT_ID, UNIT_ID, 100);
  ack.u.ack = (herd_ack_t){heading.seq, HERD_MSG_HEADING};
  fake_inject(&ack);
  run_until(&t, t + 500);
  CHECK(count_sent(HERD_MSG_HEADING, heading.seq) == 1); /* ACKed, so no resends */
  CHECK(fsm_state() == UNIT_HANDING_OFF);

  herd_msg_t taken = make_msg(HERD_MSG_TAKEN_OVER, NEIGHBOR_RIGHT_ID, UNIT_ID, 101);
  taken.u.track.track_id = heading.u.heading.track_id;
  fake_inject(&taken);
  fake_inject(&taken); /* a repeat, as if our ACK was lost */
  size_t before = fake_sent_count();
  run_until(&t, t + 100);

  CHECK(fsm_state() == UNIT_WATCHING);
  CHECK(find_sent(before, HERD_MSG_EVENT, HERD_EVENT_HANDOFF_DONE, HERD_ID_STATION) >= 0);
  long a1 = find_sent(before, HERD_MSG_ACK, 0, NEIGHBOR_RIGHT_ID);
  long a2 = a1 >= 0 ? find_sent((size_t)a1 + 1, HERD_MSG_ACK, 0, NEIGHBOR_RIGHT_ID) : -1;
  CHECK(a1 >= 0 && a2 > a1); /* both copies answered */
  if (a1 >= 0) CHECK(fake_sent((size_t)a1)->msg.u.ack.acked_seq == 101);
  CHECK(link_stats()->failed == 0);
  CHECK(link_stats()->received == 1); /* the repeat wasn't delivered twice */
}

/* ---------- this unit picks up a neighbor's person ---------- */

static void test_expecting_pickup(void) {
  printf("receiving side: neighbor warns, person appears, TAKEN_OVER sent\n");
  fake_reset();
  tracker_init();
  pantilt_init();
  link_init(UNIT_ID, fsm_on_message, fsm_on_send_failed);
  fsm_init();

  herd_msg_t heading = make_msg(HERD_MSG_HEADING, NEIGHBOR_RIGHT_ID, UNIT_ID, 40);
  heading.u.heading = (herd_heading_t){77, HERD_SIDE_LEFT, -10};
  fake_inject(&heading);
  fake_set_time(1000);
  link_poll(1000);
  CHECK(fsm_state() == UNIT_EXPECTING);
  CHECK(find_sent(0, HERD_MSG_ACK, 0, NEIGHBOR_RIGHT_ID) >= 0);

  frame_t f;
  memset(&f, 0, sizeof(f));
  f.time_ms = 1500;
  f.count = 1;
  f.det[0] = (detection_t){900, 500, 120, 400, 80};
  fake_set_time(1500);
  tracker_update(&f);
  fsm_on_frame(0, 1500);

  CHECK(fsm_state() == UNIT_TRACKING);
  long taken = find_sent(0, HERD_MSG_TAKEN_OVER, 0, NEIGHBOR_RIGHT_ID);
  CHECK(taken >= 0);
  if (taken >= 0) CHECK(fake_sent((size_t)taken)->msg.u.track.track_id == 77);
}

static void test_expecting_timeout(void) {
  printf("receiving side: nobody shows up, LOST after the timeout\n");
  fake_reset();
  tracker_init();
  pantilt_init();
  link_init(UNIT_ID, fsm_on_message, fsm_on_send_failed);
  fsm_init();

  herd_msg_t heading = make_msg(HERD_MSG_HEADING, NEIGHBOR_RIGHT_ID, UNIT_ID, 41);
  heading.u.heading = (herd_heading_t){78, HERD_SIDE_LEFT, -10};
  fake_inject(&heading);
  fake_set_time(1000);
  link_poll(1000);
  CHECK(fsm_state() == UNIT_EXPECTING);
  fsm_tick(1000 + EXPECT_TIMEOUT_MS - 1);
  CHECK(fsm_state() == UNIT_EXPECTING);
  fsm_tick(1000 + EXPECT_TIMEOUT_MS);
  CHECK(fsm_state() == UNIT_WATCHING);
  long lost = find_sent(0, HERD_MSG_LOST, 0, HERD_ID_STATION);
  CHECK(lost >= 0);
  if (lost >= 0) CHECK(fake_sent((size_t)lost)->msg.u.track.track_id == 78);

  /* A stranger's HEADING is ignored. */
  herd_msg_t stranger = make_msg(HERD_MSG_HEADING, 9, UNIT_ID, 1);
  fake_inject(&stranger);
  link_poll(6000);
  CHECK(fsm_state() == UNIT_WATCHING);

  /* Garbage on the wire is counted, not crashed on. */
  const uint8_t junk[] = {0xA5, 0x5A, 0x03, 0x01, 0x02, 0x03, 0x00, 0x00};
  fake_inject_bytes(junk, sizeof(junk));
  uint32_t bad = link_stats()->bad_frames;
  link_poll(6001);
  CHECK(link_stats()->bad_frames == bad + 1);
}

int main(int argc, char **argv) {
  (void)argv;
  fake_set_echo_log(argc > 1 || getenv("VERBOSE") != NULL);
  test_msg_roundtrip();
  test_framing();
  test_pantilt();
  test_scenario_no_neighbor_answer();
  test_scenario_handoff_ok();
  test_expecting_pickup();
  test_expecting_timeout();
  printf("\n%d checks, %d failed\n", checks, failures);
  return failures == 0 ? 0 : 1;
}
