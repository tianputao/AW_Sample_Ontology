#!/usr/bin/env python3
"""
Build script: AdventureWorks Silver layer  ->  OWL 2 DL ontology (RDF/XML).

Outputs
-------
aw_ontology.owl   : self-contained OWL ontology (TBox + small ABox)

Inputs
------
sample_data/*.json : seven JSON files extracted from ai_data_insight.silver
                     via the Databricks MCP

Design Decisions (see /memories/session/plan.md)
------------------------------------------------
* OWL 2 DL profile, RDF/XML serialisation, base IRI
  http://tarhone.com/ontology/adventrueworks#
* All annotations are bilingual (rdfs:label@en / @zh,
  rdfs:comment@en / @zh, skos:definition@en).
* NULL strategy:
    - DataProperty NULL  -> omit the triple (open-world friendly)
    - ObjectProperty NULL pointing to enumerated classes
      -> use a :unknown_<enum> named individual.
* OrderLine IRI = :orderline_<SalesOrderID>_<ProductID>
  (verified unique in our sample).
* ProductCategory : modelled BOTH as a class hierarchy (so HermiT can
  infer subclass closure) AND as named individuals of :ProductCategory
  so that :inCategory has a target individual.
* All units / annotations authored inline by the build script
  (no external dictionary).
"""

import json
import os
import re
from datetime import datetime

from rdflib import BNode, Graph, Literal, Namespace, URIRef, XSD
from rdflib.namespace import OWL, RDF, RDFS, SKOS

# --------------------------------------------------------------------------- #
# 0. Configuration
# --------------------------------------------------------------------------- #
HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "sample_data")
OUT_FILE = os.path.join(HERE, "aw_ontology.owl")

BASE = "http://tarhone.com/ontology/adventrueworks#"
ONTO_IRI = URIRef("http://tarhone.com/ontology/adventrueworks")
AW = Namespace(BASE)

g = Graph()
g.bind("aw", AW)
g.bind("owl", OWL)
g.bind("rdf", RDF)
g.bind("rdfs", RDFS)
g.bind("xsd", XSD)
g.bind("skos", SKOS)

HIGH_VALUE_THRESHOLD = 500.0  # used by :HighValueOrder definition


# --------------------------------------------------------------------------- #
# 1. Helpers
# --------------------------------------------------------------------------- #
def to_iri(local: str) -> URIRef:
    """Convert a local name to a full URI under the AW namespace."""
    return AW[local]


def slugify_class(name: str) -> str:
    """'Mountain Bikes' -> 'MountainBikes',  'Bottles and Cages' -> 'BottlesAndCages'."""
    parts = re.split(r"[^A-Za-z0-9]+", name)
    return "".join(p[:1].upper() + p[1:] for p in parts if p)


def slugify_individual(name: str) -> str:
    """Lowercase camelCase for individual local names: 'CARGO TRANSPORT 5' -> 'cargoTransport5'."""
    parts = re.split(r"[^A-Za-z0-9]+", name)
    if not parts:
        return "unknown"
    head = parts[0].lower()
    tail = "".join(p[:1].upper() + p[1:].lower() for p in parts[1:] if p)
    return head + tail


def add_class(local, label_en, label_zh, comment_en, comment_zh, parents=None):
    cls = to_iri(local)
    g.add((cls, RDF.type, OWL.Class))
    g.add((cls, RDFS.label, Literal(label_en, lang="en")))
    g.add((cls, RDFS.label, Literal(label_zh, lang="zh")))
    g.add((cls, RDFS.comment, Literal(comment_en, lang="en")))
    g.add((cls, RDFS.comment, Literal(comment_zh, lang="zh")))
    if parents:
        for p in parents:
            g.add((cls, RDFS.subClassOf, to_iri(p) if isinstance(p, str) else p))
    return cls


def add_op(local, label_en, label_zh, comment_en, comment_zh,
           domain=None, range_=None, inverse=None,
           functional=False, inverse_functional=False,
           transitive=False, symmetric=False, asymmetric=False):
    p = to_iri(local)
    g.add((p, RDF.type, OWL.ObjectProperty))
    g.add((p, RDFS.label, Literal(label_en, lang="en")))
    g.add((p, RDFS.label, Literal(label_zh, lang="zh")))
    g.add((p, RDFS.comment, Literal(comment_en, lang="en")))
    g.add((p, RDFS.comment, Literal(comment_zh, lang="zh")))
    if domain is not None:
        g.add((p, RDFS.domain, to_iri(domain) if isinstance(domain, str) else domain))
    if range_ is not None:
        g.add((p, RDFS.range, to_iri(range_) if isinstance(range_, str) else range_))
    if inverse is not None:
        g.add((p, OWL.inverseOf, to_iri(inverse) if isinstance(inverse, str) else inverse))
    if functional:
        g.add((p, RDF.type, OWL.FunctionalProperty))
    if inverse_functional:
        g.add((p, RDF.type, OWL.InverseFunctionalProperty))
    if transitive:
        g.add((p, RDF.type, OWL.TransitiveProperty))
    if symmetric:
        g.add((p, RDF.type, OWL.SymmetricProperty))
    if asymmetric:
        g.add((p, RDF.type, OWL.AsymmetricProperty))
    return p


def add_dp(local, label_en, label_zh, comment_en, comment_zh,
           domain=None, range_=XSD.string, functional=False, unit=None):
    p = to_iri(local)
    g.add((p, RDF.type, OWL.DatatypeProperty))
    g.add((p, RDFS.label, Literal(label_en, lang="en")))
    g.add((p, RDFS.label, Literal(label_zh, lang="zh")))
    g.add((p, RDFS.comment, Literal(comment_en, lang="en")))
    g.add((p, RDFS.comment, Literal(comment_zh, lang="zh")))
    if domain is not None:
        g.add((p, RDFS.domain, to_iri(domain) if isinstance(domain, str) else domain))
    g.add((p, RDFS.range, range_))
    if functional:
        g.add((p, RDF.type, OWL.FunctionalProperty))
    if unit:
        # Custom annotation property :unit captured below
        g.add((p, AW.unit, Literal(unit, lang="en")))
    return p


