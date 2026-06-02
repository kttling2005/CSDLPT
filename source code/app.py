from flask import Blueprint, Flask, render_template, jsonify, request, redirect, url_for, session, flash
from db.connect_center import get_center_connection
from db.connect_branch import get_branch_connection   # <-- helper mới (xem bên dưới)
from functools import wraps
import threading
import time

from services.inventory_service import (
    get_all_inventory,
    check_product_inventory,
    get_branch_inventory
)

from services.query_service import (
    q1_warehouses_with_stock,
    q5_orders_from_multiple_warehouses,
    q6_all_orders,
    q4_top_selling_products,
    q2_total_stock
)

from services.order_service import (
    place_order
)

from services.dashboard_service import (
    get_dashboard_stats
)

from services.statistics_service import (
    get_revenue_by_system,
    get_revenue_by_region,
    get_revenue_by_warehouse
)

from services.warehouse_service import (
    get_all_warehouses,
    add_new_warehouse,
    delete_warehouse,
    get_all_transactions,
    create_admin_transaction,
    get_branch_transactions,
    create_branch_transaction
)

app = Flask(__name__)
app.secret_key = 'csdlpt_123'

# ==========================================
# ÁNH XẠ KHU VỰC → TÊN DATABASE PHÂN MẢNH
# ==========================================
# Mỗi chi nhánh tương ứng với một DB riêng biệt trên MySQL node của nó.
# get_branch_connection(db_name) sẽ chọn đúng host theo prefix DB.
REGION_DB_MAP = {
    'Hà Nội':  'BanHangDaKho_HN',
    'Đà Nẵng': 'BanHangDaKho_DN',
    'TPHCM':     'BanHangDaKho_HCM',
}

# Tên bảng TonKho và NhapXuatKho khác nhau theo phân mảnh
REGION_TABLE_MAP = {
    'BanHangDaKho_HN':  {'tonkho': 'TonKho_HN',  'nhapxuat': 'NhapXuatKho_HN'},
    'BanHangDaKho_DN':  {'tonkho': 'TonKho_DN',  'nhapxuat': 'NhapXuatKho_DN'},
    'BanHangDaKho_HCM': {'tonkho': 'TonKho_HCM', 'nhapxuat': 'NhapXuatKho_HCM'},
}

# Prefix kho hàng thuộc từng chi nhánh (dùng để lọc đơn hàng)
REGION_WAREHOUSE_PREFIX = {
    'BanHangDaKho_HN':  'KH_HN',
    'BanHangDaKho_DN':  'KH_DN',
    'BanHangDaKho_HCM': 'KH_HCM',
}


def get_staff_db():
    """Trả về tên database phân mảnh của nhân viên đang đăng nhập."""
    region = session['user'].get('region', '')
    return REGION_DB_MAP.get(region)


