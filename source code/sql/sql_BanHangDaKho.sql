DROP DATABASE IF EXISTS BanHangDaKho;
CREATE DATABASE IF NOT EXISTS BanHangDaKho;
USE BanHangDaKho;

SET FOREIGN_KEY_CHECKS = 0;

DROP TABLE IF EXISTS
    ChiTietPhieuNhap,
    PhieuNhap,
    ChiTietDonHang,
    DonHang,
    TonKho,
    Kho,
    SanPham,
    DanhMuc,
    NhaCungCap,
    NguoiDung;

SET FOREIGN_KEY_CHECKS = 1;

-- ==========================================
-- PHẦN 1: NGƯỜI DÙNG
-- ==========================================

CREATE TABLE NguoiDung (
    MaND VARCHAR(10) PRIMARY KEY,
    Email VARCHAR(255) UNIQUE NOT NULL,
    MatKhau VARCHAR(255) NOT NULL,
    HoTen VARCHAR(255) NOT NULL,
    SoDienThoai VARCHAR(20),
    DiaChi TEXT,
    KhuVuc VARCHAR(100),

    VaiTro ENUM(
        'Admin',
        'NhanVien',
        'KhachHang'
    ) DEFAULT 'KhachHang',

    TrangThai ENUM(
        'HoatDong',
        'BiKhoa'
    ) DEFAULT 'HoatDong',

    NgayTao DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- ==========================================
-- PHẦN 2: DANH MỤC & SẢN PHẨM
-- ==========================================

CREATE TABLE DanhMuc (
    MaDanhMuc VARCHAR(50) PRIMARY KEY,
    TenDanhMuc VARCHAR(100) NOT NULL,
    MoTa TEXT
) ENGINE=InnoDB;

CREATE TABLE SanPham (
    MaSP VARCHAR(50) PRIMARY KEY,
    TenSP VARCHAR(255) NOT NULL,
    MaDanhMuc VARCHAR(50),
    Gia DECIMAL(15,2) NOT NULL,
    MoTa TEXT,
    ThuongHieu VARCHAR(100),

    FOREIGN KEY (MaDanhMuc)
        REFERENCES DanhMuc(MaDanhMuc)
) ENGINE=InnoDB;

-- ==========================================
-- PHẦN 3: KHO & TỒN KHO
-- ==========================================

CREATE TABLE Kho (
    MaKho VARCHAR(50) PRIMARY KEY,
    TenKho VARCHAR(100) NOT NULL,
    KhuVuc VARCHAR(100),
    DiaChi VARCHAR(255)
) ENGINE=InnoDB;

CREATE TABLE TonKho (
    MaKho VARCHAR(50),
    MaSP VARCHAR(50),
    SoLuong INT DEFAULT 0,

    PRIMARY KEY (MaKho, MaSP),

    FOREIGN KEY (MaKho)
        REFERENCES Kho(MaKho),

    FOREIGN KEY (MaSP)
        REFERENCES SanPham(MaSP)
) ENGINE=InnoDB;

CREATE TABLE NhapXuatKho(
    MaNX VARCHAR(50) PRIMARY KEY,
    MaKho VARCHAR(50),
    MaSP VARCHAR(50),

    LoaiGD ENUM('NHAP', 'XUAT') NOT NULL,

    SoLuong INT NOT NULL 
        CHECK (SoLuong > 0),

    NgayGD DATETIME DEFAULT CURRENT_TIMESTAMP,

    GhiChu TEXT,

    FOREIGN KEY (MaKho) REFERENCES Kho(MaKho),
    FOREIGN KEY (MaSP) REFERENCES SanPham(MaSP)
) ENGINE=InnoDB;

-- ==========================================
-- PHẦN 4: ĐƠN HÀNG
-- ==========================================
    MaDH VARCHAR(50) PRIMARY KEY,
    MaKH VARCHAR(10) NOT NULL,
    NgayDat DATETIME DEFAULT CURRENT_TIMESTAMP,

    TrangThai ENUM(
        'ChoXuLy',
        'DangGiao',
        'DaGiao',
        'DaHuy'
    ) DEFAULT 'ChoXuLy',

    TongTien DECIMAL(15,2),

    FOREIGN KEY (MaKH)
        REFERENCES NguoiDung(MaND)
) ENGINE=InnoDB;

