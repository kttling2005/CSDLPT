from db.connect_hn import get_hn_connection
from db.connect_dn import get_dn_connection
from db.connect_hcm import get_hcm_connection

def get_all_inventory():

    all_data = []

    # Hà Nội
    conn_hn = get_hn_connection()
    cursor_hn = conn_hn.cursor(dictionary=True)

    cursor_hn.execute("""
        SELECT 'Hà Nội' AS KhuVuc,
               MaKho,
               MaSP,
               SoLuong
        FROM TonKho_HN
    """)

    all_data.extend(cursor_hn.fetchall())

    conn_hn.close()

    # Đà Nẵng
    conn_dn = get_dn_connection()
    cursor_dn = conn_dn.cursor(dictionary=True)

    cursor_dn.execute("""
        SELECT 'Đà Nẵng' AS KhuVuc,
               MaKho,
               MaSP,
               SoLuong
        FROM TonKho_DN
    """)

    all_data.extend(cursor_dn.fetchall())

    conn_dn.close()

    # HCM
    conn_hcm = get_hcm_connection()
    cursor_hcm = conn_hcm.cursor(dictionary=True)

    cursor_hcm.execute("""
        SELECT 'TPHCM' AS KhuVuc,
               MaKho,
               MaSP,
               SoLuong
        FROM TonKho_HCM
    """)

    all_data.extend(cursor_hcm.fetchall())

    conn_hcm.close()

    return all_data

def check_product_inventory(ma_sp):
    """Hàm kiểm tra số lượng tồn kho của một sản phẩm cụ thể ở cả 3 miền"""
    all_inventory = get_all_inventory()
    # Lọc ra các dòng có mã sản phẩm trùng với ma_sp truyền vào
    result = [item for item in all_inventory if item['MaSP'] == ma_sp]
    return result


def get_branch_inventory(db_name, tbl_tonkho, wh_prefix):
    """
    Truy vấn tồn kho bằng cách sử dụng chính xác 3 hàm kết nối riêng biệt của từng miền.
    """
    conn = None
    cursor = None
    try:
        # Rẽ nhánh chọn đúng hàm kết nối gốc ban đầu theo db_name
        if db_name == 'BanHangDaKho_HN':
            conn = get_hn_connection()
        elif db_name == 'BanHangDaKho_DN':
            conn = get_dn_connection()
        elif db_name == 'BanHangDaKho_HCM':
            conn = get_hcm_connection()
        else:
            raise ValueError(f"Tên Database '{db_name}' không hợp lệ hoặc không được hỗ trợ!")

        cursor = conn.cursor(dictionary=True)

        # Câu lệnh truy vấn SQL lấy dữ liệu từ bảng phân mảnh và JOIN nội bộ node
        query = f"""
            SELECT tk.MaKho, tk.MaSP, tk.SoLuong,
                   k.TenKho, k.KhuVuc,
                   s.TenSP, s.ThuongHieu
            FROM {tbl_tonkho} tk
            INNER JOIN Kho k     ON tk.MaKho = k.MaKho
            INNER JOIN SanPham s ON tk.MaSP  = s.MaSP
            WHERE tk.MaKho LIKE %s
            ORDER BY tk.MaKho, tk.MaSP
        """
        cursor.execute(query, (f"{wh_prefix}%",))
        inventory = cursor.fetchall()
        return inventory

    except Exception as e:
        print(f"❌ Lỗi truy vấn tại tầng Service ({db_name}): {str(e)}")
        raise e

    finally:
        # Luôn luôn giải phóng tài nguyên hệ thống
        if cursor:
            cursor.close()
        if conn:
            conn.close()