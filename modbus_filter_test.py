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

def send_raw_frame(ser, frame: bytes, expected_response_len: int, timeout: float = 0.2) -> bytes:
    """Gửi một raw frame và nhận phản hồi"""
    ser.reset_input_buffer()
    full_frame = frame + calculate_crc(frame)
    print(f"--> Gửi: {full_frame.hex(' ').upper()}")
    
    ser.write(full_frame)
    ser.flush()
    
    # Cấu hình timeout ngắn để kiểm thử phản hồi nhanh
    ser.timeout = timeout
    rx_data = ser.read(expected_response_len)
    if rx_data:
        print(f"<-- Nhận: {rx_data.hex(' ').upper()}")
    else:
        print("<-- Nhận: Không có phản hồi (Timeout)")
    return rx_data

def run_filter_test(ser, target_id: int, expected_to_respond: bool):
    """Gửi lệnh đến một Slave ID và kiểm tra xem có phản hồi hay không"""
    print(f"\n{CYAN}{BOLD}[Kiểm thử ID {target_id}] Gửi lệnh đọc thanh ghi 0 (FC 03) tới Slave ID {target_id}...{RESET}")
    pdu = bytes([target_id, 0x03, 0x00, 0x00, 0x00, 0x01])
    
    # Đo phản hồi (chỉ chờ tối đa 0.2 giây)
    response = send_raw_frame(ser, pdu, 7, timeout=0.2)
    
    if expected_to_respond:
        if response and len(response) >= 5:
            # Xác thực gói tin phản hồi thành công
            if response[0] == target_id and response[1] == 0x03:
                print(f"{GREEN}{BOLD}--> KẾT QUẢ: PASS (Slave ID {target_id} phản hồi chính xác){RESET}")
                return True
        print(f"{RED}{BOLD}--> KẾT QUẢ: FAIL (Không nhận được phản hồi đúng từ Slave ID {target_id}){RESET}")
        return False
    else:
        if not response:
            print(f"{GREEN}{BOLD}--> KẾT QUẢ: PASS (Slave ID {target_id} im lặng đúng quy định - Lọc ID tốt){RESET}")
            return True
        else:
            print(f"{RED}{BOLD}--> KẾT QUẢ: FAIL (Lỗi bảo mật/giao thức: Slave phản hồi gói tin KHÔNG phải ID của mình!){RESET}")
            return False

def main():
    print("="*60)
    print(f"{BOLD}{CYAN}    CHƯƠNG TRÌNH KIỂM THỬ LỌC ĐỊA CHỈ SLAVE ID (MODBUS RTU){RESET}")
    print("="*60)
    print(f"{YELLOW}Mục tiêu: Đảm bảo Slave ID 1 chỉ phản hồi ID 1 và im lặng trước ID 2, 3, 4.{RESET}")
    
    port = input("Nhập cổng Serial (Mặc định: /dev/ttyUSB0): ").strip()
    if not port:
        port = "/dev/ttyUSB0"
        
    print(f"\nĐang mở cổng {port} cấu hình 115200, Even Parity...")
    try:
        ser = serial.Serial(
            port=port,
            baudrate=115200,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_EVEN,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.2
        )
    except Exception as e:
        print(f"{RED}{BOLD}Lỗi: Không thể mở cổng Serial {port}.{RESET} Chi tiết: {e}")
        sys.exit(1)
        
    results = {}
    try:
        # Chạy kiểm thử cho ID 2, 3, 4 (Kỳ vọng: Im lặng/Timeout)
        results['Slave ID 2 (Kỳ vọng: Im lặng)'] = run_filter_test(ser, 2, expected_to_respond=False)
        time.sleep(0.1)
        
        results['Slave ID 3 (Kỳ vọng: Im lặng)'] = run_filter_test(ser, 3, expected_to_respond=False)
        time.sleep(0.1)
        
        results['Slave ID 4 (Kỳ vọng: Im lặng)'] = run_filter_test(ser, 4, expected_to_respond=False)
        time.sleep(0.1)
        
        # Chạy kiểm thử cho ID 1 (Kỳ vọng: Có phản hồi thành công)
        results['Slave ID 1 (Kỳ vọng: Phản hồi)'] = run_filter_test(ser, 1, expected_to_respond=True)
        time.sleep(0.1)
        
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
        print(f"{GREEN}{BOLD}KẾT LUẬN: TÍNH NĂNG LỌC ĐỊA CHỈ SLAVE ID HOẠT ĐỘNG HOÀN HẢO!{RESET}")
    else:
        print(f"{RED}{BOLD}KẾT LUẬN: LỖI LỌC SLAVE ID, SLAVE PHẢN HỒI SAI ĐỊA CHỈ.{RESET}")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()
