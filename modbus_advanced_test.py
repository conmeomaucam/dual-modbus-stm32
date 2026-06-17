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
    
    # Cấu hình tạm thời timeout
    ser.timeout = timeout
    
    # Chờ đọc phản hồi
    rx_data = ser.read(expected_response_len)
    if rx_data:
        print(f"<-- Nhận: {rx_data.hex(' ').upper()}")
    else:
        print("<-- Nhận: Không có phản hồi (Timeout)")
    return rx_data

def run_test_case_1(ser, slave_id: int):
    """Test Case 1: Đọc địa chỉ không hợp lệ (Exception 02 - Illegal Data Address)"""
    print(f"\n{CYAN}{BOLD}[Test Case 1] Đọc địa chỉ không tồn tại (Yêu cầu Exception 02){RESET}")
    # Đọc 5 registers bắt đầu từ địa chỉ 10 (0x000A) - Mảng thực tế chỉ từ 0-9
    pdu = bytes([slave_id, 0x03, 0x00, 0x0A, 0x00, 0x05])
    # Kỳ vọng phản hồi lỗi dài 5 bytes: [ID, FC | 0x80, ExceptionCode, CRC_LSB, CRC_MSB]
    response = send_raw_frame(ser, pdu, 5)
    
    if len(response) >= 3:
        fc_err = response[1]
        err_code = response[2]
        if fc_err == 0x83 and err_code == 0x02:
            print(f"{GREEN}{BOLD}--> KẾT QUẢ: PASS (Nhận đúng mã lỗi 02 - Illegal Data Address){RESET}")
            return True
    print(f"{RED}{BOLD}--> KẾT QUẢ: FAIL (Phản hồi không đúng kỳ vọng){RESET}")
    return False

def run_test_case_2(ser, slave_id: int):
    """Test Case 2: Sử dụng Function Code chưa hỗ trợ (Exception 01 - Illegal Function)"""
    print(f"\n{CYAN}{BOLD}[Test Case 2] Sử dụng Function Code không hỗ trợ (Yêu cầu Exception 01){RESET}")
    # Gửi lệnh Read Exception Status (FC 07) - Hoàn toàn không được hỗ trợ
    pdu = bytes([slave_id, 0x07])
    # Kỳ vọng phản hồi lỗi dài 5 bytes: [ID, FC | 0x80, ExceptionCode, CRC_LSB, CRC_MSB]
    response = send_raw_frame(ser, pdu, 5)
    
    if len(response) >= 3:
        fc_err = response[1]
        err_code = response[2]
        if fc_err == 0x87 and err_code == 0x01:
            print(f"{GREEN}{BOLD}--> KẾT QUẢ: PASS (Nhận đúng mã lỗi 01 - Illegal Function){RESET}")
            return True
    print(f"{RED}{BOLD}--> KẾT QUẢ: FAIL (Phản hồi không đúng kỳ vọng){RESET}")
    return False

def run_test_case_3(ser):
    """Test Case 3: Gửi lệnh Broadcast (Slave ID = 0, LED toggle)"""
    print(f"\n{CYAN}{BOLD}[Test Case 3] Gửi lệnh Broadcast tới ID 0 (Yêu cầu đổi LED nhưng KHÔNG phản hồi){RESET}")
    # Ghi giá trị 1 vào thanh ghi 3 (Toggle LED) với Slave ID = 0
    pdu = bytes([0x00, 0x06, 0x00, 0x03, 0x00, 0x01])
    # Kỳ vọng: Slave xử lý đổi trạng thái LED nhưng IM LẶNG (Timeout hoàn toàn)
    response = send_raw_frame(ser, pdu, 10, timeout=0.3)
    
    if not response:
        print(f"{GREEN}{BOLD}--> KẾT QUẢ: PASS (Slave không phản hồi đúng theo đặc tả Broadcast){RESET}")
        print(f"{YELLOW}Gợi ý: Hãy kiểm tra xem LED PB7 trên board STM32 có chuyển trạng thái bật/tắt hay không.{RESET}")
        return True
    else:
        print(f"{RED}{BOLD}--> KẾT QUẢ: FAIL (Slave phản hồi khi nhận lệnh Broadcast - Sai đặc tả!){RESET}")
        return False

