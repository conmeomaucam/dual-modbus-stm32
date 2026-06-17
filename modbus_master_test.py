#!/usr/bin/env python3
import time
import sys

try:
    import serial
except ImportError:
    print("Error: 'pyserial' is not installed. Please run: pip3 install pyserial")
    sys.exit(1)

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

def send_modbus_frame(ser, frame: bytes, response_len: int) -> bytes:
    """Gửi một frame Modbus và nhận phản hồi"""
    # Xóa bộ đệm nhận trước khi gửi
    ser.reset_input_buffer()
    
    # Thêm CRC vào cuối gói tin
    full_frame = frame + calculate_crc(frame)
    
    # Xóa bộ đệm nhận trước khi gửi để tránh đọc nhầm dữ liệu phản hồi cũ bị sót lại
    ser.reset_input_buffer()
    
    print(f"--> Gửi: {full_frame.hex(' ').upper()}")
    ser.write(full_frame)
    ser.flush()
    
    # Chờ phản hồi
    time.sleep(0.15) # Chờ 150ms
    
    # Đọc dữ liệu phản hồi
    rx_data = ser.read(response_len + 2) # Cộng 2 bytes CRC
    if not rx_data:
        print("<-- Lỗi: Không nhận được phản hồi (Timeout)")
        return b""
        
    print(f"<-- Nhận: {rx_data.hex(' ').upper()}")
    
    # Xác thực CRC
    payload = rx_data[:-2]
    received_crc = rx_data[-2:]
    calculated_crc = calculate_crc(payload)
    
    if received_crc != calculated_crc:
        print("<-- Lỗi: Sai mã kiểm lỗi CRC!")
        return b""
        
    return rx_data

def read_holding_registers(ser, slave_id: int, start_addr: int, quantity: int):
    """Gửi lệnh đọc Holding Registers (FC 03)"""
    print(f"\n--- Đọc {quantity} Holding Registers từ địa chỉ {start_addr} (Slave ID: {slave_id}) ---")
    
    # Tạo PDU cho FC 03
    pdu = bytes([
        slave_id,
        0x03,
        (start_addr >> 8) & 0xFF, start_addr & 0xFF,
        (quantity >> 8) & 0xFF, quantity & 0xFF
    ])
    
    # Độ dài mong đợi: 1 byte ID + 1 byte FC + 1 byte ByteCount + (Quantity * 2 bytes)
    expected_len = 3 + (quantity * 2)
    response = send_modbus_frame(ser, pdu, expected_len)
    
    if response:
        byte_count = response[2]
        data = response[3:3+byte_count]
        registers = []
        for i in range(0, byte_count, 2):
            val = (data[i] << 8) | data[i+1]
            registers.append(val)
        print(f"Kết quả phân tích các thanh ghi: {registers}")
        for idx, val in enumerate(registers):
            print(f"  Register {start_addr + idx}: {val} (Hex: 0x{val:04X})")

def write_single_register(ser, slave_id: int, addr: int, value: int):
    """Gửi lệnh ghi Single Register (FC 06)"""
    print(f"\n--- Ghi giá trị 0x{value:04X} vào thanh ghi {addr} (Slave ID: {slave_id}) ---")
    
    # Tạo PDU cho FC 06
    pdu = bytes([
        slave_id,
        0x06,
        (addr >> 8) & 0xFF, addr & 0xFF,
        (value >> 8) & 0xFF, value & 0xFF
    ])
    
    # Độ dài mong đợi của phản hồi FC 06 là 6 bytes (y hệt request)
    response = send_modbus_frame(ser, pdu, 6)
    if response:
        print("Ghi thành công!")

def main():
    # Chọn cổng Serial
    port = input("Nhập cổng Serial (Mặc định: /dev/ttyUSB0): ").strip()
    if not port:
        port = "/dev/ttyUSB0"
        
    slave_id_str = input("Nhập Slave ID của STM32 (Mặc định: 1): ").strip()
    slave_id = int(slave_id_str) if slave_id_str else 1
    
    print(f"Đang mở cổng {port} cấu hình 115200, Even Parity...")
    try:
        ser = serial.Serial(
            port=port,
            baudrate=115200,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_EVEN,
            stopbits=serial.STOPBITS_ONE,
            timeout=1.0
        )
    except Exception as e:
        print(f"Lỗi: Không thể mở cổng Serial {port}. Chi tiết: {e}")
        print("Gợi ý: Cắm USB-to-RS485 vào và kiểm tra quyền truy cập (sudo chmod 666 /dev/ttyUSB0)")
        sys.exit(1)
        
    try:
        while True:
            print("\n================ MENU TESTING ================")
            print("1. Đọc 10 Holding Registers đầu tiên (FC 03)")
            print("2. Bật LED PC13 (Ghi 1 vào thanh ghi 3)")
            print("3. Tắt LED PC13 (Ghi 0 vào thanh ghi 3)")
            print("4. Ghi giá trị bất kỳ vào thanh ghi bất kỳ")
            print("5. Thoát")
            choice = input("Chọn chức năng (1-5): ").strip()
            
            if choice == '1':
                read_holding_registers(ser, slave_id, 0, 10)
            elif choice == '2':
                write_single_register(ser, slave_id, 3, 1)
            elif choice == '3':
                write_single_register(ser, slave_id, 3, 0)
            elif choice == '4':
                try:
                    addr = int(input("Nhập địa chỉ thanh ghi: "))
                    val = int(input("Nhập giá trị cần ghi: "))
                    write_single_register(ser, slave_id, addr, val)
                except ValueError:
                    print("Lỗi: Giá trị nhập vào phải là số!")
            elif choice == '5':
                break
            else:
                print("Lựa chọn không hợp lệ!")
                
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nĐã dừng chương trình.")
    finally:
        ser.close()
        print("Đã đóng cổng Serial.")

if __name__ == "__main__":
    main()
