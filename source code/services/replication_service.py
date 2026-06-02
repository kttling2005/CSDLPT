# services/replication_service.py

from db.connect_center import get_center_connection
from db.connect_hn import get_hn_connection
from db.connect_dn import get_dn_connection
from db.connect_hcm import get_hcm_connection


# ==============================
# DANH SÁCH SITE ĐÍCH
# ==============================

sites = [
    ("HN", get_hn_connection),
    ("DN", get_dn_connection),
    ("TPHCM", get_hcm_connection)
]


# ==============================
# NHÂN BẢN DANH MỤC
# ==============================

def replicate_categories():

    center_conn = get_center_connection()
    center_cursor = center_conn.cursor(dictionary=True)

    center_cursor.execute("SELECT * FROM DanhMuc")

    categories = center_cursor.fetchall()

    center_cursor.close()
    center_conn.close()

    query = """
        INSERT IGNORE INTO DanhMuc
        (MaDanhMuc, TenDanhMuc, MoTa)
        VALUES (%s, %s, %s)
    """

    for site_name, connect_func in sites:

        conn = None

        try:
            conn = connect_func()
            cursor = conn.cursor()

            for category in categories:

                values = (
                    category["MaDanhMuc"],
                    category["TenDanhMuc"],
                    category["MoTa"]
                )

                cursor.execute(query, values)

            conn.commit()

            print(f"[SUCCESS] DanhMuc -> {site_name}")

        except Exception as e:
            print(f"[ERROR] DanhMuc {site_name}: {e}")

        finally:
            if conn:
                conn.close()


# ==============================
# NHÂN BẢN KHO
# ==============================

def replicate_warehouses():

    center_conn = get_center_connection()
    center_cursor = center_conn.cursor(dictionary=True)

    center_cursor.execute("SELECT * FROM Kho")

    warehouses = center_cursor.fetchall()

    center_cursor.close()
    center_conn.close()

    query = """
        INSERT IGNORE INTO Kho
        (MaKho, TenKho, KhuVuc, DiaChi)
        VALUES (%s, %s, %s, %s)
    """

    for site_name, connect_func in sites:

        conn = None

        try:
            conn = connect_func()
            cursor = conn.cursor()

            for warehouse in warehouses:

                values = (
                    warehouse["MaKho"],
                    warehouse["TenKho"],
                    warehouse["KhuVuc"],
                    warehouse["DiaChi"]
                )

                cursor.execute(query, values)

            conn.commit()

            print(f"[SUCCESS] Kho -> {site_name}")

        except Exception as e:
            print(f"[ERROR] Kho {site_name}: {e}")

        finally:
            if conn:
                conn.close()


# ==============================
# NHÂN BẢN SẢN PHẨM
# ==============================

def replicate_products():

    center_conn = get_center_connection()
    center_cursor = center_conn.cursor(dictionary=True)

    center_cursor.execute("SELECT * FROM SanPham")

    products = center_cursor.fetchall()

    center_cursor.close()
    center_conn.close()
# query 1
    query = """
        INSERT IGNORE INTO SanPham
        (MaSP, TenSP, MaDanhMuc, Gia, MoTa, ThuongHieu)
        VALUES (%s, %s, %s, %s, %s, %s)
    """

    for site_name, connect_func in sites:

        conn = None

        try:
            conn = connect_func()
            cursor = conn.cursor()

            for product in products:

                values = (
                    product["MaSP"],
                    product["TenSP"],
                    product["MaDanhMuc"],
                    product["Gia"],
                    product["MoTa"],
                    product["ThuongHieu"]
                )

                cursor.execute(query, values)

            conn.commit()

            print(f"[SUCCESS] SanPham -> {site_name}")

        except Exception as e:
            print(f"[ERROR] SanPham {site_name}: {e}")

        finally:
            if conn:
                conn.close()


# ==============================
# CHẠY TOÀN BỘ NHÂN BẢN
# ==============================

def replicate_master_data():

    print("===== REPLICATE DANHMUC =====")
    replicate_categories()

    print("\n===== REPLICATE KHO =====")
    replicate_warehouses()

    print("\n===== REPLICATE SANPHAM =====")
    replicate_products()

    print("\n===== DONE =====")