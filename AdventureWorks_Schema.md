# AdventureWorks Schema

本文件记录构建 Ontology 所使用的 7 张 Databricks Silver 层表的结构、字段类型和业务说明，供查阅和复现使用。

| Table | Rows | Description |
|---|---:|---|
| [`salescustomer`](#salescustomer) | 847 | 客户基本信息（个人/企业）。 |
| [`salesaddress`](#salesaddress) | 417 | 地址主表（合成的美国地址，用于支撑 AddressID 外键）。 |
| [`salescustomeraddress`](#salescustomeraddress) | 417 | 客户 ↔ 地址 多对多关联（含地址类型）。 |
| [`salesorderheader`](#salesorderheader) | 32 | 销售订单头（订单元数据、金额合计、地址引用）。 |
| [`salesorderdetail`](#salesorderdetail) | 542 | 销售订单明细行（数量、单价、折扣、行小计）。 |
| [`salesproduct`](#salesproduct) | 295 | 产品主数据（名称、颜色、价格、尺寸、重量、类目）。 |
| [`salesproductcategory`](#salesproductcategory) | 41 | 产品类目（含递归父子关系）。 |

---

## `salescustomer`

**Rows:** 847
**Description:** 客户主数据，包含姓名、联系方式和公司归属信息。可用于客户画像、营销分群、客户关系管理等场景。

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `CustomerID` | INT | No | 主键 |
| `Title` | STRING | Yes (7 null) | 称谓：`Mr.` / `Ms.` / `Sr.` / `Sra.` |
| `FirstName` | STRING | No | |
| `MiddleName` | STRING | Yes (343 null) | |
| `LastName` | STRING | No | |
| `Suffix` | STRING | Yes (799 null) | `Jr.` / `II` / `Sr.` / `IV` / `PhD` |
| `CompanyName` | STRING | Yes | 有值则视为企业客户（`BusinessCustomer`） |
| `EmailAddress` | STRING | Yes | |
| `Phone` | STRING | Yes | |

```sql
CREATE TABLE ai_data_insight.silver.salescustomer (
  CustomerID         INT,
  Title              STRING,
  FirstName          STRING,
  MiddleName         STRING,
  LastName           STRING,
  Suffix             STRING,
  CompanyName        STRING,
  EmailAddress       STRING,
  Phone              STRING
)
```

---

## `salesaddress`

**Rows:** 417
**Description:** 合成的美国地址数据，用于支撑 `salescustomeraddress.AddressID` 与 `salesorderheader.ShipToAddressID / BillToAddressID` 的外键。专为本 AdventureWorks Ontology demo 创建。

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `AddressID` | INT | No | 主键 |
| `AddressLine1` | STRING | No | |
| `AddressLine2` | STRING | Yes (332 null) | 例如 `Suite 100` |
| `City` | STRING | No | 15 个城市，覆盖美国主要都市 |
| `StateProvince` | STRING | No | 10 个州（`CA` 80, `TX` 80, `WA` 55 …） |
| `CountryRegion` | STRING | No | 全部为 `United States` |
| `PostalCode` | STRING | No | 5 位邮编 |

```sql
CREATE TABLE ai_data_insight.silver.salesaddress (
  AddressID      INT,
  AddressLine1   STRING,
  AddressLine2   STRING,
  City           STRING,
  StateProvince  STRING,
  CountryRegion  STRING,
  PostalCode     STRING
)
```

---

## `salescustomeraddress`

**Rows:** 417
**Description:** 客户与地址之间的多对多关联，并通过 `AddressType` 区分主办公地址和发货地址。是构建 Ontology 中 `CustomerAddressLink` 这一 reified link class 的来源。

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `CustomerID` | INT | No | FK → `salescustomer.CustomerID` |
| `AddressID` | INT | No | FK → `salesaddress.AddressID` |
| `AddressType` | STRING | No | `Main Office` (407) / `Shipping` (10) |

```sql
CREATE TABLE ai_data_insight.silver.salescustomeraddress (
  CustomerID   INT,
  AddressID    INT,
  AddressType  STRING
)
```

---

## `salesorderheader`

**Rows:** 32
**Description:** 销售订单头，含订单状态、日期、客户引用、收发货地址引用以及金额合计字段，是订单分析、履约跟踪和业绩评估的核心表。

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `SalesOrderID` | INT | No | 主键 |
| `RevisionNumber` | INT | No | 全部为 2 |
| `DueDate` | TIMESTAMP | No | |
| `ShipDate` | TIMESTAMP | No | |
| `Status` | INT | No | 全部为 5（`shipped`） |
| `OnlineOrderFlag` | BOOLEAN | No | 全部为 `false` |
| `SalesOrderNumber` | STRING | No | 例如 `SO71774` |
| `PurchaseOrderNumber` | STRING | No | 例如 `PO348186287` |
| `AccountNumber` | STRING | No | |
| `CustomerID` | INT | No | FK → `salescustomer.CustomerID` |
| `ShipToAddressID` | INT | No | FK → `salesaddress.AddressID` |
| `BillToAddressID` | INT | No | FK → `salesaddress.AddressID` |
| `ShipMethod` | STRING | No | 全部为 `CARGO TRANSPORT 5` |
| `SubTotal` | DOUBLE | No | 金额建议建模为 `xsd:decimal` |
| `TaxAmt` | DOUBLE | No | 同上 |
| `Freight` | DOUBLE | No | 同上 |
| `TotalDue` | DOUBLE | No | 用于定义 `HighValueOrder`（≥ 500） |
| `OrderDate` | DATE | No | |

```sql
CREATE TABLE ai_data_insight.silver.salesorderheader (
  SalesOrderID         INT,
  RevisionNumber       INT,
  DueDate              TIMESTAMP,
  ShipDate             TIMESTAMP,
  Status               INT,
  OnlineOrderFlag      BOOLEAN,
  SalesOrderNumber     STRING,
  PurchaseOrderNumber  STRING,
  AccountNumber        STRING,
  CustomerID           INT,
  ShipToAddressID      INT,
  BillToAddressID      INT,
  ShipMethod           STRING,
  SubTotal             DOUBLE,
  TaxAmt               DOUBLE,
  Freight              DOUBLE,
  TotalDue             DOUBLE,
  OrderDate            DATE
)
```

---

## `salesorderdetail`

**Rows:** 542
**Description:** 销售订单明细行，记录每个订单包含的产品、数量、单价和折扣，是计算行小计 / 分析折扣影响 / 推算单品销量的基础。

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `SalesOrderID` | INT | No | FK → `salesorderheader.SalesOrderID`，构成复合主键 |
| `OrderQty` | INT | No | |
| `ProductID` | INT | No | FK → `salesproduct.ProductID`，构成复合主键 |
| `UnitPrice` | DOUBLE | No | 建议建模为 `xsd:decimal` |
| `UnitPriceDIscount` | DOUBLE | No | 0 ~ 0.4；> 0 时进入 `DiscountedOrderLine` |
| `LineTotal` | DOUBLE | No | 行小计 |

> 注：列名 `UnitPriceDIscount` 中的 `D` 大写为原表保留拼写。

```sql
CREATE TABLE ai_data_insight.silver.salesorderdetail (
  SalesOrderID       INT,
  OrderQty           INT,
  ProductID          INT,
  UnitPrice          DOUBLE,
  UnitPriceDIscount  DOUBLE,
  LineTotal          DOUBLE
)
```

---

## `salesproduct`

**Rows:** 295
**Description:** 产品主数据，含名称、产品编号、颜色、成本、标价、尺寸、重量以及类目归属，是产品维度分析的核心。

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `ProductID` | INT | No | 主键 |
| `Name` | STRING | No | 产品名 |
| `ProductNumber` | STRING | No | 例如 `PD-T852` |
| `Color` | STRING | Yes (50 null) | `Black` 89 / `Red` 38 / `Silver` 36 / `Yellow` 36 / `Blue` 26 / `Multi` 8 / `Silver/Black` 7 / `White` 4 / `Grey` 1 |
| `StandardCost` | DOUBLE | No | 建议建模为 `xsd:decimal` |
| `ListPrice` | DOUBLE | No | 同上 |
| `Size` | STRING | Yes (84 null) | 数值型 `38~70` 或服装码 `S/M/L/XL` |
| `Weight` | DOUBLE | Yes (97 null) | |
| `ProductCategoryID` | INT | No | FK → `salesproductcategory.ProductCategoryID` |

```sql
CREATE TABLE ai_data_insight.silver.salesproduct (
  ProductID          INT,
  Name               STRING,
  ProductNumber      STRING,
  Color              STRING,
  StandardCost       DOUBLE,
  ListPrice          DOUBLE,
  Size               STRING,
  Weight             DOUBLE,
  ProductCategoryID  INT
)
```

---

## `salesproductcategory`

**Rows:** 41
**Description:** 产品类目，通过 `ParentProductCategoryID` 形成 4 层递归层次（`Bikes / Components / Clothing / Accessories` 及其子类目），在 Ontology 中映射为 `hasParentCategory`（`owl:TransitiveProperty`）。

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `ProductCategoryID` | INT | No | 主键 |
| `ParentProductCategoryID` | INT | Yes (4 null) | 顶层 4 个类目的父为空 |
| `Name` | STRING | No | 类目名 |

```sql
CREATE TABLE ai_data_insight.silver.salesproductcategory (
  ProductCategoryID        INT,
  ParentProductCategoryID  INT,
  Name                     STRING
)
```