def add_ind(local, classes, label_en=None, label_zh=None, comment_en=None, comment_zh=None):
    ind = to_iri(local)
    g.add((ind, RDF.type, OWL.NamedIndividual))
    if isinstance(classes, str):
        classes = [classes]
    for c in classes:
        g.add((ind, RDF.type, to_iri(c) if isinstance(c, str) else c))
    if label_en:
        g.add((ind, RDFS.label, Literal(label_en, lang="en")))
    if label_zh:
        g.add((ind, RDFS.label, Literal(label_zh, lang="zh")))
    if comment_en:
        g.add((ind, RDFS.comment, Literal(comment_en, lang="en")))
    if comment_zh:
        g.add((ind, RDFS.comment, Literal(comment_zh, lang="zh")))
    return ind


def make_disjoint(*class_locals):
    classes = [to_iri(c) if isinstance(c, str) else c for c in class_locals]
    for i in range(len(classes)):
        for j in range(i + 1, len(classes)):
            g.add((classes[i], OWL.disjointWith, classes[j]))


def restriction(on_property, kind, value):
    """
    Build an anonymous owl:Restriction node.
    kind: one of someValuesFrom, allValuesFrom, hasValue, cardinality,
          minCardinality, maxCardinality, qualifiedCardinality
    """
    r = BNode()
    g.add((r, RDF.type, OWL.Restriction))
    g.add((r, OWL.onProperty, to_iri(on_property) if isinstance(on_property, str) else on_property))
    g.add((r, getattr(OWL, kind), value))
    return r


def intersection_of(members):
    """Build an owl:Class with owl:intersectionOf RDF list."""
    c = BNode()
    g.add((c, RDF.type, OWL.Class))
    # Use rdflib's collection helper
    from rdflib.collection import Collection
    Collection(g, c, [])  # init empty
    Collection(g, c, members)
    g.add((c, OWL.intersectionOf, c))  # NB: this is wrong; fixing below
    return c


# More reliable intersectionOf helper
def class_intersection(members):
    c = BNode()
    g.add((c, RDF.type, OWL.Class))
    list_node = BNode()
    g.add((c, OWL.intersectionOf, list_node))
    from rdflib.collection import Collection
    Collection(g, list_node, members)
    return c


# --------------------------------------------------------------------------- #
# 2. Ontology header
# --------------------------------------------------------------------------- #
g.add((ONTO_IRI, RDF.type, OWL.Ontology))
g.add((ONTO_IRI, RDFS.label, Literal("AdventureWorks Sales Ontology", lang="en")))
g.add((ONTO_IRI, RDFS.label, Literal("AdventureWorks 销售本体", lang="zh")))
g.add((ONTO_IRI, RDFS.comment, Literal(
    "An OWL 2 DL ontology generated from the AdventureWorks Silver layer "
    "(ai_data_insight.silver). Includes Customers, Addresses, Sales Orders, "
    "Order Lines, Products, and a recursive Product Category hierarchy. "
    "Authored as a learning demo for Protégé.", lang="en")))
g.add((ONTO_IRI, RDFS.comment, Literal(
    "基于 AdventureWorks Silver 数据层（ai_data_insight.silver）自动生成的 OWL 2 DL 本体，"
    "包含客户、地址、销售订单、订单明细、产品以及递归产品类目层次结构。"
    "用于 Protégé 入门演示。", lang="zh")))
g.add((ONTO_IRI, OWL.versionInfo, Literal("1.0.0")))

# A custom annotation property to hold units
g.add((AW.unit, RDF.type, OWL.AnnotationProperty))
g.add((AW.unit, RDFS.label, Literal("unit", lang="en")))
g.add((AW.unit, RDFS.label, Literal("单位", lang="zh")))
g.add((AW.unit, RDFS.comment, Literal(
    "Free-text unit-of-measure annotation for data properties.", lang="en")))


# --------------------------------------------------------------------------- #
# 3. TBox -- Core classes
# --------------------------------------------------------------------------- #
add_class("Customer", "Customer", "客户",
          "A person or business that places orders.",
          "下订单的个人或企业。")
add_class("IndividualCustomer", "Individual Customer", "个人客户",
          "A customer that is a private individual (no associated company name).",
          "无所属公司的个人客户。",
          parents=["Customer"])
add_class("BusinessCustomer", "Business Customer", "企业客户",
          "A customer that represents a company. Equivalent to any Customer with a "
          "non-empty :companyName value.",
          "代表公司的客户。等价于任何拥有非空 :companyName 的 Customer。",
          parents=["Customer"])
make_disjoint("IndividualCustomer", "BusinessCustomer")

add_class("Address", "Address", "地址",
          "A postal address used for shipping or billing.",
          "用于发货或账单的邮政地址。")

add_class("CustomerAddressLink", "Customer-Address Link", "客户-地址关联",
          "A reified n-ary relation linking a Customer, an Address and an "
          "AddressType (Main Office / Shipping / Billing).",
          "将客户、地址与地址类型（主办公地址/收货/账单）关联起来的 n 元关系实化。")

add_class("SalesOrder", "Sales Order", "销售订单",
          "A complete sales order placed by a customer.",
          "客户下的一个完整销售订单。")
add_class("OnlineOrder", "Online Order", "在线订单",
          "An order whose :onlineOrderFlag is true. Defined class.",
          "在线下单（:onlineOrderFlag 为 true）。等价类。",
          parents=["SalesOrder"])
