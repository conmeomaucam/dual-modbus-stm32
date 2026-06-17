#!/usr/bin/env python3
import time
import sys
import serial

# Màu sắc ANSI để hiển thị đẹp mắt
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

def explain_exception(response: bytes):
    """Giải thích chi tiết gói tin phản hồi lỗi Modbus Exception"""
    if len(response) < 5:
        print(f"{RED}Gói tin phản hồi quá ngắn ({len(response)} bytes), không đúng định dạng Modbus.{RESET}")
        return
        
    slave_id = response[0]
    error_fc = response[1]
    exception_code = response[2]
    received_crc = response[3:5]
    
    # Tính CRC để xác thực gói tin lỗi nhận được
    expected_crc = calculate_crc(response[:3])
    crc_ok = "HỢP LỆ (OK)" if received_crc == expected_crc else f"SAI (Kỳ vọng: {expected_crc.hex().upper()})"
    
    original_fc = error_fc & 0x7F
    
    print("\n" + "-"*50)
    print(f"{BOLD}{YELLOW}BẢN PHÂN TÍCH GÓI TIN PHẢN HỒI LỖI (EXCEPTION):{RESET}")
    print("-"*50)
    print(f"1. {BOLD}Slave ID:{RESET} {slave_id} (Đúng trạm STM32)")
    print(f"2. {BOLD}Mã Function Code Lỗi:{RESET} 0x{error_fc:02X} (Báo lỗi lệnh 0x{original_fc:02X} do bit cao nhất được set lên 1)")
    
    # Diễn giải mã lỗi Exception
    exception_desc = {
        1: "01 - ILLEGAL FUNCTION (Function Code không được hỗ trợ bởi thiết bị)",
        2: "02 - ILLEGAL DATA ADDRESS (Địa chỉ thanh ghi không tồn tại hoặc ngoài vùng map)",
        3: "03 - ILLEGAL DATA VALUE (Giá trị ghi vào thanh ghi không hợp lệ/nằm ngoài dải cho phép)",
        4: "04 - SLAVE DEVICE FAILURE (Lỗi xảy ra trong quá trình thực thi lệnh tại Slave)"
    }.get(exception_code, f"{exception_code} - Lỗi không xác định")
    
    print(f"3. {BOLD}Mã lỗi Exception Code:{RESET} {CYAN}{BOLD}{exception_desc}{RESET}")
    print(f"4. {BOLD}Mã kiểm lỗi CRC:{RESET} {received_crc.hex(' ').upper()} -> {GREEN if received_crc == expected_crc else RED}{crc_ok}{RESET}")
    print("-"*50 + "\n")

def main():
    print("="*60)
    print(f"{BOLD}{CYAN}     GỬI YÊU CẦU LỖI ĐỂ XEM PHẢN HỒI EXCEPTION TỪ STM32{RESET}")
    print("="*60)
    
    port = "/dev/ttyUSB0"
    slave_id = 1
    
    print(f"Cấu hình mặc định: Cổng {port}, Slave ID: {slave_id}, Tốc độ: 115200, Even Parity")
    
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
        print(f"{RED}{BOLD}Lỗi: Không thể mở cổng Serial {port}.{RESET} Chi tiết: {e}")
        sys.exit(1)
        
    print("\nChọn loại lỗi bạn muốn gửi đi:")
    print(f" {BOLD}1.{RESET} Gửi Function Code lạ không hỗ trợ (Ví dụ FC 07) -> Kỳ vọng nhận lỗi {BOLD}Exception 01{RESET}")
    print(f" {BOLD}2.{RESET} Gửi yêu cầu đọc ngoài vùng địa chỉ thanh ghi (Đọc Reg 15) -> Kỳ vọng nhận lỗi {BOLD}Exception 02{RESET}")
    
    choice = input("\nNhập lựa chọn của bạn (1 hoặc 2): ").strip()
    
    if choice == "1":
        # FC 07 (Read Exception Status) - Không hỗ trợ
        pdu = bytes([slave_id, 0x07])
    elif choice == "2":
        # FC 03 đọc 1 thanh ghi tại địa chỉ 15 (0x000F) - Ngoài vùng map 0-9
        pdu = bytes([slave_id, 0x03, 0x00, 0x0F, 0x00, 0x01])
    else:
        print(f"{RED}Lựa chọn không hợp lệ!{RESET}")
        ser.close()
        sys.exit(1)
        
    # Tính CRC và đóng gói
    full_frame = pdu + calculate_crc(pdu)
    
    print(f"\n{GREEN}--> Gửi đi khung tin thô:{RESET} {full_frame.hex(' ').upper()}")
    ser.write(full_frame)
    ser.flush()
    
    # Đọc phản hồi (gói tin lỗi Modbus Exception luôn dài đúng 5 bytes)
    response = ser.read(5)
    
    if response:
        print(f"{GREEN}<-- Nhận về khung tin thô:{RESET} {response.hex(' ').upper()}")
        explain_exception(response)
    else:
        print(f"{RED}<-- Nhận về: Không có phản hồi (Timeout). Hãy kiểm tra kết nối dây hoặc mạch đã cấp nguồn chưa.{RESET}")
        
    ser.close()

if __name__ == "__main__":
    main()
