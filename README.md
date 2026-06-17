 STM32G4 Dual Modbus RTU Slaves with Software Half-Duplex

Dự án mẫu triển khai **2 Modbus RTU Slave độc lập** chạy đồng thời trên vi điều khiển **STM32G474RET6U** thông qua 2 cổng bộ USART phần cứng (USART1 và USART3), kết hợp giải pháp **Software Half-Duplex (chuyển đổi chân TX động)** giúp ghép chung bus TTL truyền nhận về 1 mạch chuyển đổi USB-to-UART (YP-05) mà không cần thêm linh kiện bên ngoài.

---

## 📌 Tính năng nổi bật
* **Dual Modbus Slave:** Chạy song song 2 Slave ID độc lập (ID 1 trên USART3 và ID 2 trên USART1) sử dụng chung một thư viện công nghiệp **Agile Modbus**.
* **DMA RX + USART IDLE Interrupt:** Tự động thu nhận gói tin Modbus RTU độ dài bất kỳ thông qua DMA dạng vòng (Circular) phối hợp với ngắt dòng nghỉ (IDLE Line Detection) giúp giải phóng tối đa tài nguyên CPU.
* **Software Half-Duplex (Dynamic Pin Control):** Giải pháp chuyển đổi chế độ chân TX phần cứng tự động bằng phần mềm:
  - Khi rảnh: Chân TX ở chế độ `Input High-Z` (Trở kháng cao) để giải phóng đường truyền bus chung.
  - Khi phát phản hồi: Chân TX tự động chuyển sang `Alternate Function Push-Pull` để truyền tín hiệu khỏe, rõ nét ở tốc độ cao **115200 bps**.
  - Truyền xong: Ngay lập tức quay về `Input` để tránh xung đột chập chân phát với Slave khác.
* **Master Testing Suite:** Đi kèm bộ công cụ kiểm thử tự động và tương tác thủ công bằng Python.
* **Virtual Slave Simulator:** Mô phỏng thêm Slave thứ 3 (ID 3) qua TCP trên PC.

---

## 🔌 Sơ đồ kết nối phần cứng (Wiring)

Để kết nối đồng thời cả 2 Slave trên STM32G4 về 1 mạch USB-to-UART (YP-05) cắm vào máy tính, đấu nối dây theo nguyên tắc chéo đầu như sau:

| Tín hiệu PC (YP-05) | Tín hiệu STM32G4 | Cổng UART tương ứng | Vai trò |
| :--- | :--- | :--- | :--- |
| **TX** | **PC11** | USART3_RX (Slave 1) | PC truyền -> STM32 nhận |
| **TX** | **PC5** | USART1_RX (Slave 2) | PC truyền -> STM32 nhận |
| **RX** | **PC10** | USART3_TX (Slave 1) | STM32 phản hồi -> PC nhận |
| **RX** | **PC4** | USART1_TX (Slave 2) | STM32 phản hồi -> PC nhận |
| **GND** | **GND** | Ground chung | Nối đất |

*Lưu ý: Chân debug `printf` log của mạch được gán cứng qua ST-Link Virtual COM Port (USART2 - chân PA2/PA3).*

---

## 📁 Cấu trúc thư mục dự án

```text
portingrtu/
├── g474_modbus_test/           # Source code Firmware STM32G4 (CMake project)
│   ├── Core/
│   │   ├── Src/
│   │   │   ├── main.c              # Hàm main điều khiển chính & khởi tạo
│   │   │   ├── modbus_adapter_stm32g4.c # Triển khai Agile Modbus Adapter & Loop xử lý
│   │   │   └── stm32g4xx_hal_msp.c  # Khởi tạo chân GPIO & DMA cho USART1/3
│   │   └── Inc/
│   │       └── ringbuffer.h        # Cấu trúc bộ đệm vòng (Ring Buffer) nhận gói tin
│   ├── Agile_Modbus/           # Thư viện Agile Modbus tích hợp nhúng
│   └── CMakeLists.txt          # File build CMake chính cho vi điều khiển
├── test_dual_slaves.py         # Script Python chạy kiểm thử tự động cả 2 Slave
├── modbus_master_test.py       # Script Python giả lập Master có Menu tương tác thủ công
├── virtual_slave.py            # Script giả lập Slave ID 3 chạy ngầm trên PC qua TCP
└── README.md                   # Hướng dẫn sử dụng dự án
```