add_class("HighValueOrder", "High-Value Order", "高价值订单",
          f"An order whose :totalDue is >= {HIGH_VALUE_THRESHOLD}. Defined class.",
          f"订单 :totalDue >= {HIGH_VALUE_THRESHOLD} 的高价值订单。等价类。",
          parents=["SalesOrder"])

add_class("SalesOrderLine", "Sales Order Line", "订单明细行",
          "A single line item within a Sales Order.",
          "销售订单中的一条明细行。")
add_class("DiscountedOrderLine", "Discounted Order Line", "折扣明细行",
          "An order line whose :unitPriceDiscount is > 0. Defined class.",
          ":unitPriceDiscount > 0 的折扣明细行。等价类。",
          parents=["SalesOrderLine"])

add_class("Product", "Product", "产品",
          "A physical sellable product (bicycle, component, clothing, accessory).",
          "可销售的实体产品（自行车、零部件、服装、配件）。")

add_class("ProductCategory", "Product Category", "产品类目",
          "A category in the AdventureWorks product taxonomy. Modelled both as "
          "a class hierarchy (subclasses) and as a class whose individuals are "
          "the named categories.",
          "AdventureWorks 产品分类法中的一个类目。"
          "同时建模为类层次（子类）以及类目命名个体。")

# --------------------------------------------------------------------------- #
# 4. TBox -- Enumeration classes (will receive named individuals later)
# --------------------------------------------------------------------------- #
add_class("OrderStatus", "Order Status", "订单状态",
          "Enumeration of possible Sales Order statuses (1..6).",
          "销售订单状态枚举 (1..6)。")
add_class("AddressType", "Address Type", "地址类型",
          "Enumeration of address usage types (Main Office, Shipping, Billing).",
          "地址类型枚举（主办公地址、收货地址、账单地址）。")
add_class("ShipMethod", "Ship Method", "运输方式",
          "Enumeration of shipping methods.",
          "运输方式枚举。")
add_class("PersonTitle", "Person Title", "称谓",
          "Enumeration of personal titles (Mr, Mrs, Ms, Dr, Prof).",
          "个人称谓枚举（Mr、Mrs、Ms、Dr、Prof）。")
add_class("ProductColor", "Product Color", "产品颜色",
          "Enumeration of colours available for products.",
          "产品可选颜色的枚举。")


# --------------------------------------------------------------------------- #
# 5. TBox -- Object Properties
# --------------------------------------------------------------------------- #
add_op("placedBy", "placed by", "下单人",
       "The Customer who placed this Sales Order.",
       "下此销售订单的客户。",
       domain="SalesOrder", range_="Customer", functional=True)
add_op("placedOrder", "placed order", "下单",
       "Inverse of :placedBy; orders placed by the customer.",
       ":placedBy 的逆属性；客户下的订单。",
       domain="Customer", range_="SalesOrder", inverse="placedBy")

add_op("hasOrderLine", "has order line", "包含明细行",
       "Links a Sales Order to one of its order lines.",
       "将销售订单与其某条明细行关联。",
       domain="SalesOrder", range_="SalesOrderLine")
add_op("partOfOrder", "part of order", "属于订单",
       "Inverse of :hasOrderLine.",
       ":hasOrderLine 的逆属性。",
       domain="SalesOrderLine", range_="SalesOrder",
       inverse="hasOrderLine", functional=True)

add_op("refersToProduct", "refers to product", "引用产品",
       "The Product referenced by this order line.",
       "此明细行所引用的产品。",
       domain="SalesOrderLine", range_="Product", functional=True)
add_op("soldIn", "sold in", "出售于",
       "Order lines that reference this product.",
       "引用此产品的订单明细。",
       domain="Product", range_="SalesOrderLine", inverse="refersToProduct")

add_op("hasShipToAddress", "has ship-to address", "收货地址",
       "The shipping address of a Sales Order.",
       "销售订单的收货地址。",
       domain="SalesOrder", range_="Address", functional=True)
add_op("hasBillToAddress", "has bill-to address", "账单地址",
       "The billing address of a Sales Order.",
       "销售订单的账单地址。",
       domain="SalesOrder", range_="Address", functional=True)

add_op("hasAddressLink", "has address link", "拥有地址关联",
       "Customer side of the reified n-ary CustomerAddressLink.",
       "实化 n 元关系 CustomerAddressLink 的客户端。",
       domain="Customer", range_="CustomerAddressLink")
add_op("linksAddress", "links address", "关联地址",
       "Address side of the reified CustomerAddressLink.",
       "实化关系 CustomerAddressLink 的地址端。",
       domain="CustomerAddressLink", range_="Address", functional=True)
add_op("linksAddressType", "links address type", "关联地址类型",
       "AddressType side of the reified CustomerAddressLink.",
       "实化关系 CustomerAddressLink 的地址类型端。",
       domain="CustomerAddressLink", range_="AddressType", functional=True)

add_op("inCategory", "in category", "属于类目",
       "Direct ProductCategory of this product.",
       "此产品所属的（最细粒度）产品类目。",
       domain="Product", range_="ProductCategory", functional=True)
add_op("containsProduct", "contains product", "包含产品",
       "Inverse of :inCategory.",
       ":inCategory 的逆属性。",
       domain="ProductCategory", range_="Product", inverse="inCategory")

add_op("hasParentCategory", "has parent category", "父类目",
       "The immediate parent in the ProductCategory hierarchy.",
       "产品类目层次的直接父节点。",
       domain="ProductCategory", range_="ProductCategory", transitive=True)

add_op("hasStatus", "has status", "订单状态",
       "OrderStatus of this Sales Order.",
       "此销售订单的状态。",
       domain="SalesOrder", range_="OrderStatus", functional=True)
add_op("hasShipMethod", "has ship method", "运输方式",
       "Shipping method used for this Sales Order.",
       "此销售订单使用的运输方式。",
       domain="SalesOrder", range_="ShipMethod", functional=True)
