#!/usr/bin/env python3
import serial
import time
import sys

def calculate_crc(data: bytes) -> bytes:
    crc = 0xFFFF
    for pos in data:
        crc ^= pos
        for _ in range(8):
            if (crc & 1) != 0:
                crc >>= 1
                crc ^= 0xA001
            else:
                crc >>= 1
    return bytes([crc & 0xFF, (crc >> 8) & 0xFF])

def send_request(ser, slave_id, fc, start_addr, quantity_or_val, is_write=False):
    if not is_write:
        # Read Holding Registers (FC 03)
        pdu = bytes([
            slave_id,
            fc,
            (start_addr >> 8) & 0xFF, start_addr & 0xFF,
            (quantity_or_val >> 8) & 0xFF, quantity_or_val & 0xFF
        ])
        expected_len = 3 + (quantity_or_val * 2) + 2  # ID + FC + ByteCount + Data + CRC
    else:
        # Write Single Register (FC 06) or Write Single Coil (FC 05)
        pdu = bytes([
            slave_id,
            fc,
            (start_addr >> 8) & 0xFF, start_addr & 0xFF,
            (quantity_or_val >> 8) & 0xFF, quantity_or_val & 0xFF
        ])
        expected_len = 6 + 2  # ID + FC + Addr_H + Addr_L + Val_H + Val_L + CRC

    full_frame = pdu + calculate_crc(pdu)
    
    # Clear input buffer
    ser.reset_input_buffer()
    
    print(f"--> Sending to Slave {slave_id} (FC {fc}): {full_frame.hex(' ').upper()}")
    ser.write(full_frame)
    ser.flush()
    
    # Wait for MCU response
    time.sleep(0.1)
    
    rx_data = ser.read(expected_len)
    if not rx_data:
        print(f"<-- Timeout: No response from Slave {slave_id}")
        return None
        
    print(f"<-- Received: {rx_data.hex(' ').upper()}")
    
    # Verify CRC
    payload = rx_data[:-2]
    received_crc = rx_data[-2:]
    calculated_crc = calculate_crc(payload)
    if received_crc != calculated_crc:
        print("<-- Error: Invalid CRC!")
        return None
        
    return rx_data

def main():
    port = "/dev/ttyUSB0"
    print(f"Opening port {port} at 115200 bps, Even Parity, 1 Stop Bit...")
    try:
        ser = serial.Serial(
            port=port,
            baudrate=115200,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_EVEN,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.5
        )
    except Exception as e:
        print(f"Error opening serial port: {e}")
        sys.exit(1)
        
    try:
        # --- TEST 1: Read Holding Registers from Slave 1 (ID = 1) ---
        print("\n=== Test 1: Reading 10 holding registers from Slave 1 (USART3, ID = 1) ===")
        res1 = send_request(ser, slave_id=1, fc=3, start_addr=0, quantity_or_val=10)
        if res1:
            byte_count = res1[2]
            data = res1[3:3+byte_count]
            regs = [(data[i] << 8) | data[i+1] for i in range(0, byte_count, 2)]
            print(f"Slave 1 Registers: {regs}")
            
        time.sleep(0.2)
        
        # --- TEST 2: Read Holding Registers from Slave 2 (ID = 2) ---
        print("\n=== Test 2: Reading 10 holding registers from Slave 2 (USART1, ID = 2) ===")
        res2 = send_request(ser, slave_id=2, fc=3, start_addr=0, quantity_or_val=10)
        if res2:
            byte_count = res2[2]
            data = res2[3:3+byte_count]
            regs = [(data[i] << 8) | data[i+1] for i in range(0, byte_count, 2)]
            print(f"Slave 2 Registers: {regs}")

        time.sleep(0.2)
        
        # --- TEST 3: Toggle LED PB7 via Slave 1 (ID = 1) Write Register 3 ---
        print("\n=== Test 3: Writing 1 to Holding Register 3 on Slave 1 to trigger LED PB7 toggle ===")
        send_request(ser, slave_id=1, fc=6, start_addr=3, quantity_or_val=1, is_write=True)
        
        time.sleep(0.2)
        
        # --- TEST 4: Toggle LED PB7 via Slave 2 (ID = 2) Write Register 3 ---
        print("\n=== Test 4: Writing 1 to Holding Register 3 on Slave 2 to trigger LED PB7 toggle ===")
        send_request(ser, slave_id=2, fc=6, start_addr=3, quantity_or_val=1, is_write=True)

    finally:
        ser.close()
        print("\nTest completed. Serial port closed.")

if __name__ == "__main__":
    main()
