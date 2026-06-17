#include "modbus_adapter_stm32g4.h"
#include "stm32g4xx_hal.h"
#include "agile_modbus.h"
#include "agile_modbus_slave_util.h"
#include "ringbuffer.h"
#include <string.h>
#include <stdio.h>

extern UART_HandleTypeDef huart1;
extern UART_HandleTypeDef huart3;

#define RX_DMA_BUF_SIZE 256
#define MODBUS_RING_BUF_SIZE 512

/* ------------------ Slave 1 (USART3, ID = 1) Variables ------------------ */
uint8_t usart3_rx_dma_buf[RX_DMA_BUF_SIZE];
uint8_t usart3_ring_buf_data[MODBUS_RING_BUF_SIZE];
struct rt_ringbuffer usart3_rb;

uint16_t holding_registers_s1[10] = {
    0x1111, 0x2222, 0x3333, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000
};
uint8_t coils_s1[8] = {0x01, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00};
uint8_t discrete_inputs_s1[8] = {0x01, 0x01, 0x00, 0x00, 0x01, 0x01, 0x00, 0x01};
uint16_t input_registers_s1[8] = {0x0123, 0x4567, 0x89AB, 0xCDEF, 0x0000, 0x0000, 0x0000, 0x0000};

agile_modbus_rtu_t ctx_usart3;
uint8_t usart3_tx_buf[260];
uint8_t usart3_rx_processing_buf[260];

/* ------------------ Slave 2 (USART1, ID = 2) Variables ------------------ */
uint8_t usart1_rx_dma_buf[RX_DMA_BUF_SIZE];
uint8_t usart1_ring_buf_data[MODBUS_RING_BUF_SIZE];
struct rt_ringbuffer usart1_rb;

uint16_t holding_registers_s2[10] = {
    0x5555, 0x6666, 0x7777, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000
};
uint8_t coils_s2[8] = {0x00, 0x01, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00};
uint8_t discrete_inputs_s2[8] = {0x00, 0x00, 0x01, 0x01, 0x00, 0x00, 0x01, 0x01};
uint16_t input_registers_s2[8] = {0xFEFD, 0xFCFB, 0xFAF9, 0xF8F7, 0x0000, 0x0000, 0x0000, 0x0000};

agile_modbus_rtu_t ctx_usart1;
uint8_t usart1_tx_buf[260];
uint8_t usart1_rx_processing_buf[260];

/* ======================================================================== */
/* ======================== Callbacks for Slave 1 ========================= */
/* ======================================================================== */
static int read_holding_cb_s1(void *buf, int bufsz)
{
    uint16_t *reg_buf = (uint16_t *)buf;
    for (int i = 0; i < 10; i++) {
        reg_buf[i] = holding_registers_s1[i];
    }
    return 0;
}

static int write_holding_cb_s1(int index, int len, void *buf, int bufsz)
{
    uint16_t *reg_buf = (uint16_t *)buf;
    printf("[Slave 1] write_holding_cb index=%d len=%d\r\n", index, len);
    for (int i = 0; i < len; i++) {
        int reg_addr = index + i;
        if (reg_addr < 10) {
            uint16_t raw_val = reg_buf[i];
            printf("  -> reg[%d] val=0x%04X\r\n", reg_addr, raw_val);
            holding_registers_s1[reg_addr] = raw_val;
            if (reg_addr == 3) {
                printf("  -> Toggle LED PB7 from Slave 1\r\n");
                HAL_GPIO_TogglePin(GPIOB, GPIO_PIN_7);
            }
        }
    }
    return 0;
}

static int read_coils_cb_s1(void *buf, int bufsz)
{
    uint8_t *bit_buf = (uint8_t *)buf;
    for (int i = 0; i < 8; i++) {
        bit_buf[i] = coils_s1[i];
    }
    return 0;
}

static int write_coils_cb_s1(int index, int len, void *buf, int bufsz)
{
    uint8_t *bit_buf = (uint8_t *)buf;
    printf("[Slave 1] write_coils_cb index=%d len=%d\r\n", index, len);
    for (int i = 0; i < len; i++) {
        int addr = index + i;
        if (addr < 8) {
            coils_s1[addr] = bit_buf[i];
            printf("  -> coil[%d] = %d\r\n", addr, coils_s1[addr]);
            if (addr == 0) {
                printf("  -> LED PB7: %s\r\n", coils_s1[0] ? "ON" : "OFF");
                HAL_GPIO_WritePin(GPIOB, GPIO_PIN_7, coils_s1[0] ? GPIO_PIN_SET : GPIO_PIN_RESET);
            }
        }
    }
    return 0;
}

