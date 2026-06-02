# services/query_service.py
# 5 truy vấn phân tán theo yêu cầu đề bài (liên quan đến đặt hàng / đơn hàng)
#
# Q1 — Sản phẩm còn hàng ở những kho nào (toàn hệ thống)
# Q2 — Tổng tồn kho một sản phẩm trên toàn hệ thống
# Q3 — Doanh thu theo tháng: từng kho & toàn hệ thống
# Q4 — Top sản phẩm bán chạy nhất toàn hệ thống
# Q5 — Đơn hàng có sản phẩm xuất từ nhiều kho khác nhau
# Q6 — Xem tất cả đơn hàng + trạng thái (bonus)
# Q7 — Chi tiết một đơn hàng (bonus)

from db.connect_center import get_center_connection
from db.connect_hn     import get_hn_connection
from db.connect_dn     import get_dn_connection
from db.connect_hcm    import get_hcm_connection


# ─────────────────────────────────────────────
# HELPER
# ─────────────────────────────────────────────

SITE_CONFIG = [
    ("Hà Nội",  get_hn_connection,  "TonKho_HN"),
    ("Đà Nẵng", get_dn_connection,  "TonKho_DN"),
    ("TPHCM",   get_hcm_connection, "TonKho_HCM"),
]


# ─────────────────────────────────────────────
# Q1: Sản phẩm còn hàng ở những kho nào?
# Truy xuất: cả 3 site (HN, ĐN, HCM)
# Tổng hợp: gom kết quả Python-side
# ─────────────────────────────────────────────

def q1_warehouses_with_stock(ma_sp):
    """
    Q1 — Kiểm tra sản phẩm MaSP còn hàng tại những kho nào trên toàn hệ thống.
    Dữ liệu lấy từ: TonKho_HN (site HN), TonKho_DN (site ĐN), TonKho_HCM (site HCM).
    """
    results = []

    for region, connect_func, table in SITE_CONFIG:
        conn   = connect_func()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            f"""
            SELECT %s         AS KhuVuc,
                   tk.MaKho,
                   k.TenKho,
                   tk.MaSP,
                   tk.SoLuong
            FROM {table} tk
            JOIN Kho k ON tk.MaKho = k.MaKho
            WHERE tk.MaSP = %s
              AND tk.SoLuong > 0
            ORDER BY tk.SoLuong DESC
            """,
            (region, ma_sp)
        )
        rows = cursor.fetchall()
        results.extend(rows)
        cursor.close()
        conn.close()

    return results


# ─────────────────────────────────────────────
# Q2: Tổng tồn kho một sản phẩm toàn hệ thống
# Truy xuất: cả 3 site
# Tổng hợp: cộng SoLuong Python-side
# ─────────────────────────────────────────────

def q2_total_stock(ma_sp):
    """
    Q2 — Tính tổng tồn kho của sản phẩm MaSP trên toàn hệ thống.
    Chi tiết theo từng site, tổng cộng cuối cùng.
    """
    summary = []
    grand_total = 0

    for region, connect_func, table in SITE_CONFIG:
        conn   = connect_func()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            f"""
            SELECT %s     AS KhuVuc,
                   MaSP,
                   SUM(SoLuong) AS TongSoLuong
            FROM {table}
            WHERE MaSP = %s
            GROUP BY MaSP
            """,
            (region, ma_sp)
        )
        row = cursor.fetchone()
        cursor.close()
        conn.close()

        if row and row["TongSoLuong"] is not None:
            summary.append(row)
            grand_total += int(row["TongSoLuong"])
        else:
            summary.append({"KhuVuc": region, "MaSP": ma_sp, "TongSoLuong": 0})

    return summary, grand_total


# ─────────────────────────────────────────────
# Q3: Doanh thu theo tháng — từng kho & toàn hệ thống
# Truy xuất: DB Trung Tâm (DonHang + ChiTietDonHang)
# Phân tán: GROUP BY MaKho để phân biệt kho/vùng
# ─────────────────────────────────────────────

def q3_revenue_by_warehouse_and_month():
    """
    Q3 — Thống kê doanh thu theo tháng của từng kho và toàn hệ thống.
    Nguồn: DB Trung Tâm — JOIN DonHang + ChiTietDonHang + Kho.
    """
    conn   = get_center_connection()
    cursor = conn.cursor(dictionary=True)

    # Doanh thu từng kho theo tháng
    cursor.execute(
        """
        SELECT
            DATE_FORMAT(dh.NgayDat, '%Y-%m') AS Thang,
            ct.MaKho,
            k.TenKho,
            k.KhuVuc,
            SUM(ct.SoLuong * ct.DonGia)      AS DoanhThu,
            SUM(ct.SoLuong)                   AS TongSanPhamBan
        FROM DonHang dh
        JOIN ChiTietDonHang ct ON dh.MaDH = ct.MaDH
        JOIN Kho k             ON ct.MaKho = k.MaKho
        WHERE dh.TrangThai != 'DaHuy'
        GROUP BY Thang, ct.MaKho, k.TenKho, k.KhuVuc
        ORDER BY Thang DESC, DoanhThu DESC
        """
    )
    by_warehouse = cursor.fetchall()

    # Doanh thu toàn hệ thống theo tháng
    cursor.execute(
        """
        SELECT
            DATE_FORMAT(dh.NgayDat, '%Y-%m') AS Thang,
            SUM(ct.SoLuong * ct.DonGia)      AS TongDoanhThu,
            SUM(ct.SoLuong)                   AS TongSanPhamBan,
            COUNT(DISTINCT dh.MaDH)           AS SoDonHang
        FROM DonHang dh
        JOIN ChiTietDonHang ct ON dh.MaDH = ct.MaDH
        WHERE dh.TrangThai != 'DaHuy'
        GROUP BY Thang
        ORDER BY Thang DESC
        """
    )
    by_system = cursor.fetchall()

    cursor.close()
    conn.close()
    return by_warehouse, by_system


