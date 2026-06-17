#ifndef __MODBUS_ADAPTER_STM32G4_H
#define __MODBUS_ADAPTER_STM32G4_H

#include <stdint.h>

/* Khởi tạo bộ đệm vòng và bật chế độ nhận UART DMA */
void Modbus_Init(void);

/* Vòng lặp xử lý Modbus chính (gọi trong while(1)) */
void Modbus_Process(void);

#endif /* __MODBUS_ADAPTER_STM32G4_H */