static int read_discrete_inputs_cb_s1(void *buf, int bufsz)
{
    uint8_t *bit_buf = (uint8_t *)buf;
    for (int i = 0; i < 8; i++) {
        bit_buf[i] = discrete_inputs_s1[i];
    }
    return 0;
}

static int read_input_registers_cb_s1(void *buf, int bufsz)
{
    uint16_t *reg_buf = (uint16_t *)buf;
    for (int i = 0; i < 8; i++) {
        reg_buf[i] = input_registers_s1[i];
    }
    return 0;
}

/* ======================================================================== */
/* ======================== Callbacks for Slave 2 ========================= */
/* ======================================================================== */
static int read_holding_cb_s2(void *buf, int bufsz)
{
    uint16_t *reg_buf = (uint16_t *)buf;
    for (int i = 0; i < 10; i++) {
        reg_buf[i] = holding_registers_s2[i];
    }
    return 0;
}

static int write_holding_cb_s2(int index, int len, void *buf, int bufsz)
{
    uint16_t *reg_buf = (uint16_t *)buf;
    printf("[Slave 2] write_holding_cb index=%d len=%d\r\n", index, len);
    for (int i = 0; i < len; i++) {
        int reg_addr = index + i;
        if (reg_addr < 10) {
            uint16_t raw_val = reg_buf[i];
            printf("  -> reg[%d] val=0x%04X\r\n", reg_addr, raw_val);
            holding_registers_s2[reg_addr] = raw_val;
            if (reg_addr == 3) {
                printf("  -> Toggle LED PB7 from Slave 2\r\n");
                HAL_GPIO_TogglePin(GPIOB, GPIO_PIN_7);
            }
        }
    }
    return 0;
}

static int read_coils_cb_s2(void *buf, int bufsz)
{
    uint8_t *bit_buf = (uint8_t *)buf;
    for (int i = 0; i < 8; i++) {
        bit_buf[i] = coils_s2[i];
    }
    return 0;
}

static int write_coils_cb_s2(int index, int len, void *buf, int bufsz)
{
    uint8_t *bit_buf = (uint8_t *)buf;
    printf("[Slave 2] write_coils_cb index=%d len=%d\r\n", index, len);
    for (int i = 0; i < len; i++) {
        int addr = index + i;
        if (addr < 8) {
            coils_s2[addr] = bit_buf[i];
            printf("  -> coil[%d] = %d\r\n", addr, coils_s2[addr]);
            if (addr == 0) {
                printf("  -> LED PB7: %s\r\n", coils_s2[0] ? "ON" : "OFF");
                HAL_GPIO_WritePin(GPIOB, GPIO_PIN_7, coils_s2[0] ? GPIO_PIN_SET : GPIO_PIN_RESET);
            }
        }
    }
    return 0;
}

static int read_discrete_inputs_cb_s2(void *buf, int bufsz)
{
    uint8_t *bit_buf = (uint8_t *)buf;
    for (int i = 0; i < 8; i++) {
        bit_buf[i] = discrete_inputs_s2[i];
    }
    return 0;
}

static int read_input_registers_cb_s2(void *buf, int bufsz)
{
    uint16_t *reg_buf = (uint16_t *)buf;
    for (int i = 0; i < 8; i++) {
        reg_buf[i] = input_registers_s2[i];
    }
    return 0;
}

/* ======================================================================== */
/* ===================== Maps Definition & Checkers ======================= */
/* ======================================================================== */
static const agile_modbus_slave_util_map_t map_registers_s1[] = {
    {0x0000, 0x0009, read_holding_cb_s1, write_holding_cb_s1}
};
static const agile_modbus_slave_util_map_t map_coils_s1[] = {
    {0x0000, 0x0007, read_coils_cb_s1, write_coils_cb_s1}
};
static const agile_modbus_slave_util_map_t map_discrete_inputs_s1[] = {
    {0x0000, 0x0007, read_discrete_inputs_cb_s1, NULL}
};
static const agile_modbus_slave_util_map_t map_input_registers_s1[] = {
    {0x0000, 0x0007, read_input_registers_cb_s1, NULL}
};