add_op("hasTitle", "has title", "称谓",
       "Personal title for a Customer.",
       "客户的称谓。",
       domain="Customer", range_="PersonTitle", functional=True)
add_op("hasColor", "has color", "颜色",
       "Color of a Product.",
       "产品的颜色。",
       domain="Product", range_="ProductColor", functional=True)


# --------------------------------------------------------------------------- #
# 6. TBox -- Data Properties
# --------------------------------------------------------------------------- #
# Customer
add_dp("firstName",     "first name",      "名",        "Given name of a person.",          "个人的名。",       domain="Customer", functional=True)
add_dp("middleName",    "middle name",     "中间名",    "Middle name (if any).",           "中间名（如有）。", domain="Customer", functional=True)
add_dp("lastName",      "last name",       "姓",        "Family name of a person.",         "个人的姓。",       domain="Customer", functional=True)
add_dp("nameSuffix",    "name suffix",     "姓名后缀",  "Suffix such as Jr., Sr., II.",     "姓名后缀（Jr./Sr.）。", domain="Customer", functional=True)
add_dp("companyName",   "company name",    "公司名",    "Company name (B2B customers).",   "公司名（B2B 客户）。", domain="Customer", functional=True)
add_dp("emailAddress",  "email address",   "电子邮箱",  "Customer email.",                  "客户电子邮箱。",   domain="Customer", functional=True)
add_dp("phone",         "phone",           "电话",      "Customer phone number.",           "客户电话号码。",   domain="Customer", functional=True)
add_dp("customerId",    "customer id",     "客户编号",  "Original AdventureWorks CustomerID.", "AdventureWorks 原始 CustomerID。", domain="Customer", range_=XSD.integer, functional=True)

# Address
add_dp("addressLine1",  "address line 1",  "地址行1",   "Street address line 1.",            "街道地址第一行。", domain="Address", functional=True)
add_dp("addressLine2",  "address line 2",  "地址行2",   "Street address line 2 (suite/apt).", "街道地址第二行（套房/单元）。", domain="Address", functional=True)
add_dp("city",          "city",            "城市",      "City name.",                       "城市名。",         domain="Address", functional=True)
add_dp("stateProvince", "state / province","州/省",    "State or province code.",          "州或省的代码。",   domain="Address", functional=True)
add_dp("countryRegion", "country / region","国家/地区","Country or region name.",          "国家或地区名。",   domain="Address", functional=True)
add_dp("postalCode",    "postal code",     "邮编",      "Postal / ZIP code.",               "邮政编码。",       domain="Address", functional=True)
add_dp("addressId",     "address id",      "地址编号",  "Original AdventureWorks AddressID.", "AdventureWorks 原始 AddressID。", domain="Address", range_=XSD.integer, functional=True)

# SalesOrder
add_dp("salesOrderId",       "sales order id",        "订单编号",     "Original AdventureWorks SalesOrderID.",  "原始 SalesOrderID。", domain="SalesOrder", range_=XSD.integer, functional=True)
add_dp("salesOrderNumber",   "sales order number",    "订单号",       "Business sales order number (e.g. SO71774).", "业务订单号（如 SO71774）。", domain="SalesOrder", functional=True)
add_dp("revisionNumber",     "revision number",       "版本号",       "Sales order revision number.",            "销售订单版本号。",   domain="SalesOrder", range_=XSD.integer, functional=True)
add_dp("orderDate",          "order date",            "下单日期",     "Date the order was placed.",              "下单日期。",         domain="SalesOrder", range_=XSD.date,    functional=True)
add_dp("dueDate",            "due date",              "应交日期",     "Date the order was due.",                 "订单应交日期。",     domain="SalesOrder", range_=XSD.dateTime, functional=True)
add_dp("shipDate",           "ship date",             "发货日期",     "Date the order shipped.",                 "订单发货日期。",     domain="SalesOrder", range_=XSD.dateTime, functional=True)
add_dp("statusCode",         "status code",           "状态代码",     "Numeric status code 1..6.",               "数字状态码 1..6。",  domain="SalesOrder", range_=XSD.integer, functional=True)
add_dp("onlineOrderFlag",    "online order flag",     "线上订单标志","Whether the order was placed online.",    "订单是否线上下单。", domain="SalesOrder", range_=XSD.boolean, functional=True)
add_dp("purchaseOrderNumber","purchase order number", "采购单号",     "Customer-side purchase order number.",    "客户侧采购单号。",   domain="SalesOrder", functional=True)
add_dp("accountNumber",      "account number",        "账户号",       "Customer account number.",                "客户账户号。",       domain="SalesOrder", functional=True)
add_dp("subTotal",           "sub total",             "小计",         "Order sub total in USD.",                 "订单小计金额（美元）。", domain="SalesOrder", range_=XSD.decimal, functional=True, unit="USD")
add_dp("taxAmt",             "tax amount",            "税额",         "Tax amount in USD.",                      "税额（美元）。",     domain="SalesOrder", range_=XSD.decimal, functional=True, unit="USD")
add_dp("freight",            "freight",               "运费",         "Freight charge in USD.",                  "运费（美元）。",     domain="SalesOrder", range_=XSD.decimal, functional=True, unit="USD")
add_dp("totalDue",           "total due",             "应付总额",     "Grand total due in USD.",                 "应付总额（美元）。", domain="SalesOrder", range_=XSD.decimal, functional=True, unit="USD")

