#!/usr/bin/env python3
import time
import sys
import serial

# Màu sắc ANSI
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

def calculate_crc(data: bytes) -> bytes:
    """Tính toán mã kiểm lỗi CRC-16 cho Modbus RTU"""
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

def send_raw_frame(ser, frame: bytes, expected_response_len: int, timeout: float = 0.25) -> bytes:
    """Gửi một raw frame (chưa có CRC) và nhận phản hồi"""
    ser.reset_input_buffer()
    
    # Tính toán và thêm CRC vào frame
    full_frame = frame + calculate_crc(frame)
    print(f"--> Gửi: {full_frame.hex(' ').upper()}")
    
    ser.write(full_frame)
    ser.flush()
    
    # Chờ đọc phản hồi
    ser.timeout = timeout
    rx_data = ser.read(expected_response_len)
    if rx_data:
        print(f"<-- Nhận: {rx_data.hex(' ').upper()}")
    else:
        print("<-- Nhận: Không có phản hồi (Timeout)")
    return rx_data

def decode_bits(byte_val: int, qty: int) -> list:
    """Giải mã byte thành danh sách các bit (LSB-first)"""
    bits = []
    for i in range(qty):
        bits.append((byte_val >> i) & 1)
    return bits

def run_test_case_1(ser, slave_id: int):
    """TC1: Đọc trạng thái Coils ban đầu (FC 01)"""
    print(f"\n{CYAN}{BOLD}[Test Case 1] Đọc trạng thái Coils ban đầu (FC 01){RESET}")
    # Đọc 8 coils từ địa chỉ 0x0000
    pdu = bytes([slave_id, 0x01, 0x00, 0x00, 0x00, 0x08])
    # Phản hồi thành công: [ID, 0x01, ByteCount(1), ByteVal, CRC_LSB, CRC_MSB] -> 6 bytes
    response = send_raw_frame(ser, pdu, 6)
    
    if len(response) == 6 and response[1] == 0x01:
        byte_count = response[2]
        byte_val = response[3]
        coils_state = decode_bits(byte_val, 8)
        print(f"-> Trạng thái Coils giải mã: {coils_state}")
        # Cấu hình ban đầu của STM32: coils[8] = {1, 0, 1, 0, 0, 0, 0, 0} -> 0x05 (10100000 LSB first)
        if byte_val == 0x05:
            print(f"{GREEN}{BOLD}--> KẾT QUẢ: PASS (Đọc đúng trạng thái Coils ban đầu){RESET}")
            return True
    print(f"{RED}{BOLD}--> KẾT QUẢ: FAIL (Sai dữ liệu hoặc lỗi phản hồi){RESET}")
    return False

def run_test_case_2(ser, slave_id: int):
    """TC2: Ghi một Coil đơn lẻ để điều khiển Led (FC 05)"""
    print(f"\n{CYAN}{BOLD}[Test Case 2] Ghi Coil đơn lẻ (FC 05) - Tắt Led (Coil 0 -> 0) và kiểm tra{RESET}")
    
    # Bước 1: Ghi Coil 0 về 0 (Giá trị 0x0000 là OFF, 0xFF00 là ON)
    write_pdu = bytes([slave_id, 0x05, 0x00, 0x00, 0x00, 0x00])
    # Phản hồi thành công trùng với gói gửi (8 bytes)
    write_response = send_raw_frame(ser, write_pdu, 8)
    
    if len(write_response) == 8 and write_response[1] == 0x05:
        print(f"{YELLOW}Đã gửi lệnh ghi Coil 0 = OFF. Đang đọc lại Coils để xác thực...{RESET}")
        
        # Bước 2: Đọc lại 8 coils
        read_pdu = bytes([slave_id, 0x01, 0x00, 0x00, 0x00, 0x08])
        read_response = send_raw_frame(ser, read_pdu, 6)
        
        if len(read_response) == 6 and read_response[1] == 0x01:
            byte_val = read_response[3]
            coils_state = decode_bits(byte_val, 8)
            print(f"-> Trạng thái Coils sau khi ghi: {coils_state}")
            # Mong đợi: coils[0] thành 0 -> [0, 0, 1, 0, 0, 0, 0, 0] -> 0x04
            if byte_val == 0x04:
                print(f"{GREEN}{BOLD}--> KẾT QUẢ: PASS (Ghi single coil 0 = OFF thành công, Led PB7 tắt){RESET}")
                return True
                
    print(f"{RED}{BOLD}--> KẾT QUẢ: FAIL (Quá trình ghi hoặc đọc lại thất bại){RESET}")
    return False