CREATE TABLE ChiTietDonHang (
    MaDH VARCHAR(50),
    MaSP VARCHAR(50),
    MaKho VARCHAR(50),

    SoLuong INT NOT NULL,
    DonGia DECIMAL(15,2) NOT NULL,

    PRIMARY KEY (MaDH, MaSP, MaKho),

    FOREIGN KEY (MaDH)
        REFERENCES DonHang(MaDH),

    FOREIGN KEY (MaSP)
        REFERENCES SanPham(MaSP),

    FOREIGN KEY (MaKho)
        REFERENCES Kho(MaKho)
) ENGINE=InnoDB;

-- ==========================================
-- PHẦN 5: NHÀ CUNG CẤP
-- ==========================================

CREATE TABLE NhaCungCap (
    MaNCC VARCHAR(10) PRIMARY KEY,
    TenNCC VARCHAR(255) NOT NULL,
    SoDienThoai VARCHAR(20),
    DiaChi VARCHAR(255)
) ENGINE=InnoDB;

-- ==========================================
-- PHẦN 6: PHIẾU NHẬP
-- ==========================================

CREATE TABLE PhieuNhap (
    MaPN VARCHAR(10) PRIMARY KEY,

    MaKho VARCHAR(50),
    MaNCC VARCHAR(10),
    MaNguoiNhap VARCHAR(10),

    NgayNhap DATETIME DEFAULT CURRENT_TIMESTAMP,
    TongTienNhap DECIMAL(15,2),

    FOREIGN KEY (MaKho)
        REFERENCES Kho(MaKho),

    FOREIGN KEY (MaNCC)
        REFERENCES NhaCungCap(MaNCC),

    FOREIGN KEY (MaNguoiNhap)
        REFERENCES NguoiDung(MaND)
) ENGINE=InnoDB;

CREATE TABLE ChiTietPhieuNhap (
    MaPN VARCHAR(10),
    MaSP VARCHAR(50),

    SoLuongNhap INT NOT NULL,
    DonGiaNhap DECIMAL(15,2) NOT NULL,

    PRIMARY KEY (MaPN, MaSP),

    FOREIGN KEY (MaPN)
        REFERENCES PhieuNhap(MaPN),

    FOREIGN KEY (MaSP)
        REFERENCES SanPham(MaSP)
) ENGINE=InnoDB;

-- ==========================================
-- PHẦN 7: DỮ LIỆU MẪU
-- ==========================================

-- 1. Thêm dữ liệu vào bảng NguoiDung
INSERT INTO NguoiDung (MaND, Email, MatKhau, HoTen, SoDienThoai, DiaChi, KhuVuc, VaiTro, TrangThai) VALUES
('ND001', 'admin@gmail.com', 'hashed_pwd_1', 'Nguyễn Văn Admin', '0901234567', '123 Lê Lợi, Q1', 'TPHCM', 'Admin', 'HoatDong'),
('ND002', 'nv_ha@gmail.com', 'hashed_pwd_2', 'Trần Thị Hà (NV Kho)', '0912345678', '45 Ngô Gia Tự', 'Hà Nội', 'NhanVien', 'HoatDong'),
('ND003', 'kh_cuong@gmail.com', 'hashed_pwd_3', 'Lê Hải Cường (Khách)', '0923456789', '789 Nguyễn Chí Thanh', 'Hà Nội', 'KhachHang', 'HoatDong'),
('ND004', 'kh_linh@gmail.com', 'hashed_pwd_4', 'Phạm Mai Linh (Khách)', '0934567890', '456 Điện Biên Phủ', 'Đà Nẵng', 'KhachHang', 'HoatDong');

