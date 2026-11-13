/*
 * app_main.h - the two calls main.c needs.
 *
 * In CubeMX's main.c:
 * - after USER CODE BEGIN Includes, add: #include "app_main.h"
 * - after USER CODE BEGIN 2, add: app_init();
 * - after USER CODE BEGIN 3 (inside while (1)), add: app_loop();
 */
#ifndef APP_MAIN_H
#define APP_MAIN_H

void app_init(void);
void app_loop(void);

#endif /* APP_MAIN_H */
