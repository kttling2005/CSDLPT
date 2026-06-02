# services/order_service.py
# Module xử lý đặt hàng phân tán (v3 — dùng schema V3: VARCHAR PK, NguoiDung, SoLuong)
# - Xác định kho ưu tiên theo khu vực khách hàng
# - Nếu kho không đủ hàng → tự động tìm kho khác (tình huống phân tán)
# - Dùng transaction + SELECT FOR UPDATE để đảm bảo không âm tồn kho

import datetime
from db.connect_center import get_center_connection
from db.connect_hn    import get_hn_connection
from db.connect_dn    import get_dn_connection
from db.connect_hcm   import get_hcm_connection
from services.fragmentation_service import get_site_by_region


# ==============================
# CẤU HÌNH SITE
# ==============================

SITE_CONFIG = {
    "HN":  {"connect": get_hn_connection,  "table": "TonKho_HN"},
    "DN":  {"connect": get_dn_connection,  "table": "TonKho_DN"},
    "TPHCM": {"connect": get_hcm_connection, "table": "TonKho_HCM"},
}

# Thứ tự ưu tiên tìm kho khi site chính không đủ hàng
FALLBACK_ORDER = {
    "HN":  ["HN", "DN", "TPHCM"],
    "DN":  ["DN", "HN", "TPHCM"],
    "TPHCM": ["TPHCM", "DN", "HN"],
    None:  ["HN", "DN", "TPHCM"],
}


# ==============================
# LẤY THÔNG TIN KHÁCH HÀNG
# ==============================

def get_customer_info(ma_kh):
    """Lấy thông tin khách hàng từ DB Trung Tâm (bảng NguoiDung)."""
    conn   = get_center_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT MaND, HoTen, KhuVuc FROM NguoiDung WHERE MaND = %s AND VaiTro = 'KhachHang'",
        (ma_kh,)
    )
    customer = cursor.fetchone()
    cursor.close()
    conn.close()
    return customer


# ==============================
# KIỂM TRA TỒN KHO TẠI MỘT SITE
# ==============================

def check_inventory_at_site(site_key, ma_sp):
    """
    Trả về danh sách các kho tại site có sản phẩm MaSP còn hàng.
    Kết quả: [{"MaKho": ..., "SoLuong": ...}, ...]
    """
    cfg = SITE_CONFIG[site_key]
    conn   = cfg["connect"]()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        f"""
        SELECT MaKho, SoLuong
        FROM   {cfg['table']}
        WHERE  MaSP = %s AND SoLuong > 0
        ORDER  BY SoLuong DESC
        """,
        (ma_sp,)
    )
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows


# ==============================
# TÌM KHO ĐỦ HÀNG THEO THỨ TỰ ƯU TIÊN
# ==============================

def allocate_product(ma_sp, so_luong_can, priority_sites):
    """
    Phân bổ số lượng cần cho một sản phẩm từ các site theo thứ tự ưu tiên.

    Trả về:
    - allocations: [{"site": ..., "ma_kho": ..., "so_luong": ...}, ...]
    - con_thieu: số lượng vẫn chưa đáp ứng được
    """
    allocations  = []
    con_thieu    = so_luong_can

    print(f"\n  [PHÂN BỔ] Cần {so_luong_can} x {ma_sp}")

    for site_key in priority_sites:
        if con_thieu <= 0:
            break

        rows = check_inventory_at_site(site_key, ma_sp)

        for row in rows:
            if con_thieu <= 0:
                break

            lay = min(row["SoLuong"], con_thieu)
            allocations.append({
                "site":     site_key,
                "ma_kho":   row["MaKho"],
                "so_luong": lay,
            })
            con_thieu -= lay

            print(f"    → Lấy {lay} từ kho {row['MaKho']} ({site_key}), "
                  f"còn thiếu: {con_thieu}")

    return allocations, con_thieu


# ==============================
# TRỪ TỒN KHO (có transaction + lock)
# ==============================

