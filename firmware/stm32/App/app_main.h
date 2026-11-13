/*
 * app_main.h - the two calls main.c needs.
 *
 * In CubeMX's main.c:
 *   USER CODE BEGIN Includes   ->  #include "app_main.h"
 *   USER CODE BEGIN 2          ->  app_init();
 *   USER CODE BEGIN 3          ->  app_loop();   (inside while (1))
 */
#ifndef APP_MAIN_H
#define APP_MAIN_H

void app_init(void);
void app_loop(void);

#endif /* APP_MAIN_H */