# SalesOrderLine
add_dp("orderQty",           "order qty",             "数量",         "Quantity ordered for this line.",         "此明细订购数量。",   domain="SalesOrderLine", range_=XSD.integer, functional=True)
add_dp("unitPrice",          "unit price",            "单价",         "Unit price in USD.",                      "单价（美元）。",     domain="SalesOrderLine", range_=XSD.decimal, functional=True, unit="USD")
add_dp("unitPriceDiscount",  "unit price discount",   "单价折扣率",   "Discount fraction (0..1).",               "折扣比例（0..1）。", domain="SalesOrderLine", range_=XSD.decimal, functional=True)
add_dp("lineTotal",          "line total",            "行小计",       "Line total in USD.",                      "行小计（美元）。",   domain="SalesOrderLine", range_=XSD.decimal, functional=True, unit="USD")

# Product
add_dp("productId",          "product id",            "产品编号",     "Original AdventureWorks ProductID.",      "原始 ProductID。",   domain="Product", range_=XSD.integer, functional=True)
add_dp("productName",        "product name",          "产品名",       "Product display name.",                   "产品显示名。",       domain="Product", functional=True)
add_dp("productNumber",      "product number",        "产品货号",     "Business product number (e.g. BK-M68B-42).", "业务产品货号。",  domain="Product", functional=True)
add_dp("standardCost",       "standard cost",         "标准成本",     "Standard cost in USD.",                   "标准成本（美元）。", domain="Product", range_=XSD.decimal, functional=True, unit="USD")
add_dp("listPrice",          "list price",            "标价",         "List price in USD.",                      "标价（美元）。",     domain="Product", range_=XSD.decimal, functional=True, unit="USD")
add_dp("frameSizeCm",        "frame size (cm)",       "车架尺寸(cm)","Bicycle frame size in centimetres.",      "自行车车架尺寸（厘米）。", domain="Product", range_=XSD.decimal, functional=True, unit="cm")
add_dp("clothingSize",       "clothing size",         "服装尺寸",     "Clothing size code (S, M, L, XL).",       "服装尺寸编码（S/M/L/XL）。", domain="Product", functional=True)
add_dp("weight",             "weight",                "重量",         "Product weight in grams.",                "产品重量（克）。",   domain="Product", range_=XSD.decimal, functional=True, unit="grams")

# ProductCategory
add_dp("categoryId",         "category id",           "类目编号",     "Original AdventureWorks ProductCategoryID.", "原始 ProductCategoryID。", domain="ProductCategory", range_=XSD.integer, functional=True)
add_dp("categoryName",       "category name",         "类目名",       "Display name of the category.",          "类目显示名。",        domain="ProductCategory", functional=True)


# --------------------------------------------------------------------------- #
# 7. TBox -- Equivalent class axioms (defined classes)
# --------------------------------------------------------------------------- #
from rdflib.collection import Collection

def equivalent_class(cls_local, member_nodes):
    """Asserts cls owl:equivalentClass (intersectionOf members)."""
    cls = to_iri(cls_local)
    if len(member_nodes) == 1:
        g.add((cls, OWL.equivalentClass, member_nodes[0]))
    else:
        eq = BNode()
        g.add((eq, RDF.type, OWL.Class))
        list_node = BNode()
        g.add((eq, OWL.intersectionOf, list_node))
        Collection(g, list_node, member_nodes)
        g.add((cls, OWL.equivalentClass, eq))

# BusinessCustomer ≡ Customer ⊓ ∃ companyName . xsd:string
r1 = restriction("companyName", "someValuesFrom", XSD.string)
equivalent_class("BusinessCustomer", [to_iri("Customer"), r1])

# IndividualCustomer ≡ Customer ⊓ ¬ ∃ companyName . xsd:string
#   Use complementOf
neg = BNode()
g.add((neg, RDF.type, OWL.Class))
r_has_company = restriction("companyName", "someValuesFrom", XSD.string)
g.add((neg, OWL.complementOf, r_has_company))
equivalent_class("IndividualCustomer", [to_iri("Customer"), neg])

# OnlineOrder ≡ SalesOrder ⊓ (onlineOrderFlag value true)
r_online = restriction("onlineOrderFlag", "hasValue", Literal(True))
equivalent_class("OnlineOrder", [to_iri("SalesOrder"), r_online])

# HighValueOrder ≡ SalesOrder ⊓ (totalDue some xsd:decimal[>= HIGH_VALUE_THRESHOLD])
hv_dt = BNode()
g.add((hv_dt, RDF.type, RDFS.Datatype))
g.add((hv_dt, OWL.onDatatype, XSD.decimal))
restr_list = BNode()
g.add((hv_dt, OWL.withRestrictions, restr_list))
hv_facet = BNode()
g.add((hv_facet, XSD.minInclusive, Literal(HIGH_VALUE_THRESHOLD, datatype=XSD.decimal)))
Collection(g, restr_list, [hv_facet])
r_hv = restriction("totalDue", "someValuesFrom", hv_dt)
equivalent_class("HighValueOrder", [to_iri("SalesOrder"), r_hv])

# DiscountedOrderLine ≡ SalesOrderLine ⊓ (unitPriceDiscount some xsd:decimal[> 0])
disc_dt = BNode()
g.add((disc_dt, RDF.type, RDFS.Datatype))
g.add((disc_dt, OWL.onDatatype, XSD.decimal))
disc_restr_list = BNode()
g.add((disc_dt, OWL.withRestrictions, disc_restr_list))
disc_facet = BNode()
g.add((disc_facet, XSD.minExclusive, Literal(0.0, datatype=XSD.decimal)))
Collection(g, disc_restr_list, [disc_facet])
r_disc = restriction("unitPriceDiscount", "someValuesFrom", disc_dt)
equivalent_class("DiscountedOrderLine", [to_iri("SalesOrderLine"), r_disc])

# SalesOrder ⊑  exactly 1 :hasShipToAddress  (cardinality restriction)
exact1 = restriction("hasShipToAddress", "qualifiedCardinality",
                     Literal(1, datatype=XSD.nonNegativeInteger))
