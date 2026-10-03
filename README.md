# TECHMART – Distributed Database Online Shopping System

> A web-based online technology shopping system built with Python/Flask and
> distributed MySQL databases.

**[▶️ Watch Product Demo](https://drive.google.com/file/d/1rHlhVFLy40zS1dKp9sU-reFnP-9sgjKx/view?usp=sharing)**

---

## Overview

TechMart is a web-based online technology shopping system developed as a
team project. The system applies a distributed database architecture to
manage products, inventory, warehouses, customers, and orders across
multiple regions.

The system consists of regional databases for:
- Hanoi
- Da Nang
- Ho Chi Minh City

and a central database responsible for coordinating shared data and
system-wide operations.

## Technologies

- **Backend:** Python, Flask
- **Frontend:** HTML, CSS, JavaScript
- **Database:** MySQL, Distributed Database Architecture
- **Tools:** Git, GitHub

## Main Features

### Customer
- Browse products
- View product information
- Manage shopping cart
- Place orders
- View order information

### Inventory & Warehouse
- Manage product inventory
- Manage warehouse information
- Track stock across regional databases
- Handle concurrent inventory operations

### Order Management
- Create and process orders
- Check product availability
- Update inventory after transactions
- Maintain data consistency

## Distributed Database Architecture

The system uses a distributed database model with three regional
databases:

```text
                    Central Database
                          │
            ┌─────────────┼─────────────┐
            │             │             │
        Hanoi DB       Da Nang DB    HCMC DB
            │             │             │
        Warehouse      Warehouse     Warehouse
        Inventory      Inventory     Inventory
