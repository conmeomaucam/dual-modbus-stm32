#!/usr/bin/env python3
import time
import sys
import random

try:
    import serial
except ImportError:
    print("Error: 'pyserial' is not installed. Please run: pip3 install pyserial")
    sys.exit(1)

# Màu sắc ANSI cho terminal đẹp mắt
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
MAGENTA = "\033[95m"
BOLD = "\033[1m"
RESET = "\033[0m"

def calculate_crc(data: bytes) -> bytes:
    """Tính toán mã kiểm lỗi CRC-16 cho Modbus RTU (LSB first)"""
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

def send_modbus_frame(ser, frame: bytes, response_len: int) -> tuple[bool, float, str]:
    """
    Gửi một frame Modbus và nhận phản hồi.
    Trả về: (thành công hay không, RTT tính bằng ms, chuỗi mô tả lỗi nếu có)
    """
    # Xóa bộ đệm nhận trước khi gửi để tránh dữ liệu rác
    ser.reset_input_buffer()
    
    full_frame = frame + calculate_crc(frame)
    
    start_time = time.perf_counter()
    ser.write(full_frame)
    ser.flush()
    
    # Đọc dữ liệu phản hồi (chờ theo timeout của Serial)
    rx_data = ser.read(response_len + 2) # Cộng 2 bytes CRC
    end_time = time.perf_counter()
    
    rtt = (end_time - start_time) * 1000.0
    
    if not rx_data:
        return False, rtt, "TIMEOUT"
        
    if len(rx_data) < (response_len + 2):
        return False, rtt, f"SHORT_FRAME ({len(rx_data)}/{response_len+2}B)"
        
    # Xác thực CRC
    payload = rx_data[:-2]
    received_crc = rx_data[-2:]
    calculated_crc = calculate_crc(payload)
    
    if received_crc != calculated_crc:
        return False, rtt, "CRC_ERROR"
        
    return True, rtt, ""