g.add((exact1, OWL.onClass, to_iri("Address")))
g.add((to_iri("SalesOrder"), RDFS.subClassOf, exact1))


# --------------------------------------------------------------------------- #
# 8. TBox -- Enum class individuals
# --------------------------------------------------------------------------- #
ORDER_STATUSES = [
    (1, "InProcess",   "处理中"),
    (2, "Approved",    "已批准"),
    (3, "BackOrdered", "缺货延期"),
    (4, "Rejected",    "已拒绝"),
    (5, "Shipped",     "已发货"),
    (6, "Cancelled",   "已取消"),
]
for code, en, zh in ORDER_STATUSES:
    iri = f"status_{en[0].lower() + en[1:]}"
    add_ind(iri, "OrderStatus",
            label_en=en, label_zh=zh,
            comment_en=f"Order status code {code} = {en}.",
            comment_zh=f"订单状态码 {code} = {zh}。")
    g.add((to_iri(iri), AW.statusCode, Literal(code, datatype=XSD.integer)))

ADDRESS_TYPES = [
    ("MainOffice", "Main Office", "主办公地址"),
    ("Shipping",   "Shipping",    "收货地址"),
    ("Billing",    "Billing",     "账单地址"),
]
for slug, en, zh in ADDRESS_TYPES:
    add_ind(f"atype_{slug[0].lower() + slug[1:]}", "AddressType", label_en=en, label_zh=zh)

SHIP_METHODS = [
    ("CARGO TRANSPORT 5",  "Cargo Transport 5", "货运 5"),
    ("XRQ - TRUCK GROUND", "XRQ Truck Ground",  "XRQ 卡车陆运"),
    ("ZY - EXPRESS",       "ZY Express",        "ZY 加急快递"),
]
for raw, en, zh in SHIP_METHODS:
    add_ind(f"ship_{slugify_individual(raw)}", "ShipMethod", label_en=en, label_zh=zh)

PERSON_TITLES = [
    ("Mr.",   "title_mr",   "Mr.",   "先生"),
    ("Mrs.",  "title_mrs",  "Mrs.",  "夫人"),
    ("Ms.",   "title_ms",   "Ms.",   "女士"),
    ("Dr.",   "title_dr",   "Dr.",   "博士"),
    ("Prof.", "title_prof", "Prof.", "教授"),
]
for raw, slug, en, zh in PERSON_TITLES:
    add_ind(slug, "PersonTitle", label_en=en, label_zh=zh)

# Unknown sentinels
add_ind("title_unknown",  "PersonTitle",  label_en="Unknown",  label_zh="未知")
add_ind("color_unknown",  "ProductColor", label_en="Unknown",  label_zh="未知")
add_ind("ship_unknown",   "ShipMethod",   label_en="Unknown",  label_zh="未知")
add_ind("status_unknown", "OrderStatus",  label_en="Unknown",  label_zh="未知")


# --------------------------------------------------------------------------- #
# 9. TBox -- ProductCategory class hierarchy from data
# --------------------------------------------------------------------------- #
with open(os.path.join(DATA_DIR, "categories.json")) as f:
    categories = json.load(f)

cat_class_by_id = {}     # ProductCategoryID -> class local name (CamelCase)
cat_individual_by_id = {}  # ProductCategoryID -> individual local name

for cat in categories:
    cid = cat["ProductCategoryID"]
    name = cat["Name"]
    cls_local = slugify_class(name)             # e.g. MountainBikes
    ind_local = f"category_{cid}"               # e.g. category_5
    cat_class_by_id[cid] = cls_local
    cat_individual_by_id[cid] = ind_local

    parent_id = cat["ParentProductCategoryID"]
    parents = [cat_class_by_id[parent_id]] if parent_id else ["ProductCategory"]
    add_class(cls_local, name, name,
              f"AdventureWorks product category: {name}.",
              f"AdventureWorks 产品类目：{name}。",
              parents=parents)

    # Also create the matching ProductCategory individual
    add_ind(ind_local, "ProductCategory",
            label_en=name, label_zh=name)
    g.add((to_iri(ind_local), AW.categoryId,   Literal(cid, datatype=XSD.integer)))
    g.add((to_iri(ind_local), AW.categoryName, Literal(name)))
    if parent_id:
        g.add((to_iri(ind_local), AW.hasParentCategory,
               to_iri(cat_individual_by_id[parent_id])))


# --------------------------------------------------------------------------- #
# 10. ABox -- Customers
# --------------------------------------------------------------------------- #
with open(os.path.join(DATA_DIR, "customers.json")) as f:
    customers = json.load(f)

TITLE_TO_INDIV = {
    "Mr.":  "title_mr",
    "Mrs.": "title_mrs",
    "Ms.":  "title_ms",
    "Dr.":  "title_dr",
    "Prof.": "title_prof",
}

for c in customers:
    cid = c["CustomerID"]
    iri = f"customer_{cid}"
    label = " ".join(filter(None, [c.get("FirstName"), c.get("LastName")])) or f"Customer {cid}"
    add_ind(iri, "Customer", label_en=label, label_zh=label)
    g.add((to_iri(iri), AW.customerId, Literal(cid, datatype=XSD.integer)))
    if c.get("FirstName"):    g.add((to_iri(iri), AW.firstName,    Literal(c["FirstName"])))
    if c.get("MiddleName"):   g.add((to_iri(iri), AW.middleName,   Literal(c["MiddleName"])))
    if c.get("LastName"):     g.add((to_iri(iri), AW.lastName,     Literal(c["LastName"])))
    if c.get("Suffix"):       g.add((to_iri(iri), AW.nameSuffix,   Literal(c["Suffix"])))
    if c.get("CompanyName"):  g.add((to_iri(iri), AW.companyName,  Literal(c["CompanyName"])))
    if c.get("EmailAddress"): g.add((to_iri(iri), AW.emailAddress, Literal(c["EmailAddress"])))
    if c.get("Phone"):        g.add((to_iri(iri), AW.phone,        Literal(c["Phone"])))
    title = c.get("Title")
    if title and title in TITLE_TO_INDIV:
        g.add((to_iri(iri), AW.hasTitle, to_iri(TITLE_TO_INDIV[title])))
    elif title:
        g.add((to_iri(iri), AW.hasTitle, to_iri("title_unknown")))