def hold_inventory(site_key, ma_kho, ma_sp, so_luong):
    """
    Trừ tồn kho tại site với row-level lock (SELECT FOR UPDATE).
    Dùng transaction để tránh race condition / âm kho.
    Trả về True nếu thành công, False nếu thất bại.
    """
    config = SITE_CONFIG[site_key]
    conn   = config["connect"]()
    conn.autocommit = False
    cursor = conn.cursor(dictionary=True)
    table  = config["table"]

    try:
        # Khóa dòng tồn kho trước khi đọc + ghi (tránh âm kho đồng thời)
        cursor.execute(
            f"SELECT SoLuong FROM {table} "
            f"WHERE MaKho = %s AND MaSP = %s FOR UPDATE",
            (ma_kho, ma_sp)
        )
        row = cursor.fetchone()

        if not row or row["SoLuong"] < so_luong:
            conn.rollback()
            print(f"    [LOCK FAIL] {site_key}/kho{ma_kho}/SP{ma_sp}: "
                  f"hàng thực tế không đủ khi lock (còn {row})")
            return False

        cursor.execute(
            f"UPDATE {table} SET SoLuong = SoLuong - %s "
            f"WHERE MaKho = %s AND MaSP = %s",
            (so_luong, ma_kho, ma_sp)
        )
        conn.commit()
        print(f"    [LOCK OK] Đã trừ {so_luong} x {ma_sp} "
              f"tại {site_key}/{ma_kho}")
        return True

    except Exception as e:
        conn.rollback()
        print(f"    [ERROR] hold_inventory {site_key}: {e}")
        return False

    finally:
        cursor.close()
        conn.close()


# ==============================
# GIẢI PHÓNG HÀNG TẠM GIỮ (RELEASE HOLD)
# ==============================

def release_hold(site_key, ma_kho, ma_sp, so_luong):
    """
    Hoàn trả lại số lượng tồn kho tại site khi đặt hàng thất bại/huỷ.
    """
    config = SITE_CONFIG[site_key]
    conn   = config["connect"]()
    cursor = conn.cursor()
    table  = config["table"]

    try:
        cursor.execute(
            f"UPDATE {table} SET SoLuong = SoLuong + %s "
            f"WHERE MaKho = %s AND MaSP = %s",
            (so_luong, ma_kho, ma_sp)
        )
        conn.commit()
        print(f"    [RELEASE OK] Đã trả {so_luong} x {ma_sp} tại {site_key}/{ma_kho}")
    except Exception as e:
        conn.rollback()
        print(f"    [ERROR] release_hold {site_key}: {e}")
    finally:
        cursor.close()
        conn.close()


# ==============================
# TẠO BẢN GHI ĐƠN HÀNG (DB Trung Tâm)
# ==============================

def create_order_record(ma_kh, allocations_by_sp, tong_tien):
    """
    Ghi DonHang + ChiTietDonHang vào DB Trung Tâm.
    allocations_by_sp: {ma_sp: [{"site":..,"ma_kho":..,"so_luong":..,"don_gia":..}, ...]}
    """
    conn  = get_center_connection()
    conn.autocommit = False
    cursor = conn.cursor()

    try:
        # Tạo mã đơn hàng dạng VARCHAR (timestamp kèm microsecond để tránh trùng lặp)
        ma_dh = "DH" + datetime.datetime.now().strftime("%y%m%d%H%M%S%f")

        # Tạo đơn hàng
        cursor.execute(
            """INSERT INTO DonHang (MaDH, MaKH, NgayDat, TrangThai, TongTien)
               VALUES (%s, %s, NOW(), 'ChoXuLy', %s)""",
            (ma_dh, ma_kh, tong_tien)
        )

        # Tạo chi tiết đơn hàng
        for ma_sp, items in allocations_by_sp.items():
            for item in items:
                cursor.execute(
                    """INSERT INTO ChiTietDonHang
                       (MaDH, MaSP, MaKho, SoLuong, DonGia)
                       VALUES (%s, %s, %s, %s, %s)""",
                    (ma_dh, ma_sp, item["ma_kho"],
                     item["so_luong"], item["don_gia"])
                )

        conn.commit()
        print(f"\n  [DB CENTER] Đã tạo đơn hàng {ma_dh} "
              f"— Tổng tiền: {tong_tien:,.0f} VNĐ")
        return ma_dh

    except Exception as e:
        conn.rollback()
        print(f"  [ERROR] Tạo đơn hàng thất bại: {e}")
        return None

    finally:
        cursor.close()
        conn.close()


# ==============================
# LẤY GIÁ SẢN PHẨM
# ==============================

def get_product_price(ma_sp):
    """Lấy giá sản phẩm từ DB Trung Tâm."""
    conn   = get_center_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT Gia FROM SanPham WHERE MaSP = %s", (ma_sp,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return float(row["Gia"]) if row else 0.0


# ==============================
# HÀM CHÍNH: ĐẶT HÀNG
# ==============================

