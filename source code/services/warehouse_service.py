from db.connect_hn import get_hn_connection
from db.connect_dn import get_dn_connection
from db.connect_hcm import get_hcm_connection
from db.connect_center import get_center_connection
from datetime import datetime

def _get_branch_connection_by_region(region_name):
    if region_name == 'Hà Nội':
        return get_hn_connection()
    elif region_name == 'Đà Nẵng':
        return get_dn_connection()
    elif region_name == 'TPHCM' or region_name == 'HCM': # Đề phòng bạn truyền 'HCM' hoặc 'TPHCM'
        return get_hcm_connection()
    return None

# ==============================================================================
# TRUY VẤN VỊ TRÍ SẢN PHẨM (XEM TỒN KHO 3 MIỀN)
# ==============================================================================
def find_product_in_warehouses(ma_sp):
    """Quét qua 3 bảng tồn kho phân mảnh để tìm vị trí của một sản phẩm."""
    result = []
    sites = [
        ("Hà Nội", get_hn_connection, "TonKho_HN"),
        ("Đà Nẵng", get_dn_connection, "TonKho_DN"),
        ("TPHCM", get_hcm_connection, "TonKho_HCM")
    ]

    for region, connect_func, table_name in sites:
        try:
            conn = connect_func()
            cursor = conn.cursor(dictionary=True)

            query = f"""
                SELECT %s AS KhuVuc,
                       MaKho,
                       MaSP,
                       SoLuong
                FROM {table_name}
                WHERE MaSP = %s AND SoLuong > 0
            """
            cursor.execute(query, (region, ma_sp))
            result.extend(cursor.fetchall())

            cursor.close()
            conn.close()
        except Exception as e:
            print(f"⚠️ Lỗi tìm sản phẩm tại site {region}: {str(e)}")
            continue

    return result


# ==============================================================================
# QUẢN LÝ DANH MỤC KHO (ĐỌC - THÊM - XÓA TẠI CENTER)
# ==============================================================================
def get_all_warehouses():
    """Lấy danh sách danh mục toàn bộ kho hàng từ DB Trung Tâm."""
    try:
        conn = get_center_connection()
        cursor = conn.cursor(dictionary=True)

        query = "SELECT MaKho, TenKho, KhuVuc, DiaChi FROM Kho ORDER BY MaKho"
        cursor.execute(query)
        result = cursor.fetchall()

        cursor.close()
        conn.close()
        return result
    except Exception as e:
        print(f"⚠️ Lỗi lấy danh sách kho: {str(e)}")
        return []


def add_new_warehouse(ma_kho, ten_kho, khu_vuc, dia_chi):
    """Thêm mới một kho vào danh mục ở DB Trung Tâm và NHÂN BẢN sang TẤT CẢ các chi nhánh."""
    # Danh sách cấu hình kết nối để duyệt qua toàn bộ hệ thống
    all_sites = [
        ("Trung Tâm", get_center_connection),
        ("Hà Nội", get_hn_connection),
        ("Đà Nẵng", get_dn_connection),
        ("TPHCM", get_hcm_connection)
    ]

    opened_connections = []

    try:
        # BƯỚC 1: Kiểm tra trùng mã kho trên DB Trung tâm trước để chặn từ đầu
        center_conn = get_center_connection()
        center_cursor = center_conn.cursor()
        center_cursor.execute("SELECT MaKho FROM Kho WHERE MaKho = %s", (ma_kho,))
        duplicated = center_cursor.fetchone()
        center_cursor.close()
        center_conn.close()

        if duplicated:
            return False, "Mã kho này đã tồn tại trên hệ thống tổng!"

        # BƯỚC 2: Thực thi INSERT trên từng DB (chưa commit ngay)
        query = "INSERT INTO Kho (MaKho, TenKho, KhuVuc, DiaChi) VALUES (%s, %s, %s, %s)"

        for name, connect_func in all_sites:
            conn = connect_func()
            opened_connections.append((name, conn))  # Lưu lại để lát nữa commit hoặc rollback đồng loạt

            cursor = conn.cursor()
            cursor.execute(query, (ma_kho, ten_kho, khu_vuc, dia_chi))
            cursor.close()

        # BƯỚC 3: Nếu tất cả các nơi đều chạy lệnh OK -> Commit đồng loạt
        for name, conn in opened_connections:
            conn.commit()
            conn.close()

        return True, "Thêm danh mục kho thành công và đã đồng bộ nhân bản ra toàn hệ thống (3 miền + trung tâm)!"

    except Exception as e:
        # Nếu bất kỳ site nào bị lỗi (mất kết nối, lỗi CSDL...), lập tức Rollback toàn bộ các site đã mở
        print(f"❌ Lỗi đồng bộ thêm kho hàng phân tán: {str(e)}")
        for name, conn in opened_connections:
            try:
                conn.rollback()
                conn.close()
                print(f"↩️ Đã rollback dữ liệu tại node: {name}")
            except:
                pass
        return False, f"Lỗi đồng bộ nhân bản 3 miền: {str(e)}"