# --------------------------------------------------------------------------- #
# 11. ABox -- Addresses
# --------------------------------------------------------------------------- #
with open(os.path.join(DATA_DIR, "addresses.json")) as f:
    addresses = json.load(f)

for a in addresses:
    aid = a["AddressID"]
    iri = f"address_{aid}"
    label = f"{a.get('AddressLine1','')}, {a.get('City','')} {a.get('PostalCode','')}".strip(", ")
    add_ind(iri, "Address", label_en=label, label_zh=label)
    g.add((to_iri(iri), AW.addressId, Literal(aid, datatype=XSD.integer)))
    for k, prop in [("AddressLine1","addressLine1"),("AddressLine2","addressLine2"),
                    ("City","city"),("StateProvince","stateProvince"),
                    ("CountryRegion","countryRegion"),("PostalCode","postalCode")]:
        v = a.get(k)
        if v:
            g.add((to_iri(iri), AW[prop], Literal(v)))


# --------------------------------------------------------------------------- #
# 12. ABox -- CustomerAddressLink (reified n-ary)
# --------------------------------------------------------------------------- #
with open(os.path.join(DATA_DIR, "customer_addresses.json")) as f:
    cust_addrs = json.load(f)

ATYPE_TO_INDIV = {
    "Main Office": "atype_mainOffice",
    "Shipping":    "atype_shipping",
    "Billing":     "atype_billing",
}

for ca in cust_addrs:
    link_iri = f"custaddr_{ca['CustomerID']}_{ca['AddressID']}"
    cust_iri = f"customer_{ca['CustomerID']}"
    addr_iri = f"address_{ca['AddressID']}"
    add_ind(link_iri, "CustomerAddressLink",
            label_en=f"{ca['AddressType']} address of customer {ca['CustomerID']}",
            label_zh=f"客户 {ca['CustomerID']} 的{ca['AddressType']}地址")
    g.add((to_iri(cust_iri), AW.hasAddressLink, to_iri(link_iri)))
    g.add((to_iri(link_iri), AW.linksAddress,   to_iri(addr_iri)))
    atype_indiv = ATYPE_TO_INDIV.get(ca["AddressType"], "atype_mainOffice")
    g.add((to_iri(link_iri), AW.linksAddressType, to_iri(atype_indiv)))


# --------------------------------------------------------------------------- #
# 13. ABox -- Sales Orders
# --------------------------------------------------------------------------- #
with open(os.path.join(DATA_DIR, "orders.json")) as f:
    orders = json.load(f)

STATUS_TO_INDIV = {
    1: "status_inProcess", 2: "status_approved", 3: "status_backOrdered",
    4: "status_rejected",  5: "status_shipped",  6: "status_cancelled",
}

for o in orders:
    oid = o["SalesOrderID"]
    iri = f"order_{oid}"
    add_ind(iri, "SalesOrder",
            label_en=o["SalesOrderNumber"],
            label_zh=o["SalesOrderNumber"])
    g.add((to_iri(iri), AW.salesOrderId,        Literal(oid, datatype=XSD.integer)))
    g.add((to_iri(iri), AW.salesOrderNumber,    Literal(o["SalesOrderNumber"])))
    g.add((to_iri(iri), AW.revisionNumber,      Literal(o["RevisionNumber"], datatype=XSD.integer)))
    if o.get("OrderDate"):
        g.add((to_iri(iri), AW.orderDate,       Literal(o["OrderDate"], datatype=XSD.date)))
    if o.get("DueDate"):
        g.add((to_iri(iri), AW.dueDate,         Literal(o["DueDate"], datatype=XSD.date)))
    if o.get("ShipDate"):
        g.add((to_iri(iri), AW.shipDate,        Literal(o["ShipDate"], datatype=XSD.date)))
    g.add((to_iri(iri), AW.statusCode,          Literal(o["Status"], datatype=XSD.integer)))
    g.add((to_iri(iri), AW.onlineOrderFlag,     Literal(o["OnlineOrderFlag"], datatype=XSD.boolean)))
    if o.get("PurchaseOrderNumber"):
        g.add((to_iri(iri), AW.purchaseOrderNumber, Literal(o["PurchaseOrderNumber"])))
    if o.get("AccountNumber"):
        g.add((to_iri(iri), AW.accountNumber,   Literal(o["AccountNumber"])))
    g.add((to_iri(iri), AW.subTotal,            Literal(o["SubTotal"], datatype=XSD.decimal)))
    g.add((to_iri(iri), AW.taxAmt,              Literal(o["TaxAmt"],   datatype=XSD.decimal)))
    g.add((to_iri(iri), AW.freight,             Literal(o["Freight"],  datatype=XSD.decimal)))
    g.add((to_iri(iri), AW.totalDue,            Literal(o["TotalDue"], datatype=XSD.decimal)))
    g.add((to_iri(iri), AW.placedBy,            to_iri(f"customer_{o['CustomerID']}")))
    g.add((to_iri(iri), AW.hasShipToAddress,    to_iri(f"address_{o['ShipToAddressID']}")))
    g.add((to_iri(iri), AW.hasBillToAddress,    to_iri(f"address_{o['BillToAddressID']}")))
    status_iri = STATUS_TO_INDIV.get(o["Status"], "status_unknown")
    g.add((to_iri(iri), AW.hasStatus,           to_iri(status_iri)))
    sm_iri = f"ship_{slugify_individual(o['ShipMethod'])}"
    if (to_iri(sm_iri), RDF.type, OWL.NamedIndividual) not in g:
        # Not in the predeclared SHIP_METHODS list -> create on the fly
        add_ind(sm_iri, "ShipMethod", label_en=o["ShipMethod"], label_zh=o["ShipMethod"])
    g.add((to_iri(iri), AW.hasShipMethod,       to_iri(sm_iri)))