-- 2. Thêm dữ liệu vào bảng DanhMuc
INSERT INTO DanhMuc (MaDanhMuc, TenDanhMuc, MoTa) VALUES
('DM01', 'Điện thoại & Máy tính bảng', 'Các sản phẩm thiết bị di động thông minh'),
('DM02', 'Laptop & Máy tính', 'Máy tính xách tay, máy tính để bàn và linh kiện'),
('DM03', 'Điện tử Gia dụng', 'Tivi, tủ lạnh, máy giặt và đồ gia dụng lớn');

-- 3. Thêm dữ liệu vào bảng SanPham
INSERT INTO SanPham (MaSP, TenSP, MaDanhMuc, Gia, MoTa, ThuongHieu) VALUES
('SP01', 'iPhone 15 Pro Max 256GB', 'DM01', 29990000.00, 'Điện thoại cao cấp Apple năm 2023', 'Apple'),
('SP02', 'Samsung Galaxy S24 Ultra', 'DM01', 27990000.00, 'Điện thoại flagship Samsung tích hợp AI', 'Samsung'),
('SP03', 'MacBook Air M3 8GB/256GB', 'DM02', 26490000.00, 'Laptop mỏng nhẹ hiệu năng cao của Apple', 'Apple'),
('SP04', 'Laptop ASUS Vivobook 14', 'DM02', 13490000.00, 'Laptop học tập văn phòng giá tốt', 'ASUS'),
('SP05', 'Tủ lạnh LG Inverter 315L', 'DM03', 8990000.00, 'Tủ lạnh tiết kiệm điện, ngăn đá trên', 'LG');

-- 4. Thêm dữ liệu vào bảng Kho
INSERT INTO Kho (MaKho, TenKho, KhuVuc, DiaChi) VALUES
('KH_HN01', 'Kho Tổng Cầu Giấy', 'Hà Nội', 'Số 15 Cầu Giấy, Quận Cầu Giấy, Hà Nội'),
('KH_HN02', 'Kho Phụ Long Biên', 'Hà Nội', 'Số 45 Ngô Gia Tự, Quận Long Biên, Hà Nội'),
('KH_DN01', 'Kho Trung Tâm Hải Châu', 'Đà Nẵng', 'Số 120 Lê Duẩn, Quận Hải Châu, Đà Nẵng'),
('KH_DN02', 'Kho Liên Chiểu', 'Đà Nẵng', 'Khu Công Nghiệp Hòa Khánh, Quận Liên Chiểu, Đà Nẵng'),
('KH_HCM01', 'Kho Tổng Quận 7', 'TPHCM', 'Số 88 Nguyễn Văn Linh, Quận 7, TP. Hồ Chí Minh'),
('KH_HCM02', 'Kho Thủ Đức', 'TPHCM', 'Số 200 Võ Văn Ngân, TP. Thủ Đức, TP. Hồ Chí Minh');

-- 6. Thêm dữ liệu vào bảng NhaCungCap
INSERT INTO NhaCungCap (MaNCC, TenNCC, SoDienThoai, DiaChi) VALUES
('NCC01', 'Công ty TNHH Apple Việt Nam', '02838240000', 'Quận 1, TPHCM'),
('NCC02', 'Nhà Phân Phối Samsung Digiworld', '02435377666', 'Đống Đa, Hà Nội');

-- 7. Thêm dữ liệu vào bảng DonHang
INSERT INTO DonHang (MaDH, MaKH, NgayDat, TrangThai, TongTien) VALUES
('DH001', 'ND003', '2026-05-18 10:30:00', 'DaGiao', 59980000.00),
('DH002', 'ND004', '2026-05-20 14:15:00', 'ChoXuLy', 26490000.00);