def delete_warehouse(ma_kho, khu_vuc=None):
    """Xóa một kho khỏi DB Trung Tâm và đồng bộ xóa sạch ở TẤT CẢ các chi nhánh."""
    all_sites = [
        ("Trung Tâm", get_center_connection),
        ("Hà Nội", get_hn_connection),
        ("Đà Nẵng", get_dn_connection),
        ("TPHCM", get_hcm_connection)
    ]

    opened_connections = []

    try:
        query = "DELETE FROM Kho WHERE MaKho = %s"

        # Thực thi lệnh DELETE trên toàn bộ 4 database
        for name, connect_func in all_sites:
            conn = connect_func()
            opened_connections.append((name, conn))

            cursor = conn.cursor()
            cursor.execute(query, (ma_kho,))
            cursor.close()

        # Xác nhận lưu thay đổi đồng loạt
        for name, conn in opened_connections:
            conn.commit()
            conn.close()

        return True, "Đã xóa kho và đồng bộ xóa bản sao thành công tại tất cả các node chi nhánh!"

    except Exception as e:
        print(f"❌ Lỗi đồng bộ xóa kho hàng phân tán: {str(e)}")
        for name, conn in opened_connections:
            try:
                conn.rollback()
                conn.close()
            except:
                pass
        return False, f"Lỗi hệ thống phân tán khi xóa: {str(e)}"


# ==============================================================================
# NGHIỆP VỤ NHẬP XUẤT KHO PHÂN MẢNH (ĐƯỢC GỌI BỞI ADMIN TỔNG)
# ==============================================================================
def get_all_transactions():
    """Admin quét qua 3 bảng lịch sử phân mảnh để gom toàn bộ nhật ký nhập xuất."""
    all_tx = []
    sites = [
        ("Hà Nội", get_hn_connection, "NhapXuatKho_HN"),
        ("Đà Nẵng", get_dn_connection, "NhapXuatKho_DN"),
        ("TPHCM", get_hcm_connection, "NhapXuatKho_HCM"),
    ]

    for region, connect_func, table_name in sites:
        try:
            conn = connect_func()
            cursor = conn.cursor(dictionary=True)

            query = f"""
                SELECT MaNX, MaKho, MaSP, LoaiGD, SoLuong, NgayGD, GhiChu 
                FROM {table_name} 
                ORDER BY NgayGD DESC
            """
            cursor.execute(query)
            rows = cursor.fetchall()

            for row in rows:
                row['KhuVuc'] = region  # Đính kèm tên vùng miền để hiển thị lên bảng
                all_tx.append(row)

            cursor.close()
            conn.close()
        except Exception as e:
            print(f"⚠️ Không thể lấy lịch sử từ site {region}: {str(e)}")
            continue

    # Sắp xếp gom lịch sử cả 3 miền theo thời gian mới nhất lên đầu
    all_tx.sort(key=lambda x: x['NgayGD'] if x['NgayGD'] else datetime.min, reverse=True)
    return all_tx