# ==========================================
# DECORATORS BẢO MẬT
# ==========================================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            if request.path.startswith('/api/'):
                return jsonify({"success": False,
                                "message": "Bạn chưa đăng nhập hoặc phiên làm việc đã hết hạn!"}), 401
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def role_required(allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user' not in session:
                return redirect(url_for('login'))
            user_role = session['user'].get('role')
            if user_role not in allowed_roles:
                flash(f"Bạn không có quyền truy cập trang này (Yêu cầu: {', '.join(allowed_roles)})", "danger")
                # Trả user về đúng trang của họ dựa trên vai trò, tránh đi qua trang index gây lặp
                if user_role == 'Admin':
                    return redirect(url_for('admin_dashboard'))
                elif user_role == 'NhanVien':
                    return redirect(url_for('staff_dashboard'))
                else:
                    return redirect(url_for('customer_home'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def branch_required(f):
    """Decorator riêng cho nhân viên: kiểm tra đăng nhập + có khu vực hợp lệ."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            if request.path.startswith('/api/'):
                return jsonify({"success": False, "message": "Chưa đăng nhập!"}), 401
            return redirect(url_for('login'))
        if session['user'].get('role') != 'NhanVien':
            flash("Trang này chỉ dành cho Nhân viên chi nhánh.", "danger")
            # Nếu sai quyền, đá thẳng về đúng trang tương ứng, tuyệt đối không dùng url_for('index')
            user_role = session['user'].get('role')
            if user_role == 'Admin':
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('customer_home'))
        if not get_staff_db():
            flash("Tài khoản nhân viên chưa được gán khu vực chi nhánh hợp lệ!", "danger")
            session.clear()
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


# =========================
# ĐĂNG NHẬP / ĐĂNG XUẤT
# =========================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user' in session:
        return redirect(url_for('index'))

    if request.method == 'POST':
        email    = request.form.get('email')
        password = request.form.get('password')

        conn   = get_center_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM NguoiDung WHERE Email = %s AND MatKhau = %s", (email, password))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user:
            session['user'] = {
                'id':     user.get('MaND'),
                'name':   user.get('HoTen'),
                'role':   user.get('VaiTro'),
                # Lưu khu vực để nhân viên biết mình thuộc chi nhánh nào
                'region': user.get('KhuVuc', ''),
            }
            role = user.get('VaiTro')
            if role == 'Admin':
                return redirect(url_for('admin_dashboard'))
            elif role == 'NhanVien':
                return redirect(url_for('staff_dashboard'))
            else:
                return redirect(url_for('customer_home'))
        else:
            flash('Email hoặc mật khẩu không chính xác!', 'danger')
            return render_template('login.html')

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))


# =========================
# ĐIỀU HƯỚNG TRANG CHỦ
# =========================

@app.route('/')
@login_required
def index():
    role = session['user'].get('role')
    if role == 'Admin':
        return redirect(url_for('admin_dashboard'))
    elif role == 'NhanVien':
        return redirect(url_for('staff_dashboard'))
    elif role == 'KhachHang':
        return redirect(url_for('customer_home'))
    else:
        return render_template('index.html', stats=get_dashboard_stats())


# =========================
# TRANG NHÂN VIÊN CHI NHÁNH
# =========================

@app.route('/staff/dashboard')
@branch_required
def staff_dashboard():
    """Trang tổng quan của nhân viên — hiển thị tóm tắt tồn kho chi nhánh."""
    db_name   = get_staff_db()
    tbl       = REGION_TABLE_MAP[db_name]
    wh_prefix = REGION_WAREHOUSE_PREFIX[db_name]

    try:
        conn   = get_branch_connection(db_name)
        cursor = conn.cursor(dictionary=True)

        # Tổng số bản ghi tồn kho của chi nhánh
        cursor.execute(f"SELECT COUNT(*) AS total FROM {tbl['tonkho']}")
        total_stock_rows = cursor.fetchone()['total']

        # Tổng số lượng hàng tồn
        cursor.execute(f"SELECT COALESCE(SUM(SoLuong), 0) AS total FROM {tbl['tonkho']}")
        total_qty = cursor.fetchone()['total']

        # Số phiếu nhập/xuất của chi nhánh
        cursor.execute(f"SELECT COUNT(*) AS total FROM {tbl['nhapxuat']}")
        total_tx = cursor.fetchone()['total']

        cursor.close()
        conn.close()

        stats = {
            'total_stock_rows': total_stock_rows,
            'total_qty':        total_qty,
            'total_tx':         total_tx,
            'region':           session['user'].get('region'),
            'db_name':          db_name,
        }
        return render_template('staff/dashboard.html', stats=stats)
    except Exception as e:
        return _err(e)


# ── 1. Khách hàng chi nhánh ──────────────────────────────────────────────────

@app.route('/staff/customers')
@branch_required
def staff_customers():
    """Danh sách khách hàng thuộc khu vực chi nhánh của nhân viên."""
    region = session['user'].get('region')
    try:
        conn   = get_center_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT MaND, HoTen, Email, KhuVuc "
            "FROM NguoiDung WHERE VaiTro = 'KhachHang' AND KhuVuc = %s "
            "ORDER BY HoTen ASC",
            (region,)
        )
        customers = cursor.fetchall()
        cursor.close()
        conn.close()
        return render_template('staff/customers.html', customers=customers)
    except Exception as e:
        flash(f"Lỗi tải danh sách khách hàng: {str(e)}", "danger")
        return redirect(url_for('staff_dashboard'))


@app.route('/api/staff/customers', methods=['POST'])
@branch_required
def api_add_customer():
    try:
        # Lấy khu vực trực tiếp từ session của nhân viên đang đăng nhập
        staff_region = session['user'].get('region')

        if not staff_region:
            return jsonify({
                "success": False,
                "message": "Không xác định được khu vực của nhân viên. Vui lòng đăng nhập lại!"
            }), 403

        data = request.get_json() or {}
        mand = data.get('mand', '').strip().upper()
        hoten = data.get('hoten', '').strip()
        email = data.get('email', '').strip()
        matkhau = data.get('matkhau', '').strip() or '123456'

        # Kiểm tra validation (Bỏ qua kiểm tra khuvuc từ client gửi lên)
        if not mand or not hoten or not email:
            return jsonify({"success": False, "message": "Vui lòng điền đầy đủ thông tin bắt buộc!"}), 400

        if len(mand) > 10:
            return jsonify({"success": False, "message": "Mã số khách hàng tối đa 10 ký tự!"}), 400

        conn = get_center_connection()
        cursor = conn.cursor(dictionary=True)

        # 1. Kiểm tra trùng mã số khách hàng
        cursor.execute("SELECT MaND FROM NguoiDung WHERE MaND = %s", (mand,))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({"success": False, "message": f"Mã số '{mand}' đã tồn tại!"}), 400

        # 2. Kiểm tra trùng Email
        cursor.execute("SELECT MaND FROM NguoiDung WHERE Email = %s", (email,))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({"success": False, "message": f"Email '{email}' đã được đăng ký!"}), 400

        # 3. Thực hiện INSERT - Ghi nhận khu vực bằng 'staff_region' lấy từ session
        insert_query = """
            INSERT INTO NguoiDung (MaND, Email, MatKhau, HoTen, KhuVuc, VaiTro, TrangThai)
            VALUES (%s, %s, %s, %s, %s, 'KhachHang', 'HoatDong')
        """
        cursor.execute(insert_query, (mand, email, matkhau, hoten, staff_region))

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({
            "success": True,
            "message": f"Đăng ký thành công khách hàng thuộc khu vực {staff_region}!"
        }), 201

    except Exception as e:
        return jsonify({"success": False, "message": f"Lỗi cơ sở dữ liệu: {str(e)}"}), 500

# ── 4. Tồn kho chi nhánh ─────────────────────────────────────────────────────

@app.route('/staff/inventory')
@role_required(['NhanVien'])
def staff_inventory():
    """Tồn kho thực tế của chi nhánh, gọi hàm xử lý từ inventory_service."""
    db_name   = get_staff_db()  # Trả về 'BanHangDaKho_HN', 'BanHangDaKho_DN' hoặc 'BanHangDaKho_HCM'
    tbl       = REGION_TABLE_MAP[db_name]
    wh_prefix = REGION_WAREHOUSE_PREFIX[db_name]

    try:
        # Gọi tầng dịch vụ xử lý, bên trong sẽ tự map với get_hn_connection, get_dn_connection,...
        inventory = get_branch_inventory(
            db_name=db_name,
            tbl_tonkho=tbl['tonkho'],
            wh_prefix=wh_prefix
        )

        # Render kết quả ra file giao diện HTML của bạn
        return render_template('staff/inventory.html', inventory=inventory)

    except Exception as e:
        # Bắt lỗi tầng CSDL và quăng ra view thông báo màu đỏ
        return _err(e)


# ── 5. Nhập xuất kho chi nhánh ───────────────────────────────────────────────

@app.route('/staff/warehouse-transactions')
@role_required(['NhanVien'])
def staff_warehouse_transactions():
    """Lịch sử & thông tin tạo phiếu nhập/xuất kho cho chi nhánh (gọi từ Service)."""
    db_name   = get_staff_db()
    tbl       = REGION_TABLE_MAP[db_name]
    wh_prefix = REGION_WAREHOUSE_PREFIX[db_name]

    try:
        # Gọi Service để lấy toàn bộ cục dữ liệu (đã bóc tách SQL ra khỏi đây)
        transactions, warehouses, products = get_branch_transactions(
            db_name=db_name,
            tbl_nhapxuat=tbl['nhapxuat'],
            wh_prefix=wh_prefix
        )

        # Trả về render giao diện bình thường
        return render_template('staff/warehouse_transactions.html',
                               transactions=transactions,
                               warehouses=warehouses,
                               products=products)
    except Exception as e:
        return _err(e)

# ── 6. Đơn hàng chi nhánh ────────────────────────────────────────────────────

@app.route('/staff/orders')
@branch_required
def staff_orders():
    """Đơn hàng liên quan đến kho của chi nhánh (lấy từ DB Trung tâm)."""
    wh_prefix = REGION_WAREHOUSE_PREFIX[get_staff_db()]
    try:
        conn   = get_center_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT DISTINCT dh.MaDH, dh.MaKH, dh.NgayDat, dh.TrangThai, dh.TongTien,
                            nd.HoTen AS TenKhachHang
            FROM DonHang dh
            JOIN NguoiDung nd       ON dh.MaKH  = nd.MaND
            JOIN ChiTietDonHang ctdh ON dh.MaDH  = ctdh.MaDH
            WHERE ctdh.MaKho LIKE %s
            ORDER BY dh.NgayDat DESC
        """, (f"{wh_prefix}%",))
        orders = cursor.fetchall()
        cursor.close()
        conn.close()
        return render_template('staff/orders.html', orders=orders)
    except Exception as e:
        return _err(e)


# =========================
# TRANG ADMIN
# =========================

@app.route('/admin/dashboard')
@role_required(['Admin'])
def admin_dashboard():
    stats = get_dashboard_stats()
    return render_template('admin/dashboard.html', stats=stats)


@app.route('/admin/users')
@role_required(['Admin'])
def manage_users():
    conn   = get_center_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT MaND, HoTen, Email, VaiTro, KhuVuc FROM NguoiDung ORDER BY VaiTro, HoTen")
    data = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('admin/users.html', users=data)


@app.route('/admin/categories')
@role_required(['Admin','NhanVien'])
def manage_categories():
    """Trang giao diện quản lý toàn bộ danh mục sản phẩm"""
    try:
        conn = get_center_connection()
        cursor = conn.cursor(dictionary=True)

        # Lấy danh sách danh mục kèm theo đếm số lượng sản phẩm thuộc danh mục đó
        query = """
            SELECT 
                d.MaDanhMuc,
                d.TenDanhMuc, 
                d.MoTa,
                COUNT(s.MaSP) AS SoLuongSanPham 
            FROM DanhMuc d
            LEFT JOIN SanPham s ON d.MaDanhMuc = s.MaDanhMuc
            GROUP BY d.MaDanhMuc, d.TenDanhMuc, d.MoTa
            ORDER BY d.MaDanhMuc DESC
        """
        cursor.execute(query)
        data = cursor.fetchall()

        cursor.close()
        conn.close()
        return render_template('admin/categories.html', categories=data)
    except Exception as e:
        # flash(f"Lỗi truy vấn danh mục: {str(e)}", "danger")
        # return redirect(url_for('admin_dashboard'))
        return f"""
                <div style="padding: 20px; font-family: sans-serif; background: #fee2e2; color: #991b1b; border: 1px solid #fca5a5; margin: 20px; border-radius: 8px;">
                    <h2 style="margin-top: 0;">🔴 Phát hiện lỗi tầng CSDL hoặc Logic:</h2>
                    <p><strong>Chi tiết lỗi:</strong> {str(e)}</p>
                    <p style="font-size: 13px; color: #6b7280; margin-bottom: 0;">Hãy gửi chuỗi lỗi này cho tôi để xử lý ngay lập tức.</p>
                </div>
                """

@app.route('/admin/inventory')
@role_required(['Admin']) # Admin kiểm tra tồn kho toàn hệ thống
def admin_inventory():
    data = get_all_inventory()
    return render_template('admin/inventory.html', inventory=data)

@app.route('/admin/warehouse-transactions')
@role_required(['Admin'])
def admin_transactions():
    """Trang chủ hiển thị danh sách nhật ký giao dịch nhập xuất tổng."""
    tx_list = get_all_transactions()
    warehouse_list = get_all_warehouses() # Lấy danh sách kho từ DB Trung tâm để hiển thị ở Dropdown chọn kho
    return render_template('admin/warehouse_transactions.html', transactions=tx_list, warehouses=warehouse_list)

@app.route('/admin/revenue_stats')
@role_required(['Admin'])
def revenue_stats():
    try:
        return render_template('admin/revenue_stats.html',
                               total_stats=get_revenue_by_system(),
                               region_stats=get_revenue_by_region(),
                               warehouse_stats=get_revenue_by_warehouse())
    except Exception as e:
        return _err(e)

@app.route('/admin/warehouses')
@role_required(['Admin'])
def warehouses():
    data = get_all_warehouses()
    return render_template('admin/warehouses.html', warehouses=data)

# =========================
# TRANG TEST ĐỒNG THỜI
# =========================
# Định nghĩa Blueprint
admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/admin/concurrent_test')
@role_required(['Admin'])
def concurrent_test_page():
    """Trang giao diện kiểm thử đặt hàng đồng thời nhiều khách hàng."""
    try:
        conn   = get_center_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT MaND, HoTen, KhuVuc FROM NguoiDung "
            "WHERE VaiTro = 'KhachHang' ORDER BY MaND"
        )
        customers = cursor.fetchall()
        cursor.execute("SELECT MaSP, TenSP, Gia FROM SanPham ORDER BY MaSP")
        products = cursor.fetchall()
        cursor.close()
        conn.close()
        return render_template('admin/concurrent_test.html',
                               customers=customers, products=products)
    except Exception as e:
        return _err(e)


@admin_bp.route('/api/admin/concurrent_test', methods=['POST'])
@role_required(['Admin'])
def api_concurrent_test():
    """
    Chạy N khách hàng đặt hàng đúng cùng lúc bằng threading.Barrier trên giao diện Web.
    """
    data = request.json or {}
    orders = data.get("orders", [])

    if len(orders) < 2:
        return jsonify({"success": False,
                        "message": "Cần ít nhất 2 khách hàng để test đồng thời!"}), 400

    ma_sp_check = orders[0].get("ma_sp", "SP01").strip().upper()
    _, stock_before = q2_total_stock(ma_sp_check)

    results = [None] * len(orders)
    barrier = threading.Barrier(len(orders))
    log_lock = threading.Lock()
    logs = []

    def worker(idx, ma_kh, items):
        current_time = time.strftime("%H:%M:%S", time.localtime())
        with log_lock:
            logs.append({
                "idx": idx, "ma_kh": ma_kh, "time": current_time,
                "event": "waiting", "msg": "Sẵn sàng, đang chờ tại Barrier..."
            })

        # Đồng loạt phóng kích nổ tải
        barrier.wait()

        current_time = time.strftime("%H:%M:%S", time.localtime())
        with log_lock:
            logs.append({
                "idx": idx, "ma_kh": ma_kh, "time": current_time,
                "event": "started", "msg": "Bắt đầu gọi thủ tục đặt hàng!"
            })

        ma_dh = place_order(ma_kh, items)
        results[idx] = {"ma_kh": ma_kh, "ma_dh": ma_dh, "success": ma_dh is not None}

        current_time = time.strftime("%H:%M:%S", time.localtime())
        with log_lock:
            status = f"✅ Thành công: {ma_dh}" if ma_dh else "❌ Thất bại (Hết hàng / Xung đột Lock)"
            logs.append({
                "idx": idx, "ma_kh": ma_kh, "time": current_time,
                "event": "done", "msg": status
            })

    threads = []
    for i, o in enumerate(orders):
        items = [{"MaSP": o["ma_sp"], "SoLuong": int(o["so_luong"])}]
        t = threading.Thread(target=worker, args=(i, o["ma_kh"], items))
        threads.append(t)

    for t in threads: t.start()
    for t in threads: t.join()

    _, stock_after = q2_total_stock(ma_sp_check)
    thanh_cong = [r for r in results if r and r["success"]]
    that_bai = [r for r in results if r and not r["success"]]

    tong_da_mua = sum(
        int(orders[i]["so_luong"])
        for i, r in enumerate(results) if r and r["success"]
    )

    return jsonify({
        "success": True,
        "stock_before": stock_before,
        "stock_after": stock_after,
        "giam": stock_before - stock_after,
        "giam_dung": (stock_after == stock_before - tong_da_mua),
        "khong_am": stock_after >= 0,
        "thanh_cong": thanh_cong,
        "that_bai": that_bai,
        "results": results,
        "logs": sorted(logs, key=lambda x: (x["time"], x["idx"])),
    })

# =========================
# TRANG KHÁCH HÀNG
# =========================

@app.route('/customer/home')
@role_required(['KhachHang'])
def customer_home():
    return render_template('customer/home.html')

# =========================
# TRANG DÙNG CHUNG
# =========================

@app.route('/products')
@login_required
def products():
    conn   = get_center_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM SanPham")
    data = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('products.html', products=data)


@app.route('/orders')
@login_required
def orders():
    data = q6_all_orders()
    return render_template('orders.html', orders=data)


@app.route('/distributed-queries')
@login_required
def distributed_queries():
    multi_wh_orders = q5_orders_from_multiple_warehouses()
    return render_template('distributed.html', orders=multi_wh_orders)


# =========================
# APIs — ADMIN
# =========================

@app.route('/api/admin/users', methods=['POST'])
@role_required(['Admin'])
def api_add_user():
    data    = request.json
    hoten   = data.get('hoten')
    email   = data.get('email')
    matkhau = data.get('matkhau')
    vaitro  = data.get('vaitro')
    khuvuc  = data.get('khuvuc', '')

    if not all([hoten, email, matkhau, vaitro]):
        return jsonify({"success": False, "message": "Vui lòng điền đầy đủ thông tin!"}), 400

    try:
        conn   = get_center_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT MaND FROM NguoiDung WHERE Email = %s", (email,))
        if cursor.fetchone():
            return jsonify({"success": False, "message": "Email này đã tồn tại trên hệ thống!"})
        cursor.execute(
            "INSERT INTO NguoiDung (HoTen, Email, MatKhau, VaiTro, KhuVuc) VALUES (%s,%s,%s,%s,%s)",
            (hoten, email, matkhau, vaitro, khuvuc)
        )
        conn.commit()
        cursor.close(); conn.close()
        return jsonify({"success": True, "message": "Thêm người dùng thành công!"})
    except Exception as e:
        return jsonify({"success": False, "message": f"Lỗi hệ thống: {str(e)}"}), 500


@app.route('/api/admin/users/<int:user_id>', methods=['DELETE'])
@role_required(['Admin'])
def api_delete_user(user_id):
    if user_id == session['user']['id']:
        return jsonify({"success": False, "message": "Không thể tự xóa tài khoản chính mình!"}), 400
    try:
        conn   = get_center_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM NguoiDung WHERE MaND = %s", (user_id,))
        conn.commit()
        cursor.close(); conn.close()
        return jsonify({"success": True, "message": "Đã xóa người dùng thành công!"})
    except Exception as e:
        return jsonify({"success": False,
                        "message": "Không thể xóa. Người dùng đang liên kết với dữ liệu khác!"}), 500


@app.route('/api/admin/categories', methods=['POST'])
@role_required(['Admin','NhanVien'])
def api_add_category():
    data = request.json
    madm = data.get('madm', '').strip()
    tendm = data.get('tendm', '').strip()
    mota = data.get('mota', '').strip()

    if not madm or not tendm:
        return jsonify({"success": False, "message": "Mã và Tên danh mục không được để trống!"}), 400

    # Danh sách các database chi nhánh cần đồng bộ (theo cấu hình hệ thống của bạn)
    branch_dbs = ['BanHangDaKho_HN', 'BanHangDaKho_HCM', 'BanHangDaKho_DN']

    center_conn = None
    try:
        # 1. Thực hiện chèn vào Database Trung Tâm trước
        center_conn = get_center_connection()
        center_cursor = center_conn.cursor()

        # Kiểm tra trùng khóa chính ở trung tâm
        center_cursor.execute("SELECT COUNT(*) FROM DanhMuc WHERE MaDanhMuc = %s", (madm,))
        if center_cursor.fetchone()[0] > 0:
            center_cursor.close()
            return jsonify({"success": False, "message": f"Mã danh mục '{madm}' đã tồn tại ở Database Trung Tâm!"}), 400

        center_cursor.execute(
            "INSERT INTO DanhMuc (MaDanhMuc, TenDanhMuc, MoTa) VALUES (%s, %s, %s)",
            (madm, tendm, mota)
        )
        center_conn.commit()
        center_cursor.close()

        # 2. VÒNG LẶP ĐỒNG BỘ: Chèn dữ liệu này xuống tất cả các Site chi nhánh
        for db_name in branch_dbs:
            try:
                # Sử dụng hàm helper get_branch_connection có sẵn trong dự án của bạn
                branch_conn = get_branch_connection(db_name)
                branch_cursor = branch_conn.cursor()

                # Thực thi lệnh chèn y hệt sang DB chi nhánh
                branch_cursor.execute(
                    "INSERT INTO DanhMuc (MaDanhMuc, TenDanhMuc, MoTa) VALUES (%s, %s, %s)",
                    (madm, tendm, mota)
                )
                branch_conn.commit()
                branch_cursor.close()
                branch_conn.close()
            except Exception as branch_err:
                # Log lỗi của từng chi nhánh nếu có nhưng không làm sập toàn bộ tiến trình
                print(f"⚠️ Cảnh báo: Không thể đồng bộ danh mục tới site {db_name}. Lỗi: {str(branch_err)}")

        return jsonify({
            "success": True,
            "message": f"Khởi tạo danh mục '{tendm}' thành công và đã đồng bộ tới toàn bộ 3 chi nhánh!"
        })

    except Exception as e:
        return jsonify({"success": False, "message": f"Lỗi cơ sở dữ liệu trung tâm: {str(e)}"}), 500
    finally:
        if center_conn and center_conn.is_connected():
            center_conn.close()

@app.route('/api/admin/categories/<string:cat_id>', methods=['DELETE'])
@role_required(['Admin','NhanVien'])
def api_delete_category(cat_id):
    branch_dbs = ['BanHangDaKho_HN', 'BanHangDaKho_HCM', 'BanHangDaKho_DN']
    center_conn = None
    try:
        center_conn = get_center_connection()
        center_cursor = center_conn.cursor()

        # 1. Kiểm tra ràng buộc sản phẩm ở Database Trung Tâm
        center_cursor.execute("SELECT COUNT(*) FROM SanPham WHERE MaDanhMuc = %s", (cat_id,))
        count = center_cursor.fetchone()[0]

        if count > 0:
            center_cursor.close()
            return jsonify({
                "success": False,
                "message": f"Không thể xóa danh mục! Hiện đang có {count} sản phẩm liên kết tại hệ thống master."
            }), 400

        # 2. Xóa dữ liệu tại Database Trung Tâm
        center_cursor.execute("DELETE FROM DanhMuc WHERE MaDanhMuc = %s", (cat_id,))
        center_conn.commit()
        center_cursor.close()

        # 3. VÒNG LẶP ĐỒNG BỘ XÓA: Gỡ bỏ danh mục này ở 3 Site chi nhánh
        for db_name in branch_dbs:
            try:
                branch_conn = get_branch_connection(db_name)
                branch_cursor = branch_conn.cursor()
                branch_cursor.execute("DELETE FROM DanhMuc WHERE MaDanhMuc = %s", (cat_id,))
                branch_conn.commit()
                branch_cursor.close()
                branch_conn.close()
            except Exception as branch_err:
                print(f"⚠️ Cảnh báo: Không thể xóa danh mục ở site {db_name}. Lỗi: {str(branch_err)}")

        return jsonify({"success": True, "message": "Đã xóa danh mục và đồng bộ gỡ bỏ ở toàn bộ các kho miền!"})

    except Exception as e:
        return jsonify({"success": False, "message": f"Lỗi hệ thống: {str(e)}"}), 500
    finally:
        if center_conn and center_conn.is_connected():
            center_conn.close()

@app.route('/api/admin/track-product/<string:product_id>')
@role_required(['Admin','NhanVien'])
def api_admin_track_product(product_id):
    """API gọi hàm quét tồn kho 3 miền để tìm vị trí chi tiết của sản phẩm"""
    try:
        # Import hàm tìm kiếm phân mảnh 3 miền của bạn
        from services.warehouse_service import find_product_in_warehouses

        results = find_product_in_warehouses(product_id.strip().upper())
        return jsonify({"success": True, "data": results})
    except Exception as e:
        return jsonify({"success": False, "message": f"Lỗi truy vấn phân mảnh: {str(e)}"}), 500

@app.route('/api/admin/warehouse_transactions', methods=['POST'])
@role_required(['Admin'])
def api_create_transaction():
    data = request.json

    ma_nx = data.get('ma_nx', '').strip().upper()
    loai_gd = data.get('loai_gd')  # Nhận giá trị: 'NHAP' hoặc 'XUAT'
    ma_kho = data.get('ma_kho')
    ma_sp = data.get('ma_sp', '').strip().upper()
    so_luong = data.get('so_luong')
    ghi_chu = data.get('ghi_chu', '').strip()
    khu_vuc = data.get('khu_vuc')  # Nhận từ select option: 'Hà Nội', 'Đà Nẵng', 'TPHCM'

    if not all([ma_nx, loai_gd, ma_kho, ma_sp, so_luong, khu_vuc]):
        return jsonify({"success": False, "message": "Vui lòng nhập đầy đủ các thông tin bắt buộc!"}), 400

    try:
        # Gọi hàm xử lý phân tán truyền vào hàm kết nối tương ứng
        success, msg = create_admin_transaction(
            region=khu_vuc,
            ma_nx=ma_nx,
            ma_kho=ma_kho,
            ma_sp=ma_sp,
            loai_gd=loai_gd,
            so_luong=so_luong,
            ghi_chu=ghi_chu
        )
        if success:
            return jsonify({"success": True, "message": msg})
        else:
            return jsonify({"success": False, "message": msg}), 400
    except Exception as e:
        return jsonify({"success": False, "message": f"Lỗi hệ thống: {str(e)}"}), 500

# ── 2. API Thêm kho mới ──────────────────────────────────────────────────────
@app.route('/api/admin/warehouses', methods=['POST'])
@role_required(['Admin'])
def api_add_warehouse():
    data = request.json
    ma_kho   = data.get('ma_kho', '').strip().upper()
    ten_kho  = data.get('ten_kho', '').strip()
    khu_vuc  = data.get('khu_vuc', '') # Nhận từ dropdown: 'Hà Nội', 'Đà Nẵng', 'HCM'
    dia_chi  = data.get('dia_chi', '').strip()

    if not all([ma_kho, ten_kho, khu_vuc]):
        return jsonify({"success": False, "message": "Vui lòng nhập đầy đủ các thông tin bắt buộc!"}), 400

    try:
        success, msg = add_new_warehouse(ma_kho, ten_kho, khu_vuc, dia_chi)
        if success:
            return jsonify({"success": True, "message": msg})
        else:
            return jsonify({"success": False, "message": msg}), 400
    except Exception as e:
        return jsonify({"success": False, "message": f"Lỗi hệ thống: {str(e)}"}), 500


# ── 3. API Xóa kho hàng ──────────────────────────────────────────────────────
@app.route('/api/admin/warehouses/<string:ma_kho>', methods=['DELETE'])
@role_required(['Admin'])
def api_delete_warehouse(ma_kho):
    # Cần client truyền kèm khu vực dạng query param (?khuvuc=HCM) để hàm biết đường tìm node xóa
    khu_vuc = request.args.get('khuvuc')
    if not khu_vuc:
        return jsonify({"success": False, "message": "Thiếu thông tin khu vực của kho để thực hiện xóa!"}), 400

    try:
        success, msg = delete_warehouse(ma_kho, khu_vuc)
        if success:
            return jsonify({"success": True, "message": msg})
        else:
            return jsonify({"success": False, "message": msg}), 400
    except Exception as e:
        return jsonify({"success": False, "message": f"Lỗi hệ thống: {str(e)}"}), 500


# =========================
# APIs — NHÂN VIÊN CHI NHÁNH
# =========================

@app.route('/api/staff/customers', methods=['POST'])
@branch_required
def api_staff_add_customer():
    """Nhân viên đăng ký khách hàng mới — tự động gán đúng khu vực chi nhánh."""
    data    = request.json
    hoten   = data.get('hoten')
    email   = data.get('email')
    matkhau = data.get('matkhau', '123456')
    # Khu vực luôn lấy từ session của nhân viên, không tin vào client gửi lên
    khuvuc  = session['user'].get('region')

    if not all([hoten, email]):
        return jsonify({"success": False, "message": "Vui lòng nhập đầy đủ thông tin bắt buộc!"}), 400

    try:
        conn   = get_center_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT MaND FROM NguoiDung WHERE Email = %s", (email,))
        if cursor.fetchone():
            return jsonify({"success": False, "message": "Email này đã được đăng ký!"}), 400
        cursor.execute(
            "INSERT INTO NguoiDung (HoTen, Email, MatKhau, VaiTro, KhuVuc) "
            "VALUES (%s, %s, %s, 'KhachHang', %s)",
            (hoten, email, matkhau, khuvuc)
        )
        conn.commit()
        cursor.close(); conn.close()
        return jsonify({"success": True, "message": "Thêm mới hồ sơ khách hàng thành công!"})
    except Exception as e:
        return jsonify({"success": False, "message": f"Lỗi CSDL: {str(e)}"}), 500


@app.route('/api/staff/warehouse_transactions', methods=['POST'])
@role_required(['NhanVien'])
def api_staff_add_transaction():
    """Nhân viên tạo phiếu nhập/xuất — Gọi hàm xử lý phân mảnh từ Service."""
    data    = request.json
    ma_nx    = data.get('ma_nx', '').strip().upper()
    ma_kho   = data.get('ma_kho', '').strip().upper()
    ma_sp    = data.get('ma_sp', '').strip().upper()
    loai_gd  = data.get('loai_gd')
    so_luong = data.get('so_luong')
    ghi_chu  = data.get('ghi_chu', '').strip()

    # Kiểm tra tính đầy đủ của tham số dữ liệu
    if not all([ma_nx, ma_kho, ma_sp, loai_gd, so_luong]):
        return jsonify({"success": False, "message": "Vui lòng nhập đầy đủ các trường bắt buộc!"}), 400

    db_name   = get_staff_db()
    tbl       = REGION_TABLE_MAP[db_name]
    wh_prefix = REGION_WAREHOUSE_PREFIX[db_name]

    # Kiểm tra bảo mật: Ngăn chặn nhân viên can thiệp ghi nhầm sang mã kho của site khác
    if not ma_kho.startswith(wh_prefix):
        return jsonify({"success": False, "message": f"Kho '{ma_kho}' không thuộc phạm vi quản lý của chi nhánh bạn!"}), 403

    # Ép kiểu dữ liệu số lượng hàng
    try:
        soluong_int = int(so_luong)
        if soluong_int <= 0:
            raise ValueError
    except ValueError:
        return jsonify({"success": False, "message": "Số lượng mặt hàng phải là một số nguyên dương!"}), 400

    # 🚀 Gọi hàm dịch vụ đã tách ở tầng Service xử lý bằng 3 connect độc lập
    success, message = create_branch_transaction(
        db_name=db_name,
        tbl=tbl,
        ma_nx=ma_nx,
        ma_kho=ma_kho,
        ma_sp=ma_sp,
        loai_gd=loai_gd,
        so_luong=soluong_int,
        ghi_chu=ghi_chu
    )

    if success:
        return jsonify({"success": True, "message": message})
    else:
        return jsonify({"success": False, "message": message}), 400

# =========================
# APIs — KHÁCH HÀNG
# =========================

@app.route('/api/customer/me')
@role_required(['KhachHang'])
def api_customer_me():
    """Trả về thông tin khách hàng đang đăng nhập từ session."""
    user = session.get('user')
    if not user:
        return jsonify({"success": False, "message": "Chưa đăng nhập!"}), 401
    return jsonify({
        "success": True,
        "user": {
            "id":     user.get('id'),
            "name":   user.get('name'),
            "region": user.get('region'),
        }
    })

@app.route('/api/customer/products')
@role_required(['KhachHang'])
def api_customer_products():
    """Trả về toàn bộ danh sách sản phẩm từ DB Trung Tâm cho trang mua sắm."""
    try:
        conn   = get_center_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT MaSP, TenSP, ThuongHieu, Gia, MaDanhMuc
            FROM SanPham
            ORDER BY TenSP
        """)
        products = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify(products)
    except Exception as e:
        return jsonify({"success": False, "message": f"Lỗi tải sản phẩm: {str(e)}"}), 500


@app.route('/api/customer/order/<string:ma_dh>')
@role_required(['KhachHang', 'NhanVien', 'Admin'])
def api_customer_track_order(ma_dh):
    """Tra cứu chi tiết đơn hàng theo mã — hỗ trợ cả Khách, NV và Admin."""
    user_role = session['user'].get('role')
    ma_kh = session['user'].get('id')

    try:
        conn = get_center_connection()
        # Thêm buffered=True để tránh xung đột khi chạy 2 lệnh execute liên tiếp
        cursor = conn.cursor(dictionary=True, buffered=True)

        # Rẽ nhánh câu lệnh SQL chuẩn theo quyền (Đã bổ sung nd.KhuVuc để Modal hiển thị tag)
        if user_role == 'KhachHang':
            # Khách hàng chỉ được xem đơn của chính mình
            cursor.execute("""
                SELECT dh.MaDH, dh.MaKH, dh.NgayDat, dh.TrangThai, dh.TongTien, 
                       nd.HoTen AS TenKhachHang, nd.KhuVuc
                FROM DonHang dh
                JOIN NguoiDung nd ON dh.MaKH = nd.MaND
                WHERE dh.MaDH = %s AND dh.MaKH = %s
            """, (ma_dh.strip().upper(), ma_kh))
        else:
            # Admin hoặc Nhân viên thì được xem đơn của bất kỳ ai
            cursor.execute("""
                SELECT dh.MaDH, dh.MaKH, dh.NgayDat, dh.TrangThai, dh.TongTien, 
                       nd.HoTen AS TenKhachHang, nd.KhuVuc
                FROM DonHang dh
                JOIN NguoiDung nd ON dh.MaKH = nd.MaND
                WHERE dh.MaDH = %s
            """, (ma_dh.strip().upper(),))

        # ĐỌC KẾT QUẢ NGAY TẠI ĐÂY (Đã xóa bỏ đoạn execute thừa bị lặp cũ)
        order = cursor.fetchone()

        if not order:
            cursor.close()
            conn.close()
            return jsonify({"success": False, "message": "Không tìm thấy đơn hàng hoặc bạn không có quyền xem!"}), 404

        # Lấy chi tiết từng sản phẩm trong đơn để lấy luôn MaKho phân tán
        cursor.execute("""
            SELECT ct.MaSP, s.TenSP, ct.SoLuong, ct.DonGia, ct.MaKho
            FROM ChiTietDonHang ct
            LEFT JOIN SanPham s ON ct.MaSP = s.MaSP
            WHERE ct.MaDH = %s
        """, (ma_dh.strip().upper(),))
        details = cursor.fetchall()

        cursor.close()
        conn.close()
        return jsonify({"success": True, "order": order, "details": details})

    except Exception as e:
        return jsonify({"success": False, "message": f"Lỗi hệ thống: {str(e)}"}), 500


@app.route('/api/customer/my-orders')
@role_required(['KhachHang'])
def api_customer_my_orders():
    """Lấy toàn bộ lịch sử đơn hàng của khách hàng đang đăng nhập."""
    ma_kh = session['user'].get('id')
    try:
        conn   = get_center_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT MaDH, NgayDat, TrangThai, TongTien
            FROM DonHang
            WHERE MaKH = %s
            ORDER BY NgayDat DESC
        """, (ma_kh,))
        orders = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify({"success": True, "orders": orders})
    except Exception as e:
        return jsonify({"success": False, "message": f"Lỗi tải đơn hàng: {str(e)}"}), 500

