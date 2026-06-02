import mysql.connector

# IMPORT TUYỆT ĐỐI: Gọi DB_CONFIG từ file config.py nằm ngoài thư mục gốc
from config import DB_CONFIG 

def get_branch_connection(db_name):
    """
    Ánh xạ động từ tên database phân mảnh (BanHangDaKho_XX) 
    sang key tương ứng trong DB_CONFIG để lấy cấu hình kết nối Docker chuẩn.
    """
    # 1. Tạo một bảng map nhỏ từ tên DB sang key của CONFIG
    name_map = {
        'BanHangDaKho_HN':  'hn',
        'BanHangDaKho_DN':  'dn',
        'BanHangDaKho_HCM': 'hcm'
    }
    
    # 2. Lấy key viết tắt ('hn', 'dn', 'hcm') dựa trên db_name truyền vào
    config_key = name_map.get(db_name)
    
    if not config_key:
        raise ValueError(f"Không tìm thấy cấu hình phù hợp cho tên Database: {db_name}")
        
    # 3. Lấy cụm thông số kết nối (host, port, user, pwd, db) tương ứng
    branch_config = DB_CONFIG[config_key]
    
    try:
        # Giải nén dictionary cấu hình bằng toán tử ** để truyền thẳng vào mysql connect
        connection = mysql.connector.connect(**branch_config)
        return connection
    except mysql.connector.Error as err:
        print(f"🔴 Lỗi kết nối tới node phân mảnh [{db_name}] qua port {branch_config['port']}: {err}")
        raise err