def create_admin_transaction(region, ma_nx, ma_kho, ma_sp, loai_gd, so_luong, ghi_chu):
    """Phát lệnh giao dịch: Cập nhật song song bảng Tồn Kho và bảng Lịch sử tại phân mảnh tương ứng."""

    # Bản đồ ánh xạ: Khu vực -> (Hàm kết nối, Bảng Tồn Kho, Bảng Lịch Sử)
    site_map = {
        'Hà Nội': (get_hn_connection, 'TonKho_HN', 'NhapXuatKho_HN'),
        'Đà Nẵng': (get_dn_connection, 'TonKho_DN', 'NhapXuatKho_DN'),
        'TPHCM': (get_hcm_connection, 'TonKho_HCM', 'NhapXuatKho_HCM')
    }

    if region not in site_map:
        return False, f"Khu vực '{region}' không hợp lệ trên cấu trúc phân mảnh hệ thống!"

    connect_func, tbl_tonkho, tbl_lichsu = site_map[region]

    conn = connect_func()
    cursor = conn.cursor()

    try:
        # Bước 1: Kiểm tra trùng mã giao dịch (MaNX) tại bảng lịch sử phân mảnh của site đó
        query_check_nx = f"SELECT MaNX FROM {tbl_lichsu} WHERE MaNX = %s"
        cursor.execute(query_check_nx, (ma_nx,))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return False, f"Mã giao dịch {ma_nx} đã tồn tại ở phân mảnh {region}!"

        # Bước 2: Cập nhật số lượng vật lý trực tiếp tại bảng TỒN KHO của phân mảnh đó
        if loai_gd == 'NHAP':
            # Nếu chưa có bản ghi sản phẩm tại kho đó -> Insert, có rồi -> Cộng dồn số lượng
            query_update_stock = f"""
                INSERT INTO {tbl_tonkho} (MaKho, MaSP, SoLuong) VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE SoLuong = SoLuong + %s
            """
            cursor.execute(query_update_stock, (ma_kho, ma_sp, int(so_luong), int(so_luong)))

        elif loai_gd == 'XUAT':
            # Kiểm tra lượng hàng hiện tại trong kho xem có đủ xuất không
            query_check_stock = f"SELECT SoLuong FROM {tbl_tonkho} WHERE MaKho = %s AND MaSP = %s"
            cursor.execute(query_check_stock, (ma_kho, ma_sp))
            current_stock = cursor.fetchone()

            if not current_stock or current_stock[0] < int(so_luong):
                stock_available = current_stock[0] if current_stock else 0
                cursor.close()
                conn.close()
                return False, f"Không đủ hàng xuất! Kho ở {region} hiện tại chỉ còn tồn: {stock_available} cái."

            # Tiến hành trừ số lượng hàng trong kho chi nhánh
            query_decrease_stock = f"""
                UPDATE {tbl_tonkho} SET SoLuong = SoLuong - %s
                WHERE MaKho = %s AND MaSP = %s
            """
            cursor.execute(query_decrease_stock, (int(so_luong), ma_kho, ma_sp))

        # Bước 3: Ghi nhận nhật ký chứng từ vào đúng bảng lịch sử của phân mảnh đó
        query_insert_log = f"""
            INSERT INTO {tbl_lichsu} (MaNX, MaKho, MaSP, LoaiGD, SoLuong, NgayGD, GhiChu)
            VALUES (%s, %s, %s, %s, %s, NOW(), %s)
        """
        cursor.execute(query_insert_log, (ma_nx, ma_kho, ma_sp, loai_gd, int(so_luong), ghi_chu))

        # Xác nhận hoàn tất đồng thời cả 2 bảng trên Node
        conn.commit()
        return True, f"Khởi tạo lệnh điều phối và cập nhật kho {region} thành công!"

    except Exception as e:
        conn.rollback()
        print(f"❌ Lỗi MySQL thực tế tại Node {region}: {str(e)}")
        return False, f"Lỗi xảy ra tại CSDL chi nhánh: {str(e)}"

    finally:
        cursor.close()
        conn.close()