def run_stress_test(port: str, slave_id: int, mode: int, num_cycles: int, interval_ms: float):
    print(f"\n{CYAN}{BOLD}=== KHỞI CHẠY KIỂM THỬ ĐỘ ỔN ĐỊNH MODBUS RTU ==={RESET}")
    print(f"Cổng Serial:  {YELLOW}{port}{RESET}")
    print(f"Baudrate:     {YELLOW}115200 (Even, 9-bit, 1 Stopbit){RESET}")
    print(f"Slave ID:     {YELLOW}{slave_id}{RESET}")
    print(f"Chế độ test:  {YELLOW}{'1. Chỉ Đọc (Read Only)' if mode == 1 else '2. Chỉ Ghi (Write Only)' if mode == 2 else '3. Trộn lẫn (Read/Write Mixed)'}{RESET}")
    print(f"Số chu kỳ:    {YELLOW}{'Vô hạn (Nhấn Ctrl+C để dừng)' if num_cycles == 0 else num_cycles}{RESET}")
    print(f"Độ trễ chu kỳ: {YELLOW}{interval_ms} ms{RESET}\n")

    try:
        ser = serial.Serial(
            port=port,
            baudrate=115200,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_EVEN,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.25 # Timeout 250ms cho phản hồi nhanh
        )
    except Exception as e:
        print(f"{RED}{BOLD}Lỗi: Không thể mở cổng Serial {port}.{RESET} Chi tiết: {e}")
        return

    # Thống kê
    total_sent = 0
    success_count = 0
    timeout_count = 0
    crc_error_count = 0
    other_error_count = 0
    
    rtt_list = []
    
    # Mảng đếm lỗi chi tiết
    error_details = {}

    start_test_time = time.time()
    
    try:
        cycle = 0
        while True:
            if num_cycles > 0 and cycle >= num_cycles:
                break
                
            cycle += 1
            total_sent += 1
            
            # Quyết định hành động tùy theo chế độ
            action = mode
            if mode == 3:
                action = 1 if (cycle % 2 == 1) else 2
                
            success = False
            rtt = 0.0
            err_msg = ""
            
            if action == 1:
                # Đọc 10 holding registers đầu tiên (FC 03) từ địa chỉ 0
                pdu = bytes([slave_id, 0x03, 0x00, 0x00, 0x00, 0x0A])
                expected_len = 3 + (10 * 2) # ID + FC + ByteCount + 20 bytes data
                success, rtt, err_msg = send_modbus_frame(ser, pdu, expected_len)
            else:
                # Ghi giá trị (luân phiên 0 và 1) vào thanh ghi 3 (toggled LED trên mạch)
                led_val = 1 if (cycle % 2 == 0) else 0
                pdu = bytes([slave_id, 0x06, 0x00, 0x03, 0x00, led_val])
                expected_len = 6 # Lệnh phản hồi ghi FC 06 dài đúng 6 bytes
                success, rtt, err_msg = send_modbus_frame(ser, pdu, expected_len)
            
            if success:
                success_count += 1
                rtt_list.append(rtt)
            else:
                if err_msg == "TIMEOUT":
                    timeout_count += 1
                elif err_msg == "CRC_ERROR":
                    crc_error_count += 1
                else:
                    other_error_count += 1
                error_details[err_msg] = error_details.get(err_msg, 0) + 1

            # Tính toán thống kê nhanh
            success_rate = (success_count / total_sent) * 100.0
            avg_rtt = sum(rtt_list) / len(rtt_list) if rtt_list else 0.0
            min_rtt = min(rtt_list) if rtt_list else 0.0
            max_rtt = max(rtt_list) if rtt_list else 0.0
            
            # In dòng trạng thái cập nhật liên tục (In-place update)
            status_text = (
                f"\r{BOLD}Chu kỳ: {cycle:<6}{RESET} | "
                f"Thành công: {GREEN}{success_count:<5}{RESET} ({success_rate:5.1f}%) | "
                f"Timeout: {RED}{timeout_count:<4}{RESET} | "
                f"Lỗi CRC: {YELLOW}{crc_error_count:<4}{RESET} | "
                f"RTT: {avg_rtt:5.1f} ms"
            )
            sys.stdout.write(status_text)
            sys.stdout.flush()
            
            # Chờ trước chu kỳ tiếp theo
            if interval_ms > 0:
                time.sleep(interval_ms / 1000.0)
                
    except KeyboardInterrupt:
        print(f"\n\n{YELLOW}Đang dừng kiểm thử theo yêu cầu từ bàn phím (Ctrl+C)...{RESET}")
    finally:
        ser.close()
        
    # In báo cáo kết quả chi tiết
    duration = time.time() - start_test_time
    success_rate = (success_count / total_sent) * 100.0 if total_sent > 0 else 0.0
    avg_rtt = sum(rtt_list) / len(rtt_list) if rtt_list else 0.0
    min_rtt = min(rtt_list) if rtt_list else 0.0
    max_rtt = max(rtt_list) if rtt_list else 0.0
    
    print("\n" + "="*60)
    print(f"{BOLD}{CYAN}                 BÁO CÁO THỬ NGHIỆM ĐỘ ỔN ĐỊNH{RESET}")
    print("="*60)
    print(f"Tổng thời gian chạy test: {duration:.2f} giây")
    print(f"Số gói tin yêu cầu đã gửi: {total_sent}")
    print(f"Số gói tin thành công:    {GREEN}{success_count} ({success_rate:.2f}%){RESET}")
    print(f"Số gói tin bị Timeout:    {RED}{timeout_count}{RESET}")
    print(f"Số gói tin lỗi CRC:       {YELLOW}{crc_error_count}{RESET}")
    print(f"Số gói tin lỗi khác:      {RED}{other_error_count}{RESET}")
    
    if error_details:
        print(f"\n{BOLD}Chi tiết các lỗi gặp phải:{RESET}")
        for err, count in error_details.items():
            print(f"  - {err}: {count} lần")
            
    print(f"\n{BOLD}Thông số Độ trễ phản hồi (RTT - Round Trip Time):{RESET}")
    print(f"  - Nhỏ nhất (Min): {min_rtt:.2f} ms")
    print(f"  - Lớn nhất (Max): {max_rtt:.2f} ms")
    print(f"  - Trung bình (Avg): {avg_rtt:.2f} ms")
    print("="*60)
    
    if success_rate >= 99.9:
        print(f"{GREEN}{BOLD}KẾT LUẬN: ĐƯỜNG TRUYỀN MODBUS ĐẠT ĐỘ ỔN ĐỊNH CỰC CAO (Tốt){RESET}")
    elif success_rate >= 95.0:
        print(f"{YELLOW}{BOLD}KẾT LUẬN: ĐƯỜNG TRUYỀN ĐẠT YÊU CẦU NHƯNG VẪN CÓ TỶ LỆ TRONG GIỚI HẠN LỖI (Trung bình){RESET}")
    else:
        print(f"{RED}{BOLD}KẾT LUẬN: ĐƯỜNG TRUYỀN KHÔNG ỔN ĐỊNH! Vui lòng kiểm tra lại nhiễu, phần cứng, DMA hoặc cấu hình UART.{RESET}")
    print("="*60 + "\n")

def main():
    print("="*50)
    print(f"{BOLD}{CYAN}   CÔNG CỤ KIỂM THỬ ĐỘ ỔN ĐỊNH MODBUS RTU MASTER{RESET}")
    print("="*50)
    
    # 1. Nhập cổng
    port = input("Nhập cổng Serial (Mặc định: /dev/ttyUSB0): ").strip()
    if not port:
        port = "/dev/ttyUSB0"
        
    # 2. Nhập ID Slave
    slave_id_str = input("Nhập Slave ID của STM32 (Mặc định: 1): ").strip()
    slave_id = int(slave_id_str) if slave_id_str else 1
    
    # 3. Chọn chế độ
    print("\nChọn chế độ stress test:")
    print("  1. Chỉ Đọc (Read-only stress test) - Đọc liên tục 10 holding register")
    print("  2. Chỉ Ghi (Write-only stress test) - Ghi và đổi trạng thái LED liên tục")
    print("  3. Kết hợp (Read/Write mixed) - Đọc và ghi xen kẽ để thử thách State Machine")
    mode_str = input("Lựa chọn (1-3, Mặc định: 3): ").strip()
    mode = int(mode_str) if mode_str in ['1', '2', '3'] else 3
    
    # 4. Nhập số chu kỳ
    num_cycles_str = input("\nNhập số chu kỳ test (0 = chạy vô hạn cho đến khi dừng): ").strip()
    num_cycles = int(num_cycles_str) if num_cycles_str else 0
    
    # 5. Nhập độ trễ chu kỳ
    interval_str = input("Nhập khoảng thời gian giữa các gói (ms) (Mặc định: 50 ms): ").strip()
    interval_ms = float(interval_str) if interval_str else 50.0
    
    run_stress_test(port, slave_id, mode, num_cycles, interval_ms)

if __name__ == "__main__":
    main()