def run_test_case_4(ser, slave_id: int):
    """Test Case 4: Ghi nhiều thanh ghi cùng lúc (FC 16 / 0x10)"""
    print(f"\n{CYAN}{BOLD}[Test Case 4] Ghi nhiều thanh ghi cùng lúc (FC 16 / 0x10){RESET}")
    # Ghi 3 thanh ghi từ địa chỉ 0, các giá trị lần lượt là: 0xAAAA, 0xBBBB, 0xCCCC
    # PDU: [ID, FC(0x10), StartAddr(2B), Qty(2B), ByteCount(1B), Data(6B)]
    pdu = bytes([
        slave_id, 0x10, 
        0x00, 0x00, 
        0x00, 0x03, 
        0x06, 
        0xAA, 0xAA, 
        0xBB, 0xBB, 
        0xCC, 0xCC
    ])
    # Kỳ vọng phản hồi thành công dài 8 bytes: [ID, 0x10, StartAddr(2B), Qty(2B), CRC_LSB, CRC_MSB]
    response = send_raw_frame(ser, pdu, 8)
    
    if len(response) == 8:
        # Xác thực CRC phản hồi
        payload = response[:-2]
        received_crc = response[-2:]
        if calculate_crc(payload) == received_crc and response[1] == 0x10:
            print(f"{GREEN}{BOLD}--> KẾT QUẢ: PASS (Ghi nhiều thanh ghi thành công){RESET}")
            
            # Đọc lại để xác thực dữ liệu đã ghi
            print(f"{YELLOW}Đang đọc lại các thanh ghi 0-2 để kiểm chứng...{RESET}")
            read_pdu = bytes([slave_id, 0x03, 0x00, 0x00, 0x00, 0x03])
            read_response = send_raw_frame(ser, read_pdu, 3 + 3*2)
            if len(read_response) >= 9:
                data = read_response[3:9]
                if data == bytes([0xAA, 0xAA, 0xBB, 0xBB, 0xCC, 0xCC]):
                    print(f"{GREEN}{BOLD}--> XÁC THỰC DỮ LIỆU ĐỌC VỀ: ĐÚNG (0xAAAA, 0xBBBB, 0xCCCC){RESET}")
                    return True
                else:
                    print(f"{RED}{BOLD}--> XÁC THỰC DỮ LIỆU ĐỌC VỀ: SAI (Dữ liệu nhận về: {data.hex().upper()}){RESET}")
            else:
                print(f"{RED}{BOLD}--> XÁC THỰC DỮ LIỆU ĐỌC VỀ: THẤT BẠI (Không đọc được phản hồi){RESET}")
    print(f"{RED}{BOLD}--> KẾT QUẢ: FAIL (Quá trình ghi/đọc kiểm chứng thất bại){RESET}")
    return False

def main():
    print("="*60)
    print(f"{BOLD}{CYAN}      CHƯƠNG TRÌNH KIỂM THỬ MODBUS RTU NÂNG CAO (AUTOMATED){RESET}")
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
        results['TC1: Exception 02'] = run_test_case_1(ser, slave_id)
        time.sleep(0.2)
        
        results['TC2: Exception 01'] = run_test_case_2(ser, slave_id)
        time.sleep(0.2)
        
        results['TC3: Broadcast ID 0'] = run_test_case_3(ser)
        time.sleep(0.2)
        
        results['TC4: Write Multiple FC 16'] = run_test_case_4(ser, slave_id)
        time.sleep(0.2)
        
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
        print(f"  - {tc:<30}: {status_str}")
    print("="*60)
    if all_pass:
        print(f"{GREEN}{BOLD}KẾT LUẬN CHUNG: TẤT CẢ CÁC TÍNH NĂNG NÂNG CAO ĐẠT YÊU CẦU!{RESET}")
    else:
        print(f"{RED}{BOLD}KẾT LUẬN CHUNG: CÓ TÍNH NĂNG BỊ LỖI, CẦN KIỂM TRA LẠI CODE SLAVE.{RESET}")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()
