import asyncio
import logging
from pymodbus.server import StartAsyncTcpServer
from pymodbus.datastore import ModbusSequentialDataBlock, ModbusSlaveContext, ModbusServerContext

# Bật log để nhìn rõ các gói tin gửi/nhận
logging.basicConfig()
log = logging.getLogger()
log.setLevel(logging.DEBUG)

async def run_server():
    # Khởi tạo bộ nhớ (thanh ghi) cho Slave
    # Khởi tạo Holding Registers có sẵn giá trị 1, 2, 3, 4... để lát nữa test đọc
    store = ModbusSlaveContext(
        di=ModbusSequentialDataBlock(0, [0]*100),
        co=ModbusSequentialDataBlock(0, [0]*100),
        hr=ModbusSequentialDataBlock(0, [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]),
        ir=ModbusSequentialDataBlock(0, [0]*100)
    )
    
    # Gán bộ nhớ này cho con Slave có ID = 3
    context = ModbusServerContext(slaves={3: store}, single=False)
    
    print("==================================================")
    print("Khởi động Modbus Slave Simulator...")
    print("Slave ID: 3")
    print("Giao thức: TCP/IP")
    print("Địa chỉ: 127.0.0.1 (localhost) - Cổng: 5020")
    print("==================================================")
    
    # Chạy Server lắng nghe vô thời hạn
    await StartAsyncTcpServer(context=context, address=("127.0.0.1", 5020))

if __name__ == "__main__":
    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        print("Đã tắt Slave Simulator.")