def get_branch_transactions(db_name, tbl_nhapxuat, wh_prefix):
    """
    Lấy danh sách lịch sử nhập xuất kho và thông tin bổ trợ (kho, sản phẩm)
    của riêng chi nhánh đang đăng nhập bằng 3 hàm kết nối gốc.
    """
    conn = None
    cursor = None
    try:
        # 1. Rẽ nhánh chọn đúng kết nối gốc
        if db_name == 'BanHangDaKho_HN':
            conn = get_hn_connection()
            region_name = 'Hà Nội'
        elif db_name == 'BanHangDaKho_DN':
            conn = get_dn_connection()
            region_name = 'Đà Nẵng'
        elif db_name == 'BanHangDaKho_HCM':
            conn = get_hcm_connection()
            region_name = 'TPHCM'
        else:
            raise ValueError(f"Tên Database '{db_name}' không hợp lệ!")

        cursor = conn.cursor(dictionary=True)

        # 2. Lấy dữ liệu lịch sử nhập xuất kho (JOIN Kho và SanPham nội bộ node)
        query_tx = f"""
            SELECT nx.*, k.TenKho, s.TenSP
            FROM {tbl_nhapxuat} nx
            INNER JOIN Kho     k ON nx.MaKho = k.MaKho
            INNER JOIN SanPham s ON nx.MaSP  = s.MaSP
            WHERE nx.MaKho LIKE %s
            ORDER BY nx.NgayGD DESC
        """
        cursor.execute(query_tx, (f"{wh_prefix}%",))
        transactions = cursor.fetchall()

        for row in transactions:
            row['KhuVuc'] = region_name

        # 3. Lấy danh sách kho của chi nhánh đó (để hiển thị lên dropdown khi tạo phiếu)
        cursor.execute("SELECT MaKho, TenKho FROM Kho WHERE MaKho LIKE %s ORDER BY TenKho",
                       (f"{wh_prefix}%",))
        warehouses = cursor.fetchall()

        # 4. Lấy danh sách sản phẩm để nhân viên chọn khi tạo phiếu
        cursor.execute("SELECT MaSP, TenSP FROM SanPham ORDER BY TenSP")
        products = cursor.fetchall()

        # Trả về bộ 3 dữ liệu cần thiết cho giao diện
        return transactions, warehouses, products

    except Exception as e:
        print(f"❌ Lỗi lấy lịch sử kho tại Service ({db_name}): {str(e)}")
        raise e

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def create_branch_transaction(db_name, tbl, ma_nx, ma_kho, ma_sp, loai_gd, so_luong, ghi_chu):
    """
    Nhân viên tạo phiếu nhập/xuất kho — thực thi trực tiếp trên Node phân mảnh
    của chi nhánh bằng cách sử dụng chính xác 3 kết nối gốc.
    """
    conn = None
    cursor = None
    try:
        # 1. Rẽ nhánh chọn đúng hàm kết nối gốc dựa vào db_name
        if db_name == 'BanHangDaKho_HN':
            conn = get_hn_connection()
        elif db_name == 'BanHangDaKho_DN':
            conn = get_dn_connection()
        elif db_name == 'BanHangDaKho_HCM':
            conn = get_hcm_connection()
        else:
            return False, f"Tên CSDL chi nhánh '{db_name}' không hợp lệ trên hệ thống!"

        cursor = conn.cursor()

        # 2. Kiểm tra trùng mã phiếu giao dịch (MaNX)
        query_check = f"SELECT MaNX FROM {tbl['nhapxuat']} WHERE MaNX = %s"
        cursor.execute(query_check, (ma_nx,))
        if cursor.fetchone():
            return False, "Mã phiếu giao dịch này đã tồn tại trên chi nhánh!"

        # 3. Cập nhật số lượng vật lý tại bảng TỒN KHO của phân mảnh
        if loai_gd == 'NHAP':
            # Thực hiện kĩ thuật UPSERT (Nếu chưa có hàng -> INSERT mới, có rồi -> CỘNG DỒN)
            query_stock = f"""
                INSERT INTO {tbl['tonkho']} (MaKho, MaSP, SoLuong) VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE SoLuong = SoLuong + VALUES(SoLuong)
            """
            cursor.execute(query_stock, (ma_kho, ma_sp, so_luong))

        elif loai_gd == 'XUAT':
            # Kiểm tra xem lượng tồn thực tế có đủ để trừ không
            query_check_stock = f"SELECT SoLuong FROM {tbl['tonkho']} WHERE MaKho = %s AND MaSP = %s"
            cursor.execute(query_check_stock, (ma_kho, ma_sp))
            row = cursor.fetchone()

            if not row or row[0] < so_luong:
                stock_available = row[0] if row else 0
                return False, f"Số lượng tồn kho không đủ để xuất! Hiện còn: {stock_available}"

            # Tiến hành trừ lượng hàng tồn
            query_sub_stock = f"UPDATE {tbl['tonkho']} SET SoLuong = SoLuong - %s WHERE MaKho = %s AND MaSP = %s"
            cursor.execute(query_sub_stock, (so_luong, ma_kho, ma_sp))

        # 4. Ghi nhận nhật ký chứng từ vào bảng NhapXuatKho_XX tương ứng
        query_log = f"""
            INSERT INTO {tbl['nhapxuat']} (MaNX, MaKho, MaSP, LoaiGD, SoLuong, NgayGD, GhiChu) 
            VALUES (%s, %s, %s, %s, %s, NOW(), %s)
        """
        cursor.execute(query_log, (ma_nx, ma_kho, ma_sp, loai_gd, so_luong, ghi_chu))

        # Xác nhận commit đồng thời giao dịch thành công xuống Node phân mảnh
        conn.commit()
        return True, f"Tạo phiếu {loai_gd.lower()} kho thành công tại chi nhánh!"

    except Exception as e:
        if conn:
            conn.rollback()
        print(f"❌ Lỗi xử lý kho tại Node chi nhánh ({db_name}): {str(e)}")
        return False, f"Lỗi hệ thống CSDL chi nhánh: {str(e)}"

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()