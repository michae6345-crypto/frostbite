#pragma once
#include <stdint.h>
typedef int i2c_status_t;
#define I2C_STATUS_SUCCESS 0
void i2c_init(void);
i2c_status_t i2c_transmit(uint8_t a,const uint8_t*d,uint16_t n,uint16_t t);
i2c_status_t i2c_write_register(uint8_t a,uint8_t r,const uint8_t*d,uint16_t n,uint16_t t);
#define i2c_transmit_P i2c_transmit
