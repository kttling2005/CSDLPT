import threading
from services.order_service import place_order, check_inventory_at_site
from services.query_service import q2_total_stock

# ── HELPER ───────────────────────────────────────────────────
def get_total_stock(ma_sp):
    _, total = q2_total_stock(ma_sp)
    return total

def get_site_stock(site, ma_sp):
    rows = check_inventory_at_site(site, ma_sp)
    return sum(r["SoLuong"] for r in rows)

def sep(title):
    print(f"\n{'═'*65}")
    print(f"  {title}")
    print(f"{'═'*65}")

# ── WORKER ───────────────────────────────────────────────────
def worker(ma_kh, items, barrier, results, idx):
    """Chờ tất cả sẵn sàng rồi đồng loạt áp tải vào đặt hàng."""
    print(f"  [Thread-{idx:02d}] Khách {ma_kh} — sẵn sàng, đang chờ...")
    barrier.wait()          
    print(f"  [Thread-{idx:02d}] Khách {ma_kh} — BẮT ĐẦU!")
    ma_dh = place_order(ma_kh, items)
    results[idx] = (ma_kh, ma_dh)
    status = f"✅ {ma_dh}" if ma_dh else "❌ Thất bại"
    print(f"  [Thread-{idx:02d}] Khách {ma_kh} — {status}")

# ── HÀM CHÍNH XỬ LÝ KỊCH BẢN ────────────────────────────────
def run_concurrent(test_id, test_name, customers_orders, ma_sp_check):
    sep(f"{test_id} — {test_name}")
    N = len(customers_orders)
    print(f"  Số khách hàng đồng thời: {N}")

    stock_before = get_total_stock(ma_sp_check)
    print(f"  Tồn kho {ma_sp_check} toàn hệ thống trước: {stock_before}\n")

    results = [None] * N
    barrier = threading.Barrier(N)

    threads = [
        threading.Thread(
            target=worker,
            args=(c["ma_kh"], c["items"], barrier, results, i),
        )
        for i, c in enumerate(customers_orders)
    ]

    for t in threads: t.start()
    for t in threads: t.join()

    # ── THỐNG KÊ KẾT QUẢ NÂNG CAO ─────────────────────────────
    stock_after = get_total_stock(ma_sp_check)
    thanh_cong = [(i, ma_kh, ma_dh) for i, (ma_kh, ma_dh) in enumerate(results) if ma_dh]
    that_bai = [(i, ma_kh) for i, (ma_kh, ma_dh) in enumerate(results) if not ma_dh]

    tong_da_mua = sum(
        sum(item["SoLuong"] for item in customers_orders[i]["items"])
        for i, _, _ in thanh_cong
    )
    giam_dung = (stock_after == stock_before - tong_da_mua)
    khong_am = stock_after >= 0

    print(f"\n  {'─' * 60}")
    print(f"  TỔNG KẾT KỊCH BẢN ĐỒNG THỜI: {test_id}")
    print(f"  {'─' * 60}")
    print(f"  Tồn kho {ma_sp_check} toàn hệ thống TRƯỚC : {stock_before}")
    print(f"  Tồn kho {ma_sp_check} toàn hệ thống SAU   : {stock_after} (Thực giảm: {stock_before - stock_after})")
    print(f"  [PHÂN TÁCH SITE] Kho HN: {get_site_stock('HN', ma_sp_check)} | Kho DN: {get_site_stock('DN', ma_sp_check)} | Kho HCM: {get_site_stock('TPHCM', ma_sp_check)}")

    print(f"\n  ✅ Thành công ({len(thanh_cong)}/{N} khách):")
    for i, ma_kh, ma_dh in thanh_cong:
        print(f"     Thread-{i:02d} Khách {ma_kh} → Đơn hàng: {ma_dh}")

    if that_bai:
        print(f"\n  ❌ Thất bại ({len(that_bai)}/{N} khách):")
        for i, ma_kh in that_bai:
            print(f"     Thread-{i:02d} Khách {ma_kh} → Bị từ chối (Tranh chấp Lock/Hết hàng)")

    print(f"\n  📊 KIỂM TRA TÍNH TOÀN VẸN:")
    print(f"  {'✅ ĐẠT' if khong_am else '❌ LỖI'} Tồn kho hệ thống không bị âm.")
    print(f"  {'✅ ĐẠT' if giam_dung else '❌ LỖI'} Kho giảm đúng bằng số lượng chốt đơn (-{tong_da_mua}).")


# ── KHỞI CHẠY KHỐI KỊCH BẢN ──────────────────────────────────
if __name__ == "__main__":
    # Kịch bản 1
    run_concurrent(
        test_id      = "TC_C01",
        test_name    = "5 khách đồng thời — kho đủ cho tất cả",
        ma_sp_check  = "SP05",
        customers_orders = [
            {"ma_kh": "ND003", "items": [{"MaSP": "SP05", "SoLuong": 1}]},
            {"ma_kh": "ND004", "items": [{"MaSP": "SP05", "SoLuong": 1}]},
            {"ma_kh": "ND005", "items": [{"MaSP": "SP05", "SoLuong": 1}]},
            {"ma_kh": "ND006", "items": [{"MaSP": "SP05", "SoLuong": 1}]},
            {"ma_kh": "ND007", "items": [{"MaSP": "SP05", "SoLuong": 1}]},
        ],
    )

    # Kịch bản 2
    run_concurrent(
        test_id      = "TC_C02",
        test_name    = "5 khách đồng thời tranh SP01, kho chỉ đủ 3 người",
        ma_sp_check  = "SP01",
        customers_orders = [
            {"ma_kh": "ND003", "items": [{"MaSP": "SP01", "SoLuong": 3}]},
            {"ma_kh": "ND004", "items": [{"MaSP": "SP01", "SoLuong": 3}]},
            {"ma_kh": "ND005", "items": [{"MaSP": "SP01", "SoLuong": 3}]},
            {"ma_kh": "ND006", "items": [{"MaSP": "SP01", "SoLuong": 3}]},
            {"ma_kh": "ND007", "items": [{"MaSP": "SP01", "SoLuong": 3}]},
        ],
    )

    # Kịch bản 3
    run_concurrent(
        test_id      = "TC_C03",
        test_name    = "10 khách đồng thời — stress test (SP03)",
        ma_sp_check  = "SP03",
        customers_orders = [
            {"ma_kh": f"ND{str(i).zfill(3)}", "items": [{"MaSP": "SP03", "SoLuong": 1}]}
            for i in range(3, 13)
        ],
    )

    print(f"\n{'═'*65}\n  Hoàn thành tất cả kịch bản kiểm thử đồng thời.\n{'═'*65}\n")
