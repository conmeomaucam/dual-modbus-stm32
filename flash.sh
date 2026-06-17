#!/bin/bash

# Dừng kịch bản ngay lập tức nếu bất kỳ lệnh nào bị lỗi
set -e

echo "=== 1. Đang tiến hành biên dịch dự án STM32G4... ==="
cmake --build build-arm

echo ""
echo "=== 2. Đang tiến hành nạp code xuống mạch bằng OpenOCD... ==="
echo "Đảm bảo bạn đã cắm ST-Link kết nối với board mạch."

# Chạy OpenOCD để nạp file ELF trực tiếp
# Cấu hình: stlink.cfg làm interface, stm32g4x.cfg làm target chip
if openocd -f interface/stlink.cfg -f target/stm32g4x.cfg -c "program build-arm/g474_modbus_test.elf verify reset exit"; then
    echo ""
    echo "🎉 Nạp code (Flash) thành công! Board đang được reset..."
else
    echo ""
    echo "❌ Lỗi: Không thể kết nối hoặc nạp code bằng OpenOCD."
    echo "💡 Gợi ý xử lý sự cố:"
    echo "  1. Kiểm tra lại kết nối cáp USB ST-Link từ mạch vào máy tính."
    echo "  2. Nếu bị lỗi quyền truy cập USB (Permission denied), hãy chạy thử bằng quyền sudo:"
    echo "     sudo ./flash.sh"
    echo "  3. Hoặc thêm quyền truy cập USB cho tài khoản hiện tại bằng lệnh udev:"
    echo "     sudo cp /usr/share/openocd/contrib/60-openocd.rules /etc/udev/rules.d/ && sudo udevadm control --reload-rules && sudo udevadm trigger"
fi