def run_test_case_3(ser, slave_id: int):
    """TC3: Ghi nhiều Coils cùng lúc (FC 15 / 0x0F)"""
    print(f"\n{CYAN}{BOLD}[Test Case 3] Ghi nhiều Coils cùng lúc (FC 15) - Bật lại Led (Coil 0 -> 1){RESET}")
    # Ghi trạng thái: [1, 1, 0, 0, 1, 1, 0, 0] vào địa chỉ 0x0000 -> 0x0007
    # LSB-first bit pattern: 00110011 (binary) -> 0x33 (hex)
    # PDU: [ID, 0x0F, StartAddr_H, StartAddr_L, Qty_H, Qty_L, ByteCount, ValueByte]
    pdu = bytes([slave_id, 0x0F, 0x00, 0x00, 0x00, 0x08, 0x01, 0x33])
    # Phản hồi thành công: [ID, 0x0F, StartAddr(2), Qty(2), CRC(2)] -> 8 bytes
    response = send_raw_frame(ser, pdu, 8)
    
    if len(response) == 8 and response[1] == 0x0F:
        print(f"{YELLOW}Đã ghi nhiều coils thành công. Đang đọc lại để xác thực...{RESET}")
        
        # Đọc lại để kiểm tra
        read_pdu = bytes([slave_id, 0x01, 0x00, 0x00, 0x00, 0x08])
        read_response = send_raw_frame(ser, read_pdu, 6)
        
        if len(read_response) == 6 and read_response[1] == 0x01:
            byte_val = read_response[3]
            coils_state = decode_bits(byte_val, 8)
            print(f"-> Trạng thái Coils sau khi ghi: {coils_state}")
            if byte_val == 0x33:
                print(f"{GREEN}{BOLD}--> KẾT QUẢ: PASS (Ghi nhiều Coils thành công, Led PB7 sáng){RESET}")
                return True
                
    print(f"{RED}{BOLD}--> KẾT QUẢ: FAIL (Ghi hoặc xác thực ghi nhiều Coils thất bại){RESET}")
    return False

def run_test_case_4(ser, slave_id: int):
    """TC4: Đọc các đầu vào số Discrete Inputs (FC 02)"""
    print(f"\n{CYAN}{BOLD}[Test Case 4] Đọc ngõ vào Discrete Inputs (FC 02){RESET}")
    # Đọc 8 discrete inputs từ địa chỉ 0x0000
    pdu = bytes([slave_id, 0x02, 0x00, 0x00, 0x00, 0x08])
    # Phản hồi: [ID, 0x02, ByteCount(1), ByteVal, CRC(2)] -> 6 bytes
    response = send_raw_frame(ser, pdu, 6)
    
    if len(response) == 6 and response[1] == 0x02:
        byte_val = response[3]
        inputs_state = decode_bits(byte_val, 8)
        print(f"-> Trạng thái Discrete Inputs giải mã: {inputs_state}")
        # Cấu hình ban đầu của STM32: discrete_inputs[8] = {1, 1, 0, 0, 1, 1, 0, 1} -> 0xB3 (10110011 LSB first)
        if byte_val == 0xB3:
            print(f"{GREEN}{BOLD}--> KẾT QUẢ: PASS (Đọc chính xác trạng thái Discrete Inputs){RESET}")
            return True
            
    print(f"{RED}{BOLD}--> KẾT QUẢ: FAIL (Sai dữ liệu hoặc lỗi phản hồi){RESET}")
    return False

