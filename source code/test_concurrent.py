import threading
import time
from flask import Flask, render_template_string, request, jsonify
from db.connect_hn import get_hn_connection

app = Flask(__name__)

# Giao diện HTML siêu thô (Không CSS, không màu mè, thuần HTML gốc)
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Tool Test Dong Thoi</title>
</head>
<body>
    <h2>KỊCH BẢN MÔ PHỎNG ĐẶT HÀNG ĐỒNG THỜI</h2>

    <table border="1" cellpadding="5">
        <tr>
            <td>Mã sản phẩm (MaSP):</td>
            <td><input type="text" id="ma_sp" value="SP01"></td>
        </tr>
        <tr>
            <td>Mã kho (Hà Nội):</td>
            <td><input type="text" id="ma_kho" value="KH_HN01"></td>
        </tr>
        <tr>
            <td>Số lượng kho ban đầu:</td>
            <td><input type="number" id="stock_ban_dau" value="4"></td>
        </tr>
        <tr>
            <td>Mỗi khách mua:</td>
            <td><input type="number" id="so_luong_mua" value="2"></td>
        </tr>
    </table>
    <br>

    <button id="btn-run" onclick="startSim()" style="padding: 10px 20px; font-weight: bold;">
        BẮT ĐẦU CHẠY 5 THREADS CÙNG LÚC
    </button>

    <hr>

    <h3>KẾT QUẢ TRONG DATABASE</h3>
    <ul>
        <li>Kho ban đầu thiết lập: <b id="lbl-start">-</b></li>
        <li>Số lượng bị trừ đi thực tế: <b id="lbl-deducted">-</b></li>
        <li>Số lượng còn lại cuối cùng trong DB: <b id="lbl-end" style="color: blue;">-</b></li>
    </ul>

    <hr>

    <h3>NHẬT KÝ CHI TIẾT CỦA 5 LUỒNG KHÁCH HÀNG</h3>
    <table border="1" cellpadding="8" cellspacing="0" width="100%">
        <thead>
            <tr style="background-color: #eee;">
                <th>Khách hàng</th>
                <th>Thời gian chạy</th>
                <th>Trạng thái</th>
                <th>Chi tiết phản hồi từ code</th>
            </tr>
        </thead>
        <tbody id="result-table-body">
            <tr>
                <td colspan="4" align="center">Chưa có dữ liệu. Bấm nút phía trên để test.</td>
            </tr>
        </tbody>
    </table>

    <script>
    function startSim() {
        const btn = document.getElementById('btn-run');
        btn.disabled = true;
        btn.innerText = "ĐANG CHẠY ĐỒNG THỜI...";

        const payload = {
            ma_sp: document.getElementById('ma_sp').value,
            ma_kho: document.getElementById('ma_kho').value,
            stock_ban_dau: document.getElementById('stock_ban_dau').value,
            so_luong_mua: document.getElementById('so_luong_mua').value
        };

        fetch('/run-trigger', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        })
        .then(res => res.json())
        .then(data => {
            btn.disabled = false;
            btn.innerText = "BẮT ĐẦU CHẠY 5 THREADS CÙNG LÚC";

            if(!data.success) {
                alert("Lỗi: " + data.message);
                return;
            }

            // Đổ dữ liệu tổng quan
            document.getElementById('lbl-start').innerText = data.stock_ban_dau;
            document.getElementById('lbl-deducted').innerText = data.total_deducted;
            document.getElementById('lbl-end').innerText = data.stock_cuoi_cung;

            // Đổ dữ liệu bảng luồng
            const tbody = document.getElementById('result-table-body');
            tbody.innerHTML = '';

            for (const [customer, info] of Object.entries(data.details)) {
                const color = info.status === 'SUCCESS' ? 'green' : 'red';
                const row = `
                    <tr>
                        <td><b>${customer}</b></td>
                        <td>${info.time}</td>
                        <td style="color: ${color}; font-weight: bold;">${info.status}</td>
                        <td>${info.message}</td>
                    </tr>
                `;
                tbody.innerHTML += row;
            }
        })
        .catch(err => {
            btn.disabled = false;
            btn.innerText = "BẮT ĐẦU CHẠY 5 THREADS CÙNG LÚC";
            alert("Lỗi kết nối server!");
        });
    }
    </script>
</body>
</html>
"""


@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route('/run-trigger', methods=['POST'])
def run_trigger():
    from services.order_service import place_order

    data = request.json or {}
    ma_sp = data.get('ma_sp', '').strip().upper()
    ma_kho = data.get('ma_kho', '').strip().upper()
    stock_ban_dau = int(data.get('stock_ban_dau', 4))
    so_luong_mua = int(data.get('so_luong_mua', 2))

    # Đảm bảo 5 mã này có thật trong bảng NguoiDung (DB Center)
    customers = ["ND003", "ND011", "ND014", "ND017", "ND018"]

    if not ma_sp or not ma_kho:
        return jsonify({"success": False, "message": "Thiếu thông tin SP hoặc Kho!"}), 400

    # 1. Reset dữ liệu kho về mức test ban đầu
    try:
        conn = get_hn_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE TonKho_HN SET SoLuong = %s WHERE MaSP = %s AND MaKho = %s",
            (stock_ban_dau, ma_sp, ma_kho)
        )
        conn.commit()
        cursor.close();
        conn.close()
    except Exception as e:
        return jsonify({"success": False, "message": f"Lỗi DB: {str(e)}"}), 500

    # 2. Kích hoạt 5 luồng chạy song song đặt hàng
    order_results = {}

    def worker(ma_kh):
        items = [{"MaSP": ma_sp, "SoLuong": so_luong_mua}]
        start_time = time.time()

        # Gọi thẳng vào logic xử lý đặt hàng phân tán của bạn
        ma_dh = place_order(ma_kh, items)

        duration = time.time() - start_time
        if ma_dh:
            order_results[ma_kh] = {
                "status": "SUCCESS",
                "message": f"Tạo đơn thành công: {ma_dh}",
                "time": f"{duration:.2f}s"
            }
        else:
            order_results[ma_kh] = {
                "status": "FAILED",
                "message": "Bị huỷ đơn (Cơ chế Lock chặn lại để bảo vệ kho)",
                "time": f"{duration:.2f}s"
            }

    threads = []
    for kh in customers:
        t = threading.Thread(target=worker, args=(kh,))
        threads.append(t)

    for t in threads: t.start()
    for t in threads: t.join()

    # 3. Lấy số lượng tồn kho thực tế sau khi chạy xong bài test
    stock_cuoi_cung = 0
    try:
        conn = get_hn_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT SoLuong FROM TonKho_HN WHERE MaSP = %s AND MaKho = %s", (ma_sp, ma_kho))
        row = cursor.fetchone()
        stock_cuoi_cung = row['SoLuong'] if row else 0
        cursor.close();
        conn.close()
    except:
        pass

    return jsonify({
        "success": True,
        "stock_ban_dau": stock_ban_dau,
        "stock_cuoi_cung": stock_cuoi_cung,
        "total_deducted": stock_ban_dau - stock_cuoi_cung,
        "details": order_results
    })


if __name__ == '__main__':
    # Chạy độc lập hoàn toàn ở Port 8080
    app.run(host='0.0.0.0', port=8080, debug=True)