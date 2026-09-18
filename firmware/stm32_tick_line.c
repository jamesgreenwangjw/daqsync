/* 最小行协议：每 10ms 打一行。T 必须是 HAL_GetTick()，不要用循环计数冒充。 */
#include "usart.h"
#include "adc.h"
#include <stdio.h>
#include <string.h>

static uint32_t last;

void daqsync_tick_line(void)
{
    uint32_t now = HAL_GetTick();
    if (now - last < 10) return;
    last = now;

    uint32_t adc = 0;
    HAL_ADC_Start(&hadc1);
    if (HAL_ADC_PollForConversion(&hadc1, 2) == HAL_OK)
        adc = HAL_ADC_GetValue(&hadc1);

    char line[64];
    int n = snprintf(line, sizeof line, "T=%lu,ADC=%lu\r\n",
                     (unsigned long)now, (unsigned long)adc);
    HAL_UART_Transmit(&huart1, (uint8_t *)line, n, 10);
}