static const agile_modbus_slave_util_map_t map_registers_s2[] = {
    {0x0000, 0x0009, read_holding_cb_s2, write_holding_cb_s2}
};
static const agile_modbus_slave_util_map_t map_coils_s2[] = {
    {0x0000, 0x0007, read_coils_cb_s2, write_coils_cb_s2}
};
static const agile_modbus_slave_util_map_t map_discrete_inputs_s2[] = {
    {0x0000, 0x0007, read_discrete_inputs_cb_s2, NULL}
};
static const agile_modbus_slave_util_map_t map_input_registers_s2[] = {
    {0x0000, 0x0007, read_input_registers_cb_s2, NULL}
};

/* Address Checkers */
static int addr_check_s1(agile_modbus_t *ctx, struct agile_modbus_slave_info *slave_info)
{
    int slave = slave_info->sft->slave;
    if ((slave != ctx->slave) && (slave != AGILE_MODBUS_BROADCAST_ADDRESS))
        return -AGILE_MODBUS_EXCEPTION_UNKNOW;

    int function = slave_info->sft->function;
    int address = slave_info->address;
    int nb = slave_info->nb;

    switch (function) {
        case AGILE_MODBUS_FC_READ_COILS:
        case AGILE_MODBUS_FC_WRITE_SINGLE_COIL:
        case AGILE_MODBUS_FC_WRITE_MULTIPLE_COILS: {
            int qty = (function == AGILE_MODBUS_FC_WRITE_SINGLE_COIL) ? 1 : nb;
            if (address < 0 || (address + qty) > 8) return -AGILE_MODBUS_EXCEPTION_ILLEGAL_DATA_ADDRESS;
            break;
        }
        case AGILE_MODBUS_FC_READ_DISCRETE_INPUTS: {
            if (address < 0 || (address + nb) > 8) return -AGILE_MODBUS_EXCEPTION_ILLEGAL_DATA_ADDRESS;
            break;
        }
        case AGILE_MODBUS_FC_READ_HOLDING_REGISTERS:
        case AGILE_MODBUS_FC_WRITE_SINGLE_REGISTER:
        case AGILE_MODBUS_FC_WRITE_MULTIPLE_REGISTERS: {
            int qty = (function == AGILE_MODBUS_FC_WRITE_SINGLE_REGISTER) ? 1 : nb;
            if (address < 0 || (address + qty) > 10) return -AGILE_MODBUS_EXCEPTION_ILLEGAL_DATA_ADDRESS;
            break;
        }
        case AGILE_MODBUS_FC_READ_INPUT_REGISTERS: {
            if (address < 0 || (address + nb) > 8) return -AGILE_MODBUS_EXCEPTION_ILLEGAL_DATA_ADDRESS;
            break;
        }
        default:
            return -AGILE_MODBUS_EXCEPTION_ILLEGAL_FUNCTION;
    }
    return 0;
}

static int addr_check_s2(agile_modbus_t *ctx, struct agile_modbus_slave_info *slave_info)
{
    int slave = slave_info->sft->slave;
    if ((slave != ctx->slave) && (slave != AGILE_MODBUS_BROADCAST_ADDRESS))
        return -AGILE_MODBUS_EXCEPTION_UNKNOW;

    int function = slave_info->sft->function;
    int address = slave_info->address;
    int nb = slave_info->nb;

    switch (function) {
        case AGILE_MODBUS_FC_READ_COILS:
        case AGILE_MODBUS_FC_WRITE_SINGLE_COIL:
        case AGILE_MODBUS_FC_WRITE_MULTIPLE_COILS: {
            int qty = (function == AGILE_MODBUS_FC_WRITE_SINGLE_COIL) ? 1 : nb;
            if (address < 0 || (address + qty) > 8) return -AGILE_MODBUS_EXCEPTION_ILLEGAL_DATA_ADDRESS;
            break;
        }
        case AGILE_MODBUS_FC_READ_DISCRETE_INPUTS: {
            if (address < 0 || (address + nb) > 8) return -AGILE_MODBUS_EXCEPTION_ILLEGAL_DATA_ADDRESS;
            break;
        }
        case AGILE_MODBUS_FC_READ_HOLDING_REGISTERS:
        case AGILE_MODBUS_FC_WRITE_SINGLE_REGISTER:
        case AGILE_MODBUS_FC_WRITE_MULTIPLE_REGISTERS: {
            int qty = (function == AGILE_MODBUS_FC_WRITE_SINGLE_REGISTER) ? 1 : nb;
            if (address < 0 || (address + qty) > 10) return -AGILE_MODBUS_EXCEPTION_ILLEGAL_DATA_ADDRESS;
            break;
        }
        case AGILE_MODBUS_FC_READ_INPUT_REGISTERS: {
            if (address < 0 || (address + nb) > 8) return -AGILE_MODBUS_EXCEPTION_ILLEGAL_DATA_ADDRESS;
            break;
        }
        default:
            return -AGILE_MODBUS_EXCEPTION_ILLEGAL_FUNCTION;
    }
    return 0;
}