def run_test_case_5(ser, slave_id: int):
    """TC5: Đọc thanh ghi đầu vào Input Registers (FC 04)"""
    print(f"\n{CYAN}{BOLD}[Test Case 5] Đọc các thanh ghi Input Registers (FC 04){RESET}")
    # Đọc 4 thanh ghi đầu vào từ địa chỉ 0x0000 (Chỉ đọc)
    pdu = bytes([slave_id, 0x04, 0x00, 0x00, 0x00, 0x04])
    # Phản hồi: [ID, 0x04, ByteCount(1 - là 8), Data(8 bytes), CRC(2)] -> 3 + 8 + 2 = 13 bytes
    response = send_raw_frame(ser, pdu, 13)
    
    if len(response) == 13 and response[1] == 0x04:
        # Giải mã các thanh ghi 16-bit (Big-endian)
        regs = []
        for i in range(4):
            val = (response[3 + i*2] << 8) | response[4 + i*2]
            regs.append(f"0x{val:04X}")
        print(f"-> Giá trị Input Registers đọc được: {regs}")
        
        # Đối chiếu cấu hình STM32: {0x0123, 0x4567, 0x89AB, 0xCDEF}
        expected = ["0x0123", "0x4567", "0x89AB", "0xCDEF"]
        if regs == expected:
            print(f"{GREEN}{BOLD}--> KẾT QUẢ: PASS (Đọc chính xác dữ liệu Input Registers){RESET}")
            return True
            
    print(f"{RED}{BOLD}--> KẾT QUẢ: FAIL (Sai dữ liệu hoặc lỗi phản hồi){RESET}")
    return False

def main():
    print("="*60)
    print(f"{BOLD}{CYAN}   KIỂM THỬ ĐẦY ĐỦ COILS, DISCRETE INPUTS & INPUT REGISTERS{RESET}")
    print("="*60)
    
    port = input("Nhập cổng Serial (Mặc định: /dev/ttyUSB0): ").strip()
    if not port:
        port = "/dev/ttyUSB0"
        
    slave_id_str = input("Nhập Slave ID của STM32 (Mặc định: 1): ").strip()
    slave_id = int(slave_id_str) if slave_id_str else 1
    
    print(f"\nĐang mở cổng {port} cấu hình 115200, Even Parity...")
    try:
        ser = serial.Serial(
            port=port,
            baudrate=115200,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_EVEN,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.25
        )
    except Exception as e:
        print(f"{RED}{BOLD}Lỗi: Không thể mở cổng Serial {port}.{RESET} Chi tiết: {e}")
        sys.exit(1)
        
    results = {}
    try:
        # Chạy từng Test Case
        results['TC1: Read Coils (FC 01)'] = run_test_case_1(ser, slave_id)
        time.sleep(0.15)
        
        results['TC2: Write Single Coil (FC 05)'] = run_test_case_2(ser, slave_id)
        time.sleep(0.15)
        
        results['TC3: Write Multiple Coils (FC 15)'] = run_test_case_3(ser, slave_id)
        time.sleep(0.15)
        
        results['TC4: Read Discrete Inputs (FC 02)'] = run_test_case_4(ser, slave_id)
        time.sleep(0.15)
        
        results['TC5: Read Input Registers (FC 04)'] = run_test_case_5(ser, slave_id)
        time.sleep(0.15)
        
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Bị dừng bởi người dùng.{RESET}")
    finally:
        ser.close()
        print(f"\n{CYAN}Đã đóng cổng Serial.{RESET}")
        
    # Tổng kết
    print("\n" + "="*60)
    print(f"{BOLD}{CYAN}                    TỔNG HỢP KẾT QUẢ KIỂM THỬ{RESET}")
    print("="*60)
    all_pass = True
    for tc, pass_status in results.items():
        status_str = f"{GREEN}PASS{RESET}" if pass_status else f"{RED}FAIL{RESET}"
        if not pass_status:
            all_pass = False
        print(f"  - {tc:<40}: {status_str}")
    print("="*60)
    if all_pass:
        print(f"{GREEN}{BOLD}KẾT LUẬN: TẤT CẢ CÁC VÙNG DỮ LIỆU MODBUS ĐỀU HOẠT ĐỘNG CHÍNH XÁC!{RESET}")
    else:
        print(f"{RED}{BOLD}KẾT LUẬN: CÓ LỖI XẢY RA TRONG QUÁ TRÌNH KIỂM THỬ VÙNG DỮ LIỆU.{RESET}")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()
