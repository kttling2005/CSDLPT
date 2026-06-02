CREATE DATABASE IF NOT EXISTS BanHangDaKho_HCM;
USE BanHangDaKho_HCM;

SET FOREIGN_KEY_CHECKS = 0;

drop table if exists Kho, TonKho_HCM, SanPham, DanhMuc, NhapXuatKho_HCM;

-- Bảng Danh Mục
CREATE TABLE DanhMuc (
    MaDanhMuc VARCHAR(50) PRIMARY KEY,
    TenDanhMuc VARCHAR(100) NOT NULL,
    MoTa TEXT
) ENGINE=InnoDB;

INSERT INTO DanhMuc (MaDanhMuc, TenDanhMuc, MoTa) VALUES
('DM01', 'Điện thoại & Máy tính bảng', 'Các sản phẩm thiết bị di động thông minh'),
('DM02', 'Laptop & Máy tính', 'Máy tính xách tay, máy tính để bàn và linh kiện'),
('DM03', 'Điện tử Gia dụng', 'Tivi, tủ lạnh, máy giặt và đồ gia dụng lớn');

-- Bảng Sản Phẩm
CREATE TABLE SanPham (
    MaSP VARCHAR(50) PRIMARY KEY,
    TenSP VARCHAR(255) NOT NULL,
    MaDanhMuc VARCHAR(50),
    Gia DECIMAL(15,2) NOT NULL,
    MoTa TEXT,
    ThuongHieu VARCHAR(100),
    FOREIGN KEY (MaDanhMuc) REFERENCES DanhMuc(MaDanhMuc)
) ENGINE=InnoDB;

INSERT INTO SanPham (MaSP, TenSP, MaDanhMuc, Gia, MoTa, ThuongHieu) VALUES
('SP01', 'iPhone 15 Pro Max 256GB', 'DM01', 29990000.00, 'Điện thoại cao cấp Apple năm 2023', 'Apple'),
('SP02', 'Samsung Galaxy S24 Ultra', 'DM01', 27990000.00, 'Điện thoại flagship Samsung tích hợp AI', 'Samsung'),
('SP03', 'MacBook Air M3 8GB/256GB', 'DM02', 26490000.00, 'Laptop mỏng nhẹ hiệu năng cao của Apple', 'Apple'),
('SP04', 'Laptop ASUS Vivobook 14', 'DM02', 13490000.00, 'Laptop học tập văn phòng giá tốt', 'ASUS'),
('SP05', 'Tủ lạnh LG Inverter 315L', 'DM03', 8990000.00, 'Tủ lạnh tiết kiệm điện, ngăn đá trên', 'LG');

-- Bảng Kho
CREATE TABLE Kho (
    MaKho VARCHAR(50) PRIMARY KEY,
    TenKho VARCHAR(100) NOT NULL,
    KhuVuc VARCHAR(100),
    DiaChi VARCHAR(255)
) ENGINE=InnoDB;

INSERT INTO Kho (MaKho, TenKho, KhuVuc, DiaChi) VALUES
('KH_HN01', 'Kho Tổng Cầu Giấy', 'Hà Nội', 'Số 15 Cầu Giấy, Quận Cầu Giấy, Hà Nội'),
('KH_HN02', 'Kho Phụ Long Biên', 'Hà Nội', 'Số 45 Ngô Gia Tự, Quận Long Biên, Hà Nội'),
('KH_DN01', 'Kho Trung Tâm Hải Châu', 'Đà Nẵng', 'Số 120 Lê Duẩn, Quận Hải Châu, Đà Nẵng'),
('KH_DN02', 'Kho Liên Chiểu', 'Đà Nẵng', 'Khu Công Nghiệp Hòa Khánh, Quận Liên Chiểu, Đà Nẵng'),
('KH_HCM01', 'Kho Tổng Quận 7', 'TPHCM', 'Số 88 Nguyễn Văn Linh, Quận 7, TP. Hồ Chí Minh'),
('KH_HCM02', 'Kho Thủ Đức', 'TPHCM', 'Số 200 Võ Văn Ngân, TP. Thủ Đức, TP. Hồ Chí Minh');

-- Bảng Tồn Kho
CREATE TABLE TonKho_HCM (
    MaKho VARCHAR(50),
    MaSP VARCHAR(50),
    SoLuong INT DEFAULT 0,

    PRIMARY KEY (MaKho, MaSP),

    CONSTRAINT CK_SoLuong_KhongAm 
        CHECK (SoLuong >= 0),

    CONSTRAINT FK_TonKhoHCM_Kho
        FOREIGN KEY (MaKho) REFERENCES Kho(MaKho),

    CONSTRAINT FK_TonKhoHCM_SanPham
        FOREIGN KEY (MaSP) REFERENCES SanPham(MaSP)
) ENGINE=InnoDB;

CREATE TABLE NhapXuatKho_HCM (
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

-- Thêm dữ liệu vào bảng TonKho_HCM
INSERT INTO TonKho_HCM (MaKho, MaSP, SoLuong) VALUES
('KH_HCM01', 'SP01', 60),  
('KH_HCM01', 'SP02', 50),  
('KH_HCM01', 'SP03', 35),   
('KH_HCM02', 'SP01', 20),   
('KH_HCM02', 'SP04', 30),   
('KH_HCM02', 'SP05', 12);

-- Dữ liệu mẫu cho bảng NhapXuatKho_HCM
INSERT INTO NhapXuatKho_HCM (MaNX, MaKho, MaSP, LoaiGD, SoLuong, GhiChu) VALUES
('NXHCM001', 'KH_HCM01', 'SP01', 'NHAP', 120, 'Nhập thêm iPhone 15 từ nhà cung cấp Apple'),
('NXHCM002', 'KH_HCM01', 'SP02', 'NHAP', 100, 'Nhập thêm Samsung Galaxy S24 Ultra'),
('NXHCM003', 'KH_HCM01', 'SP01', 'XUAT', 25, 'Xuất bán cho khách lẻ'),
('NXHCM004', 'KH_HCM02', 'SP04', 'NHAP', 60, 'Nhập laptop ASUS Vivobook'),
('NXHCM005', 'KH_HCM02', 'SP05', 'XUAT', 7, 'Xuất kho giao khách điện máy'),
('NXHCM006', 'KH_HCM02', 'SP03', 'NHAP', 30, 'Nhập thêm MacBook Air M3');

SET FOREIGN_KEY_CHECKS = 1;