static const agile_modbus_slave_util_t slave_util_s1 = {
    .tab_bits = map_coils_s1,
    .nb_bits = sizeof(map_coils_s1) / sizeof(map_coils_s1[0]),
    .tab_input_bits = map_discrete_inputs_s1,
    .nb_input_bits = sizeof(map_discrete_inputs_s1) / sizeof(map_discrete_inputs_s1[0]),
    .tab_registers = map_registers_s1,
    .nb_registers = sizeof(map_registers_s1) / sizeof(map_registers_s1[0]),
    .tab_input_registers = map_input_registers_s1,
    .nb_input_registers = sizeof(map_input_registers_s1) / sizeof(map_input_registers_s1[0]),
    .addr_check = addr_check_s1
};

static const agile_modbus_slave_util_t slave_util_s2 = {
    .tab_bits = map_coils_s2,
    .nb_bits = sizeof(map_coils_s2) / sizeof(map_coils_s2[0]),
    .tab_input_bits = map_discrete_inputs_s2,
    .nb_input_bits = sizeof(map_discrete_inputs_s2) / sizeof(map_discrete_inputs_s2[0]),
    .tab_registers = map_registers_s2,
    .nb_registers = sizeof(map_registers_s2) / sizeof(map_registers_s2[0]),
    .tab_input_registers = map_input_registers_s2,
    .nb_input_registers = sizeof(map_input_registers_s2) / sizeof(map_input_registers_s2[0]),
    .addr_check = addr_check_s2
};

/* ======================================================================== */
/* ======================= Modbus Initialization ========================== */
/* ======================================================================== */
void Modbus_Init(void)
{
    /* 1. Khởi tạo các ring buffer */
    rt_ringbuffer_init(&usart3_rb, usart3_ring_buf_data, MODBUS_RING_BUF_SIZE);
    rt_ringbuffer_init(&usart1_rb, usart1_ring_buf_data, MODBUS_RING_BUF_SIZE);
    
    /* 2. Xóa sạch các bộ đệm nhận DMA */
    memset(usart3_rx_dma_buf, 0, RX_DMA_BUF_SIZE);
    memset(usart1_rx_dma_buf, 0, RX_DMA_BUF_SIZE);
    
    /* 3. Kích hoạt ngắt IDLE cho cả hai UART */
    __HAL_UART_ENABLE_IT(&huart3, UART_IT_IDLE);
    __HAL_UART_ENABLE_IT(&huart1, UART_IT_IDLE);
    
    /* 4. Khởi động nhận DMA Circular */
    HAL_UART_Receive_DMA(&huart3, usart3_rx_dma_buf, RX_DMA_BUF_SIZE);
    HAL_UART_Receive_DMA(&huart1, usart1_rx_dma_buf, RX_DMA_BUF_SIZE);
}