# ─────────────────────────────────────────────
# Q4: Top sản phẩm bán chạy nhất toàn hệ thống
# Truy xuất: DB Trung Tâm
# Phân tán: tổng hợp từ tất cả đơn hàng tất cả kho
# ─────────────────────────────────────────────

def q4_top_selling_products(top_n=5):
    """
    Q4 — Top N sản phẩm bán chạy nhất toàn hệ thống.
    Nguồn: DB Trung Tâm — JOIN ChiTietDonHang + SanPham.
    """
    conn   = get_center_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT
            ct.MaSP,
            sp.TenSP,
            sp.ThuongHieu,
            SUM(ct.SoLuong)              AS TongBan,
            SUM(ct.SoLuong * ct.DonGia)  AS TongDoanhThu,
            COUNT(DISTINCT ct.MaKho)     AS SoKhoXuat
        FROM ChiTietDonHang ct
        JOIN DonHang dh ON ct.MaDH = dh.MaDH
        JOIN SanPham sp ON ct.MaSP = sp.MaSP
        WHERE dh.TrangThai != 'DaHuy'
        GROUP BY ct.MaSP, sp.TenSP, sp.ThuongHieu
        ORDER BY TongBan DESC
        LIMIT %s
        """,
        (top_n,)
    )
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows


# ─────────────────────────────────────────────
# Q5: Đơn hàng xuất từ nhiều kho khác nhau
# Truy xuất: DB Trung Tâm
# Ý nghĩa: phát hiện đơn hàng phân tán — lấy từ >= 2 kho
# ─────────────────────────────────────────────

def q5_orders_from_multiple_warehouses():
    """
    Q5 — Tìm các đơn hàng có sản phẩm được xuất từ nhiều kho khác nhau.
    Đây là bằng chứng cho tình huống đặt hàng phân tán (kho ưu tiên không đủ).
    """
    conn   = get_center_connection()
    cursor = conn.cursor(dictionary=True)

    # Đơn hàng dùng >= 2 kho
    cursor.execute(
        """
        SELECT
            ct.MaDH,
            dh.TrangThai,
            dh.NgayDat,
            nd.HoTen         AS TenKhachHang,
            nd.KhuVuc,
            COUNT(DISTINCT ct.MaKho)    AS SoKhoXuat,
            GROUP_CONCAT(DISTINCT ct.MaKho ORDER BY ct.MaKho) AS DanhSachKho,
            SUM(ct.SoLuong * ct.DonGia) AS TongTien
        FROM ChiTietDonHang ct
        JOIN DonHang  dh ON ct.MaDH  = dh.MaDH
        JOIN NguoiDung nd ON dh.MaKH = nd.MaND
        GROUP BY ct.MaDH, dh.TrangThai, dh.NgayDat, nd.HoTen, nd.KhuVuc
        HAVING SoKhoXuat >= 2
        ORDER BY SoKhoXuat DESC, dh.NgayDat DESC
        """
    )
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows


# ─────────────────────────────────────────────
# Q6 (bonus): Xem tất cả đơn hàng + trạng thái
# ─────────────────────────────────────────────

def q6_all_orders():
    """
    Q6 — Danh sách tất cả đơn hàng kèm thông tin khách hàng và trạng thái.
    """
    conn   = get_center_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT
            dh.MaDH,
            dh.NgayDat,
            dh.TrangThai,
            dh.TongTien,
            nd.HoTen    AS TenKhachHang,
            nd.KhuVuc
        FROM DonHang dh
        JOIN NguoiDung nd ON dh.MaKH = nd.MaND
        ORDER BY dh.NgayDat DESC
        """
    )
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows


# ─────────────────────────────────────────────
# Q7 (bonus): Chi tiết một đơn hàng
# ─────────────────────────────────────────────

def q7_order_detail(ma_dh):
    """
    Q7 — Xem chi tiết đơn hàng: từng sản phẩm, xuất từ kho nào, số lượng, đơn giá.
    """
    conn   = get_center_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT
            ct.MaDH,
            ct.MaSP,
            sp.TenSP,
            ct.MaKho,
            k.TenKho,
            k.KhuVuc,
            ct.SoLuong,
            ct.DonGia,
            (ct.SoLuong * ct.DonGia) AS ThanhTien
        FROM ChiTietDonHang ct
        JOIN SanPham  sp ON ct.MaSP  = sp.MaSP
        JOIN Kho      k  ON ct.MaKho = k.MaKho
        WHERE ct.MaDH = %s
        ORDER BY ct.MaSP, ct.MaKho
        """,
        (ma_dh,)
    )
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows
