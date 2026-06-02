from db.connect_center import get_center_connection
from db.connect_hn import get_hn_connection
from db.connect_dn import get_dn_connection
from db.connect_hcm import get_hcm_connection
from services.warehouse_service import get_all_warehouses

def get_revenue_by_system():
    """1. Thống kê doanh thu và đơn hàng TOÀN HỆ THỐNG (Không tính đơn hủy)"""
    conn = get_center_connection()
    # Sử dụng dictionary=True để trả về dạng key-value dễ dùng ở giao diện
    cursor = conn.cursor(dictionary=True)

    query = """
        SELECT 
            COUNT(MaDH) AS TongDonHang,
            IFNULL(SUM(TongTien), 0) AS TongDoanhThu
        FROM DonHang
        WHERE TrangThai != 'DaHuy'
    """
    cursor.execute(query)
    result = cursor.fetchone()

    cursor.close()
    conn.close()
    return result


def get_revenue_by_region():
    """2. Thống kê doanh thu theo VÙNG MIỀN (Dựa trên địa chỉ khách hàng KhuVuc)"""
    conn = get_center_connection()
    cursor = conn.cursor(dictionary=True)

    query = """
        SELECT 
            nd.KhuVuc AS VungMien,
            COUNT(dh.MaDH) AS SoDonHang,
            IFNULL(SUM(dh.TongTien), 0) AS DoanhThuVung
        FROM DonHang dh
        JOIN NguoiDung nd ON dh.MaKH = nd.MaND
        WHERE dh.TrangThai != 'DaHuy'
        GROUP BY nd.KhuVuc
        ORDER BY DoanhThuVung DESC
    """
    cursor.execute(query)
    results = cursor.fetchall()

    cursor.close()
    conn.close()
    return results

def get_revenue_by_warehouse():
    """3. Thống kê doanh thu thực tế theo TỪNG KHO HÀNG (Lấy trực tiếp từ Center)"""
    # Bước 1: Lấy danh mục Kho từ Center làm gốc
    warehouses = get_all_warehouses()
    if not warehouses:
        return []

    # Bước 2: Lấy dữ liệu doanh thu đơn hàng tập trung tại Center
    warehouse_stats = {}
    try:
        conn = get_center_connection()
        cursor = conn.cursor(dictionary=True)

        # Lấy doanh thu từ các đơn hàng hợp lệ (bỏ đơn hủy) trực tiếp tại DB Center
        query = """
            SELECT 
                ct.MaKho, 
                COUNT(DISTINCT ct.MaDH) AS SoDon, 
                SUM(ct.SoLuong * ct.DonGia) AS DoanhThu
            FROM ChiTietDonHang ct
            JOIN DonHang dh ON ct.MaDH = dh.MaDH
            WHERE dh.TrangThai != 'DaHuy'
            GROUP BY ct.MaKho
        """
        cursor.execute(query)
        rows = cursor.fetchall()

        for row in rows:
            ma_kho = row['MaKho']
            warehouse_stats[ma_kho] = {
                'SoDonHang': int(row['SoDon']),
                'DoanhThuKho': float(row['DoanhThu'])
            }

        cursor.close()
        conn.close()
    except Exception as e:
        print(f"⚠️ Lỗi khi truy vấn doanh thu kho tại Center: {str(e)}")

    # Bước 3: Ráp dữ liệu với danh mục kho động
    final_result = []
    for wh in warehouses:
        ma_kho = wh['MaKho']
        stats = warehouse_stats.get(ma_kho, {'SoDonHang': 0, 'DoanhThuKho': 0.0})

        final_result.append({
            'MaKho': ma_kho,
            'TenKho': wh['TenKho'],
            'SoDonHang': stats['SoDonHang'],
            'DoanhThuKho': stats['DoanhThuKho']
        })

    # Sắp xếp theo doanh thu giảm dần
    final_result.sort(key=lambda x: x['DoanhThuKho'], reverse=True)
    return final_result

def get_total_revenue():
    conn = get_center_connection()
    cursor = conn.cursor()

    query = """
        SELECT SUM(TongTien)
        FROM DonHang
        WHERE TrangThai != 'DaHuy'
    """

    cursor.execute(query)
    result = cursor.fetchone()

    cursor.close()
    conn.close()

    return result[0] if result[0] else 0


def get_top_selling_products(limit=5):
    conn = get_center_connection()
    cursor = conn.cursor()

    query = """
        SELECT 
            ct.MaSP,
            sp.TenSP,
            SUM(ct.SoLuong) AS TongDaBan
        FROM ChiTietDonHang ct
        JOIN DonHang dh ON ct.MaDH = dh.MaKH
        JOIN SanPham sp ON ct.MaSP = sp.MaSP
        WHERE dh.TrangThai != 'DaHuy'
        GROUP BY ct.MaSP, sp.TenSP
        ORDER BY TongDaBan DESC
        LIMIT %s
    """

    cursor.execute(query, (limit,))
    results = cursor.fetchall()

    cursor.close()
    conn.close()

    return results


def get_orders_by_region():
    conn = get_center_connection()
    cursor = conn.cursor()

    query = """
        SELECT 
            nd.KhuVuc,
            COUNT(dh.MaDH) AS SoDon
        FROM DonHang dh
        JOIN NguoiDung nd ON dh.MaKH = nd.MaND
        GROUP BY nd.KhuVuc
        ORDER BY SoDon DESC
    """

    cursor.execute(query)
    results = cursor.fetchall()

    cursor.close()
    conn.close()

    return results


def get_inventory_summary():
    all_inventory = []

    sites = [
        ("HN", get_hn_connection(), "TonKho_HN"),
        ("DN", get_dn_connection(), "TonKho_DN"),
        ("HCM", get_hcm_connection(), "TonKho_HCM"),
    ]

    for site_name, conn, table_name in sites:
        cursor = conn.cursor()

        query = f"""
            SELECT 
                tk.MaSP,
                sp.TenSP,
                SUM(tk.SoLuong) AS TongTon
            FROM {table_name} tk
            JOIN SanPham sp ON tk.MaSP = sp.MaSP
            GROUP BY tk.MaSP, sp.TenSP
        """

        cursor.execute(query)
        results = cursor.fetchall()
        all_inventory.extend(results)

        cursor.close()
        conn.close()

    summary = {}

    for ma_sp, ten_sp, so_luong in all_inventory:
        if ma_sp not in summary:
            summary[ma_sp] = {
                "ten_sp": ten_sp,
                "tong_ton": 0
            }

        summary[ma_sp]["tong_ton"] += so_luong

    return summary

def get_low_stock_products(threshold=20):
    low_stock = []

    sites = [
        ("HN", get_hn_connection(), "TonKho_HN"),
        ("DN", get_dn_connection(), "TonKho_DN"),
        ("HCM", get_hcm_connection(), "TonKho_HCM"),
    ]

    for site_name, conn, table_name in sites:
        cursor = conn.cursor()

        query = f"""
            SELECT
                tk.MaKho,
                tk.MaSP,
                sp.TenSP,
                tk.SoLuong
            FROM {table_name} tk
            JOIN SanPham sp ON tk.MaSP = sp.MaSP
            WHERE tk.SoLuong <= %s
            ORDER BY tk.SoLuong ASC
        """

        cursor.execute(query, (threshold,))
        results = cursor.fetchall()

        for row in results:
            low_stock.append((site_name, *row))

        cursor.close()
        conn.close()

    return low_stock