# =========================
# APIs — DÙNG CHUNG
# =========================
# --- API 1: THÊM SẢN PHẨM MỚI (ĐỒNG BỘ 3 SITE) ---
@app.route('/api/products', methods=['POST'])
@login_required
def add_product():
    conn_center = None
    try:
        data = request.get_json()

        # Đọc dữ liệu từ request body gửi lên
        ma_sp = data.get('MaSP')
        ten_sp = data.get('TenSP')
        ma_danh_muc = data.get('MaDanhMuc')
        thuong_hieu = data.get('ThuongHieu')
        mo_ta = data.get('MoTa', '')
        gia = data.get('Gia')

        # Kiểm tra các trường bắt buộc không được để trống
        if not all([ma_sp, ten_sp, ma_danh_muc, gia]):
            return jsonify({
                'success': False,
                'message': 'Vui lòng điền đầy đủ: Mã SP, Tên SP, Danh mục và Giá bán.'
            }), 400

        # Mở kết nối tới DB Trung Tâm
        conn_center = get_center_connection()
        cursor_center = conn_center.cursor()

        # Kiểm tra trùng khóa chính (Mã sản phẩm) tại Trung Tâm trước
        cursor_center.execute("SELECT COUNT(*) FROM SanPham WHERE MaSP = %s", (ma_sp,))
        if cursor_center.fetchone()[0] > 0:
            cursor_center.close()
            return jsonify({'success': False, 'message': f'Mã sản phẩm "{ma_sp}" đã tồn tại trên toàn hệ thống.'}), 400

        # 1. Thực thi lệnh INSERT vào bảng SanPham tại Trung Tâm
        query = """
            INSERT INTO SanPham (MaSP, TenSP, MaDanhMuc, ThuongHieu, MoTa, Gia)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        cursor_center.execute(query, (ma_sp, ten_sp, ma_danh_muc, thuong_hieu, mo_ta, gia))
        conn_center.commit()
        cursor_center.close()

        # 2. VÒNG LẶP ĐỒNG BỘ: Chèn sản phẩm này xuống tất cả các Site chi nhánh
        branch_dbs = ['BanHangDaKho_HN', 'BanHangDaKho_HCM', 'BanHangDaKho_DN']
        for db_name in branch_dbs:
            try:
                # Sử dụng hàm helper kết nối chi nhánh sẵn có trong hệ thống của bạn
                conn_branch = get_branch_connection(db_name)
                cursor_branch = conn_branch.cursor()

                cursor_branch.execute(query, (ma_sp, ten_sp, ma_danh_muc, thuong_hieu, mo_ta, gia))
                conn_branch.commit()

                cursor_branch.close()
                conn_branch.close()
            except Exception as branch_err:
                # Ghi nhận cảnh báo lỗi của site nhưng không chặn luồng chạy chính của ứng dụng
                print(f"⚠️ Cảnh báo: Không thể đồng bộ sản phẩm {ma_sp} tới site {db_name}. Lỗi: {str(branch_err)}")

        return jsonify({
            'success': True,
            'message': f'Thêm sản phẩm "{ten_sp}" ({ma_sp}) thành công và đã đồng bộ dữ liệu xuống 3 kho miền!'
        }), 201

    except Exception as e:
        print("Lỗi API POST /api/products:", str(e))
        return jsonify({'success': False, 'message': f'Lỗi hệ thống: {str(e)}'}), 500
    finally:
        if conn_center:
            conn_center.close()


# --- API 2: XÓA SẢN PHẨM (ĐỒNG BỘ GỠ BỎ Ở 3 SITE) ---
@app.route('/api/products/<string:product_id>', methods=['DELETE'])
@login_required
def delete_product(product_id):
    conn_center = None
    try:
        conn_center = get_center_connection()
        cursor_center = conn_center.cursor()

        # 1. Kiểm tra sản phẩm có tồn tại trong hệ thống hay không
        cursor_center.execute("SELECT MaSP FROM SanPham WHERE MaSP = %s", (product_id,))
        product = cursor_center.fetchone()

        if not product:
            cursor_center.close()
            return jsonify({'success': False, 'message': f'Sản phẩm mã {product_id} không tồn tại trên hệ thống.'}), 404

        # 2. Kiểm tra ràng buộc khóa ngoại trước khi xóa (Rất quan trọng đối với bảng dữ liệu phân tán)
        # Nếu sản phẩm này đang có dữ liệu trong các bảng như TonKho, ChiTietDonHang,... thì không được xóa bừa bãi
        cursor_center.execute("SELECT COUNT(*) FROM TonKho WHERE MaSP = %s", (product_id,))
        if cursor_center.fetchone()[0] > 0:
            cursor_center.close()
            return jsonify({
                'success': False,
                'message': 'Không thể xóa: Sản phẩm này hiện đang có cấu hình số lượng tồn tại các kho miền!'
            }), 400

        # 3. Tiến hành xóa sản phẩm khỏi Database Trung Tâm
        cursor_center.execute("DELETE FROM SanPham WHERE MaSP = %s", (product_id,))
        conn_center.commit()
        cursor_center.close()

        # 4. VÒNG LẶP ĐỒNG BỘ XÓA: Gỡ bỏ sản phẩm này tại 3 Site chi nhánh
        branch_dbs = ['BanHangDaKho_HN', 'BanHangDaKho_HCM', 'BanHangDaKho_DN']
        for db_name in branch_dbs:
            try:
                conn_branch = get_branch_connection(db_name)
                cursor_branch = conn_branch.cursor()

                cursor_branch.execute("DELETE FROM SanPham WHERE MaSP = %s", (product_id,))
                conn_branch.commit()

                cursor_branch.close()
                conn_branch.close()
            except Exception as branch_err:
                print(f"⚠️ Cảnh báo: Không thể xóa sản phẩm {product_id} ở site {db_name}. Lỗi: {str(branch_err)}")

        return jsonify({
            'success': True,
            'message': f'Đã xóa hoàn toàn sản phẩm {product_id} và đồng bộ dọn dẹp ở tất cả các kho miền.'
        })

    except Exception as e:
        print(f"Lỗi API DELETE /api/products/{product_id}:", str(e))
        return jsonify({'success': False, 'message': f'Không thể xóa sản phẩm: {str(e)}'}), 500
    finally:
        if conn_center:
            conn_center.close()

@app.route('/api/categories', methods=['GET'])
def api_get_categories():
    try:
        # Giả sử bạn lấy từ database trung tâm kết nối bằng get_center_connection()
        conn = get_center_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT MaDanhMuc, TenDanhMuc FROM DanhMuc")
        categories = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify({"success": True, "data": categories})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/inventory')
@login_required
def api_inventory():
    return jsonify(get_all_inventory())


@app.route('/api/inventory/<product_id>')
@login_required
def api_inventory_product(product_id):
    return jsonify(check_product_inventory(product_id))


@app.route('/api/order', methods=['POST'])
@login_required
def api_place_order():
    data   = request.json
    ma_kh  = data.get("ma_kh")
    items  = data.get("items", [])
    ma_dh  = place_order(ma_kh, items)
    if ma_dh:
        return jsonify({"success": True, "ma_dh": ma_dh, "message": "Đặt hàng thành công!"})
    else:
        return jsonify({"success": False, "message": "Đặt hàng thất bại (hết hàng hoặc lỗi hệ thống)."})


@app.route('/api/admin/orders/<string:order_id>/status', methods=['POST'])
@login_required
@role_required(['Admin', 'NhanVien'])  # Cho phép cả admin và nhân viên cập nhật tùy theo logic phân quyền của bạn
def api_update_order_status(order_id):
    data = request.json
    new_status = data.get('status')

    # Chuẩn hóa lại chuỗi lưu vào CSDL
    status_mapping = {
        'ChoXuLy': 'ChoXuLy',
        'DangGiao': 'DangGiao',
        'DaGiao': 'DaGiao',
        'DaHuy': 'DaHuy'
    }

    db_status = status_mapping.get(new_status)
    if not db_status:
        return jsonify({"success": False, "message": "Trạng thái không hợp lệ!"}), 400

    try:
        # Kết nối tới DB Trung tâm (vì bảng DonHang của bạn đang lưu tập trung theo code app.py trước đó)
        conn = get_center_connection()
        cursor = conn.cursor()

        # Cập nhật trạng thái của đơn hàng
        cursor.execute("""
            UPDATE DonHang 
            SET TrangThai = %s 
            WHERE MaDH = %s
        """, (db_status, order_id))

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({
            "success": True,
            "message": f"Đã cập nhật đơn hàng #{order_id} sang trạng thái '{db_status}' thành công!"
        })
    except Exception as e:
        return jsonify({"success": False, "message": f"Lỗi cập nhật CSDL: {str(e)}"}), 500


@app.route('/api/customer/orders/<string:order_id>/cancel', methods=['POST'])
@role_required(['KhachHang'])  # Sử dụng decorator phân quyền có sẵn của bạn
def api_customer_cancel_order(order_id):
    # Lấy ID khách hàng thật từ session theo đúng cấu trúc app của bạn
    current_user_id = session['user'].get('id')

    try:
        # 1. Kết nối DB Trung tâm để kiểm tra đơn hàng
        center_conn = get_center_connection()
        center_cursor = center_conn.cursor(dictionary=True)

        center_cursor.execute("""
            SELECT MaKH, TrangThai FROM DonHang WHERE MaDH = %s
        """, (order_id.strip().upper(),))
        order = center_cursor.fetchone()

        if not order:
            center_cursor.close()
            center_conn.close()
            return jsonify({"success": False, "message": "Không tìm thấy đơn hàng!"}), 404

        # 2. Kiểm tra xem có đúng là đơn hàng của chính khách này không
        if order['MaKH'] != current_user_id:
            center_cursor.close()
            center_conn.close()
            return jsonify({"success": False, "message": "Bạn không có quyền hủy đơn hàng này!"}), 403

        # 3. Kiểm tra trạng thái đơn (Chỉ cho phép hủy khi đang 'ChoXuLy')
        if order['TrangThai'] != 'ChoXuLy':
            center_cursor.close()
            center_conn.close()
            return jsonify(
                {"success": False, "message": "Đơn hàng đã được xử lý hoặc đang giao, không thể tự hủy!"}), 400

        # 4. Lấy chi tiết các sản phẩm trong đơn để biết cần trả về kho nào
        center_cursor.execute("""
            SELECT MaSP, MaKho, SoLuong FROM ChiTietDonHang WHERE MaDH = %s
        """, (order_id.strip().upper(),))
        items = center_cursor.fetchall()

        # 5. Tiến hành CẬP NHẬT TRẠNG THÁI đơn hàng thành 'DaHuy' ở trung tâm
        center_cursor.execute("""
            UPDATE DonHang SET TrangThai = 'DaHuy' WHERE MaDH = %s
        """, (order_id.strip().upper(),))
        center_conn.commit()

        center_cursor.close()
        center_conn.close()

        # 6. HOÀN TRẢ TỒN KHO VỀ CÁC SITE PHÂN TÁN
        # Import hàm giải phóng/hoàn tồn kho từ order_service của bạn
        from services.order_service import release_hold

        for item in items:
            ma_kho = item['MaKho'].strip().upper()

            # Khớp cấu trúc dựa vào REGION_WAREHOUSE_PREFIX của bạn (HN, DN, HCM)
            if "HN" in ma_kho:
                site_key = "HN"
            elif "DN" in ma_kho:
                site_key = "DN"
            else:
                site_key = "TPHCM"  # Đồng bộ theo key "TPHCM" ở bài trước bạn sửa nhé

            # Gọi hàm hoàn trả tồn kho phân tán
            release_hold(site_key, ma_kho, item['MaSP'], item['SoLuong'])

        return jsonify({
            "success": True,
            "message": f"Hủy đơn hàng #{order_id} thành công. Sản phẩm đã được hoàn trả về kho!"
        })

    except Exception as e:
        return jsonify({"success": False, "message": f"Lỗi hệ thống khi hủy đơn: {str(e)}"}), 500

@app.route('/api/stats/top-selling', methods=['GET'])
@login_required
def api_top_selling_products():
    """API Endpoint trả về dữ liệu JSON sản phẩm bán chạy (tiện cho việc vẽ biểu đồ Chart.js)."""
    # Lấy tham số 'limit' từ URL query (ví dụ: /api/stats/top-selling?limit=5), mặc định là 5
    limit = request.args.get('limit', default=3, type=int)
    try:
        data = q4_top_selling_products(top_n=limit)
        return jsonify({"success": True, "data": data})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
# =========================
# HELPER
# =========================

def _err(e):
    """Hiển thị lỗi debug dạng thẻ HTML đỏ (chỉ dùng trong môi trường phát triển)."""
    return f"""
    <div style="padding:20px;font-family:sans-serif;background:#fee2e2;color:#991b1b;
                border:1px solid #fca5a5;margin:20px;border-radius:8px;">
        <h2 style="margin-top:0;">🔴 Lỗi tầng CSDL / Logic:</h2>
        <p><strong>Chi tiết:</strong> {str(e)}</p>
        <p style="font-size:13px;color:#6b7280;margin-bottom:0;">
            Gửi chuỗi lỗi này để được hỗ trợ xử lý.
        </p>
    </div>
    """

app.register_blueprint(admin_bp)
if __name__ == '__main__':
    app.run(debug=True)