-- 8. Thêm dữ liệu vào bảng ChiTietDonHang
INSERT INTO ChiTietDonHang (MaDH, MaSP, MaKho, SoLuong, DonGia) VALUES
('DH001', 'SP01', 'KH_HN01', 2, 29990000.00),
('DH002', 'SP03', 'KH_DN01', 1, 26490000.00);

-- 9. Thêm dữ liệu vào bảng PhieuNhap
INSERT INTO PhieuNhap (MaPN, MaKho, MaNCC, MaNguoiNhap, NgayNhap, TongTienNhap) VALUES
('PN001', 'KH_HN01', 'NCC01', 'ND002', '2026-05-15 09:00:00', 250000000.00);

-- 10. Thêm dữ liệu vào bảng ChiTietPhieuNhap
INSERT INTO ChiTietPhieuNhap (MaPN, MaSP, SoLuongNhap, DonGiaNhap) VALUES
('PN001', 'SP01', 10, 25000000.00);

INSERT INTO NguoiDung 
(MaND, Email, MatKhau, HoTen, SoDienThoai, DiaChi, KhuVuc, VaiTro, TrangThai) 
VALUES
('ND005', 'nv_hcm_1@gmail.com', 'hashed_pwd_5', 'Nguyễn Quốc Bảo (NV Kho)', '0941111111', '12 Nguyễn Huệ, Q1', 'TPHCM', 'NhanVien', 'HoatDong'),
('ND006', 'nv_hcm_2@gmail.com', 'hashed_pwd_6', 'Trần Minh Khang (NV Giao Hàng)', '0942222222', '88 Võ Văn Tần, Q3', 'TPHCM', 'NhanVien', 'HoatDong'),

('ND007', 'nv_hn_1@gmail.com', 'hashed_pwd_7', 'Đặng Thu Trang (NV Kho)', '0951111111', '25 Cầu Giấy', 'Hà Nội', 'NhanVien', 'HoatDong'),
('ND008', 'nv_hn_2@gmail.com', 'hashed_pwd_8', 'Phạm Đức Long (NV Bán Hàng)', '0952222222', '77 Hai Bà Trưng', 'Hà Nội', 'NhanVien', 'HoatDong'),

('ND009', 'nv_dn_1@gmail.com', 'hashed_pwd_9', 'Võ Thanh Tùng (NV Kho)', '0961111111', '15 Trần Phú', 'Đà Nẵng', 'NhanVien', 'HoatDong'),
('ND010', 'nv_dn_2@gmail.com', 'hashed_pwd_10', 'Lê Ngọc Anh (NV CSKH)', '0962222222', '120 Nguyễn Văn Linh', 'Đà Nẵng', 'NhanVien', 'HoatDong'),
('ND011', 'kh_huy@gmail.com', 'hashed_pwd_11', 'Nguyễn Gia Huy', '0971111111', '22 Phạm Văn Đồng', 'Hà Nội', 'KhachHang', 'HoatDong'),
('ND012', 'kh_nhi@gmail.com', 'hashed_pwd_12', 'Trần Bảo Nhi', '0972222222', '11 Nguyễn Tri Phương', 'Đà Nẵng', 'KhachHang', 'HoatDong'),
('ND013', 'kh_tuan@gmail.com', 'hashed_pwd_13', 'Lê Minh Tuấn', '0973333333', '56 Lý Thường Kiệt', 'TPHCM', 'KhachHang', 'HoatDong'),
('ND014', 'kh_hanh@gmail.com', 'hashed_pwd_14', 'Phạm Ngọc Hạnh', '0974444444', '90 Hoàng Hoa Thám', 'Hà Nội', 'KhachHang', 'HoatDong'),
('ND015', 'kh_quynh@gmail.com', 'hashed_pwd_15', 'Đỗ Thanh Quỳnh', '0975555555', '18 Nguyễn Tất Thành', 'Đà Nẵng', 'KhachHang', 'HoatDong');

COMMIT;