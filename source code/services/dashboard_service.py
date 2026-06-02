from db.connect_center import get_center_connection
from db.connect_hn import get_hn_connection
from db.connect_dn import get_dn_connection
from db.connect_hcm import get_hcm_connection


def get_dashboard_stats():
    """
    Hàm tổng hợp số liệu thống kê hiển thị lên trang chủ (Dashboard)
    """
    stats = {
        "total_orders": 0,
        "total_revenue": 0.0,
        "total_customers": 0,
        "total_products_in_stock": 0
    }

    try:
        # 1. Lấy tổng số đơn và doanh thu từ DB Trung Tâm
        conn_center = get_center_connection()
        cursor_center = conn_center.cursor(dictionary=True)

        # Đếm số đơn hàng
        cursor_center.execute("SELECT COUNT(*) AS total FROM DonHang")
        stats["total_orders"] = cursor_center.fetchone()["total"] or 0

        # Tính tổng doanh thu
        cursor_center.execute("SELECT SUM(TongTien) AS total_rev FROM DonHang WHERE TrangThai != 'DaHuy'")
        stats["total_revenue"] = cursor_center.fetchone()["total_rev"] or 0.0

        # Đếm tổng số khách hàng
        cursor_center.execute("SELECT COUNT(*) AS total_cust FROM NguoiDung WHERE VaiTro = 'KhachHang'")
        stats["total_customers"] = cursor_center.fetchone()["total_cust"] or 0

        cursor_center.close()
        conn_center.close()

        # 2. Gom tổng số lượng tồn kho từ 3 site miền
        sites = [get_hn_connection, get_dn_connection, get_hcm_connection]
        tables = ["TonKho_HN", "TonKho_DN", "TonKho_HCM"]

        for get_conn, table in zip(sites, tables):
            try:
                conn = get_conn()
                cursor = conn.cursor(dictionary=True)
                cursor.execute(f"SELECT SUM(SoLuong) AS total_stock FROM {table}")
                res = cursor.fetchone()
                if res and res["total_stock"]:
                    stats["total_products_in_stock"] += int(res["total_stock"])
                cursor.close()
                conn.close()
            except Exception as e:
                print(f"[Dashboard] Lỗi lấy dữ liệu từ {table}: {e}")

    except Exception as e:
        print(f"[Dashboard Lỗi tổng thể]: {e}")

    return stats