---

## 🚀 Hướng dẫn sử dụng

### 1. Biên dịch và Nạp firmware xuống STM32G4
Mở Terminal tại thư mục `g474_modbus_test/` và thực hiện các lệnh sau:

```bash
# Tạo thư mục build và cấu hình cmake
cmake -B build -G "Unix Makefiles"

# Biên dịch chương trình
cmake --build build -j$(nproc)

# Nạp file binary xuống mạch thông qua st-flash (ST-Link v2)
st-flash write build/g474_modbus_test.bin 0x08000000

# Reset mạch để bắt đầu chạy
st-flash reset
```

---

### 2. Cài đặt môi trường kiểm thử trên PC
Chương trình kiểm thử yêu cầu môi trường Python 3 và các thư viện hỗ trợ:

```bash
# Cài đặt thư viện giao tiếp nối tiếp và Modbus
pip install pyserial pymodbus
```

---

### 3. Chạy kiểm thử tự động (Auto Test)
Kết nối mạch YP-05 vào máy tính và chạy script tự động để kiểm tra khả năng phản hồi của cả 2 Slave:

```bash
python3 test_dual_slaves.py
```
*Script sẽ tự động gửi gói tin đọc thanh ghi (Function Code 03) và ghi lệnh điều khiển LED (Function Code 06) xuống cả 2 Slave ID 1 & 2.*

---

### 4. Chạy kiểm thử tương tác thủ công (Interactive Test)
Chạy script tương tác bằng Menu để điều khiển trạng thái bật/tắt LED hoặc ghi giá trị bất kỳ:

```bash
python3 modbus_master_test.py
```
*Nhập cổng Serial tương ứng (Ví dụ `/dev/ttyUSB0`) và chọn Slave ID muốn tương tác.*

---

### 5. Sử dụng Modbus Slave Simulator qua TCP (Slave ID 3)
Để kiểm tra việc tích hợp thêm Slave ảo trên PC, chạy script:

```bash
python3 virtual_slave.py
```
*Màn hình log sẽ hiển thị chi tiết các gói tin trao đổi Modbus TCP trên cổng 5020.*

---

## 🛠 Giải pháp phần mềm chi tiết

### 🔄 Thu nhận gói tin (DMA RX + USART IDLE)
Hệ thống sử dụng bộ đệm vòng `RingBuffer` để lưu trữ dữ liệu truyền nhận bất đồng bộ. Khi đường truyền UART rơi vào trạng thái nghỉ (IDLE) tối thiểu 1 frame truyền, ngắt IDLE sẽ kích hoạt và thực hiện tính toán số byte đã nhận được từ bộ đếm DMA NDTR:

```c
// Xử lý trong stm32g4xx_it.c
if (__HAL_UART_GET_FLAG(&huart3, UART_FLAG_IDLE) != RESET) {
    __HAL_UART_CLEAR_IDLEFLAG(&huart3);
    uint32_t curr_rx_pos = RX_DMA_BUF_SIZE - __HAL_DMA_GET_COUNTER(huart3.hdmarx);
    // Tính toán độ dài bytes và nạp dữ liệu vào RingBuffer
    ...
}
```

### ⚡ Chuyển chân phát động (Dynamic TX Switching)
Mỗi khi cần gửi gói tin phản hồi về Master, chân TX của USART tương ứng được chuyển đổi trạng thái:

```c
/* Bước 1: Chuyển chân sang chế độ Push-Pull phát tín hiệu cực khỏe */
GPIO_InitStruct.Pin = GPIO_PIN_10;
GPIO_InitStruct.Mode = GPIO_MODE_AF_PP;
HAL_GPIO_Init(GPIOC, &GPIO_InitStruct);

/* Bước 2: Phát dữ liệu */
HAL_UART_Transmit(&huart3, send_buf, send_len, 100);

/* Bước 3: Trả chân về lại trạng thái INPUT High-Z để giải phóng Bus */
GPIO_InitStruct.Mode = GPIO_MODE_INPUT;
GPIO_InitStruct.Pull = GPIO_PULLUP;
HAL_GPIO_Init(GPIOC, &GPIO_InitStruct);
```