/* ======================================================================== */
/* =========================== Modbus Process ============================= */
/* ======================================================================== */
void Modbus_Process(void)
{
    static uint8_t is_ctx_inited = 0;
    
    /* Khởi tạo các ngữ cảnh Agile Modbus RTU một lần */
    if (!is_ctx_inited) {
        agile_modbus_rtu_init(&ctx_usart3, usart3_tx_buf, sizeof(usart3_tx_buf), usart3_rx_processing_buf, sizeof(usart3_rx_processing_buf));
        agile_modbus_set_slave(&ctx_usart3._ctx, 1); /* Slave ID = 1 */

        agile_modbus_rtu_init(&ctx_usart1, usart1_tx_buf, sizeof(usart1_tx_buf), usart1_rx_processing_buf, sizeof(usart1_rx_processing_buf));
        agile_modbus_set_slave(&ctx_usart1._ctx, 2); /* Slave ID = 2 */

        is_ctx_inited = 1;
    }
    
    /* ------------------- Xử lý Modbus cho USART3 (ID 1) ------------------- */
    uint32_t data_len3 = rt_ringbuffer_data_len(&usart3_rb);
    if (data_len3 > 0) {
        if (data_len3 > ctx_usart3._ctx.read_bufsz) {
            data_len3 = ctx_usart3._ctx.read_bufsz;
        }
        
        uint32_t rx_len = rt_ringbuffer_get(&usart3_rb, ctx_usart3._ctx.read_buf, data_len3);
        
        printf("[Slave 1 - USART3] Popped %d bytes: ", (int)rx_len);
        for(int i = 0; i < rx_len; i++) {
            printf("%02X ", ctx_usart3._ctx.read_buf[i]);
        }
        printf("\r\n");

        int send_len = agile_modbus_slave_handle(&ctx_usart3._ctx, rx_len, 1, 
                                                 agile_modbus_slave_util_callback, &slave_util_s1, NULL);
        
        if (send_len > 0) {
            printf("[Slave 1 - USART3] Responding %d bytes\r\n", send_len);
            
            /* Dynamic Pin Control: Switch PC10 to Push-Pull for strong transmission */
            GPIO_InitTypeDef GPIO_InitStruct = {0};
            GPIO_InitStruct.Pin = GPIO_PIN_10;
            GPIO_InitStruct.Mode = GPIO_MODE_AF_PP;
            GPIO_InitStruct.Pull = GPIO_NOPULL;
            GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
            GPIO_InitStruct.Alternate = GPIO_AF7_USART3;
            HAL_GPIO_Init(GPIOC, &GPIO_InitStruct);

            HAL_UART_Transmit(&huart3, ctx_usart3._ctx.send_buf, send_len, 100);

            /* Dynamic Pin Control: Switch PC10 back to Input High-Z to release the bus */
            GPIO_InitStruct.Mode = GPIO_MODE_INPUT;
            GPIO_InitStruct.Pull = GPIO_PULLUP;
            HAL_GPIO_Init(GPIOC, &GPIO_InitStruct);
        }
    }

    /* ------------------- Xử lý Modbus cho USART1 (ID 2) ------------------- */
    uint32_t data_len1 = rt_ringbuffer_data_len(&usart1_rb);
    if (data_len1 > 0) {
        if (data_len1 > ctx_usart1._ctx.read_bufsz) {
            data_len1 = ctx_usart1._ctx.read_bufsz;
        }
        
        uint32_t rx_len = rt_ringbuffer_get(&usart1_rb, ctx_usart1._ctx.read_buf, data_len1);
        
        printf("[Slave 2 - USART1] Popped %d bytes: ", (int)rx_len);
        for(int i = 0; i < rx_len; i++) {
            printf("%02X ", ctx_usart1._ctx.read_buf[i]);
        }
        printf("\r\n");

        int send_len = agile_modbus_slave_handle(&ctx_usart1._ctx, rx_len, 1, 
                                                 agile_modbus_slave_util_callback, &slave_util_s2, NULL);
        
        if (send_len > 0) {
            printf("[Slave 2 - USART1] Responding %d bytes\r\n", send_len);
            
            /* Dynamic Pin Control: Switch PC4 to Push-Pull for strong transmission */
            GPIO_InitTypeDef GPIO_InitStruct = {0};
            GPIO_InitStruct.Pin = GPIO_PIN_4;
            GPIO_InitStruct.Mode = GPIO_MODE_AF_PP;
            GPIO_InitStruct.Pull = GPIO_NOPULL;
            GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
            GPIO_InitStruct.Alternate = GPIO_AF7_USART1;
            HAL_GPIO_Init(GPIOC, &GPIO_InitStruct);

            HAL_UART_Transmit(&huart1, ctx_usart1._ctx.send_buf, send_len, 100);

            /* Dynamic Pin Control: Switch PC4 back to Input High-Z to release the bus */
            GPIO_InitStruct.Mode = GPIO_MODE_INPUT;
            GPIO_InitStruct.Pull = GPIO_PULLUP;
            HAL_GPIO_Init(GPIOC, &GPIO_InitStruct);
        }
    }
}