# --------------------------------------------------------------------------- #
# 14. ABox -- Products
# --------------------------------------------------------------------------- #
with open(os.path.join(DATA_DIR, "products.json")) as f:
    products = json.load(f)

# Distinct colours -> ProductColor individuals
distinct_colors = sorted({p["Color"] for p in products if p.get("Color")})
COLOR_TO_INDIV = {}
for color in distinct_colors:
    iri = f"color_{slugify_individual(color)}"
    COLOR_TO_INDIV[color] = iri
    add_ind(iri, "ProductColor", label_en=color, label_zh=color)

for p in products:
    pid = p["ProductID"]
    iri = f"product_{pid}"
    cat_id = p["ProductCategoryID"]
    cls_local = cat_class_by_id.get(cat_id, "Product")
    # Type the product as :Product AND as its leaf category class
    add_ind(iri, ["Product", cls_local], label_en=p["Name"], label_zh=p["Name"])
    g.add((to_iri(iri), AW.productId,     Literal(pid, datatype=XSD.integer)))
    g.add((to_iri(iri), AW.productName,   Literal(p["Name"])))
    g.add((to_iri(iri), AW.productNumber, Literal(p["ProductNumber"])))
    g.add((to_iri(iri), AW.standardCost,  Literal(p["StandardCost"], datatype=XSD.decimal)))
    g.add((to_iri(iri), AW.listPrice,     Literal(p["ListPrice"],    datatype=XSD.decimal)))
    if p.get("Weight") is not None:
        g.add((to_iri(iri), AW.weight,    Literal(p["Weight"], datatype=XSD.decimal)))
    size = p.get("Size")
    if size:
        # Numeric -> frame size in cm; alphabetic -> clothing size
        if re.fullmatch(r"\d+(\.\d+)?", str(size)):
            g.add((to_iri(iri), AW.frameSizeCm, Literal(float(size), datatype=XSD.decimal)))
        else:
            g.add((to_iri(iri), AW.clothingSize, Literal(str(size))))
    color = p.get("Color")
    if color and color in COLOR_TO_INDIV:
        g.add((to_iri(iri), AW.hasColor, to_iri(COLOR_TO_INDIV[color])))
    g.add((to_iri(iri), AW.inCategory, to_iri(cat_individual_by_id[cat_id])))


# --------------------------------------------------------------------------- #
# 15. ABox -- Sales Order Lines
# --------------------------------------------------------------------------- #
with open(os.path.join(DATA_DIR, "order_lines.json")) as f:
    order_lines = json.load(f)

# Verify (SalesOrderID, ProductID) uniqueness in the sample
seen_pairs = set()
duplicate = False
for line in order_lines:
    key = (line["SalesOrderID"], line["ProductID"])
    if key in seen_pairs:
        duplicate = True
        print(f"!! Duplicate (OrderID, ProductID) detected: {key} -- will fall back to row counter.")
    seen_pairs.add(key)

pair_counter = {}
for line in order_lines:
    oid, pid = line["SalesOrderID"], line["ProductID"]
    if duplicate:
        pair_counter[(oid, pid)] = pair_counter.get((oid, pid), 0) + 1
        suffix = f"_{pair_counter[(oid, pid)]}"
    else:
        suffix = ""
    iri = f"orderline_{oid}_{pid}{suffix}"
    add_ind(iri, "SalesOrderLine",
            label_en=f"Line of {oid} -> product {pid}",
            label_zh=f"订单 {oid} 的产品 {pid} 明细")
    g.add((to_iri(iri), AW.partOfOrder,       to_iri(f"order_{oid}")))
    g.add((to_iri(f"order_{oid}"), AW.hasOrderLine, to_iri(iri)))
    g.add((to_iri(iri), AW.refersToProduct,   to_iri(f"product_{pid}")))
    g.add((to_iri(iri), AW.orderQty,          Literal(line["OrderQty"], datatype=XSD.integer)))
    g.add((to_iri(iri), AW.unitPrice,         Literal(line["UnitPrice"], datatype=XSD.decimal)))
    g.add((to_iri(iri), AW.unitPriceDiscount, Literal(line["UnitPriceDiscount"], datatype=XSD.decimal)))
    g.add((to_iri(iri), AW.lineTotal,         Literal(line["LineTotal"], datatype=XSD.decimal)))


# --------------------------------------------------------------------------- #
# 16. Serialise
# --------------------------------------------------------------------------- #
g.serialize(destination=OUT_FILE, format="pretty-xml")
print(f"\n✅ Wrote {OUT_FILE}")

# Quick stats
n_classes  = len(set(g.subjects(RDF.type, OWL.Class)))
n_op       = len(set(g.subjects(RDF.type, OWL.ObjectProperty)))
n_dp       = len(set(g.subjects(RDF.type, OWL.DatatypeProperty)))
n_ap       = len(set(g.subjects(RDF.type, OWL.AnnotationProperty)))
n_inds     = len(set(g.subjects(RDF.type, OWL.NamedIndividual)))
n_triples  = len(g)
print(f"   Classes              : {n_classes}")
print(f"   Object Properties    : {n_op}")
print(f"   Data   Properties    : {n_dp}")
print(f"   Annotation Properties: {n_ap}")
print(f"   Named Individuals    : {n_inds}")
print(f"   Total triples        : {n_triples}")