def place_order(ma_kh, items):
    """
    Xử lý đặt hàng phân tán.

    Tham số:
    - ma_kh : mã khách hàng (VD: 'ND003')
    - items  : [{"MaSP": "SP01", "SoLuong": 5}, ...]

    Trả về:
    - ma_dh nếu thành công, None nếu thất bại
    """

    print(f"\n{'='*55}")
    print(f"  ĐẶT HÀNG — Khách: {ma_kh}")
    print(f"{'='*55}")

    # ── Bước 1: Lấy thông tin khách hàng ──────────────────
    customer = get_customer_info(ma_kh)
    if not customer:
        print(f"  [LỖI] Không tìm thấy khách hàng {ma_kh}")
        return None

    khu_vuc  = customer.get("KhuVuc", "")
    site_uu_tien = get_site_by_region(khu_vuc)
    order_sites  = FALLBACK_ORDER.get(site_uu_tien, FALLBACK_ORDER[None])

    print(f"  Khách: {customer['HoTen']} | Khu vực: {khu_vuc}")
    print(f"  Site ưu tiên: {site_uu_tien} | Thứ tự tìm kho: {order_sites}")

    # ── Bước 2: Phân bổ từng sản phẩm ────────────────────
    allocations_by_sp = {}
    tong_tien = 0.0
    co_loi    = False

    for item in items:
        ma_sp     = item["MaSP"]
        so_luong  = item["SoLuong"]
        don_gia   = get_product_price(ma_sp)

        allocs, con_thieu = allocate_product(ma_sp, so_luong, order_sites)

        if con_thieu > 0:
            print(f"\n  [LỖI] Sản phẩm {ma_sp}: "
                  f"toàn hệ thống thiếu {con_thieu} sản phẩm. Huỷ đơn.")
            co_loi = True
            break

        # Gắn đơn giá vào từng dòng phân bổ
        for a in allocs:
            a["don_gia"] = don_gia
            tong_tien   += a["so_luong"] * don_gia

        allocations_by_sp[ma_sp] = allocs

    if co_loi:
        print("  → Đơn hàng bị huỷ. Không trừ tồn kho.\n")
        return None

    # ── Bước 3: Trừ tồn kho (có lock) ────────────────────
    print(f"\n  [BƯỚC 3] Trừ tồn kho (SELECT FOR UPDATE)...")
    held = []

    for ma_sp, allocs in allocations_by_sp.items():
        for a in allocs:
            ok = hold_inventory(a["site"], a["ma_kho"], ma_sp, a["so_luong"])
            if not ok:
                print(f"\n  [LỖI] Không thể trừ kho. Hoàn trả {len(held)} kho đã giữ...")
                for h in held:
                    release_hold(h["site"], h["ma_kho"], h["ma_sp"], h["so_luong"])
                print("  → Đơn hàng bị huỷ.\n")
                return None
            held.append({**a, "ma_sp": ma_sp})

    # ── Bước 4: Ghi đơn hàng vào DB Trung Tâm ────────────
    print(f"\n  [BƯỚC 4] Ghi đơn hàng vào DB Trung Tâm...")
    ma_dh = create_order_record(ma_kh, allocations_by_sp, tong_tien)

    if ma_dh:
        print(f"\n  ✅ ĐẶT HÀNG THÀNH CÔNG — Mã đơn: {ma_dh}")
    else:
        print(f"\n  ❌ Ghi DB thất bại. Hoàn trả hàng tạm giữ...")
        for h in held:
            release_hold(h["site"], h["ma_kho"], h["ma_sp"], h["so_luong"])

    print(f"{'='*55}\n")
    return ma_dh


# ==============================
# CẬP NHẬT TRẠNG THÁI ĐƠN HÀNG
# ==============================

def update_order_status(ma_dh, trang_thai):
    """
    Cập nhật trạng thái đơn hàng tại DB Trung Tâm.
    Các trạng thái hợp lệ: 'ChoXuLy' | 'DangGiao' | 'DaGiao' | 'DaHuy'
    """
    conn   = get_center_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE DonHang SET TrangThai = %s WHERE MaDH = %s",
        (trang_thai, ma_dh)
    )
    conn.commit()
    rows = cursor.rowcount
    cursor.close()
    conn.close()

    if rows:
        print(f"  [OK] Đơn {ma_dh} → trạng thái: {trang_thai}")
    else:
        print(f"  [WARN] Không tìm thấy đơn hàng {ma_dh}")
