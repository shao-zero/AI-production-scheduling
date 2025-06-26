from typing import List, Dict, Union
from datetime import datetime


class Equipment:
    """设备信息模型"""

    def __init__(self, id: str, name: str, process_type: str,
                 production_rate: float, qualified_rate: float, unqualified_rate: float):
        self.id = id  # 设备ID
        self.name = name  # 设备名称
        self.process_type = process_type  # 所属工序类型
        self.production_rate = production_rate  # 平均每小时产出数量
        self.qualified_rate = qualified_rate  # 合格率
        self.unqualified_rate = unqualified_rate  # 不合格率


class Order:
    """订单信息模型"""

    def __init__(self, id: str, product_id: str, quantity: int,
                 delivery_date: str, priority: int = 1):
        self.id = id  # 订单ID
        self.product_id = product_id  # 产品ID
        self.quantity = quantity  # 订单数量
        self.delivery_date = datetime.strptime(delivery_date, "%Y-%m-%d %H:%M:%S")  # 交付日期
        self.priority = priority  # 订单优先级
        self.status = "pending"  # 订单状态


class BOM:
    """物料清单模型"""

    def __init__(self, product_id: str, components: Dict[str, int],
                 process_sequence: List[str]):
        self.product_id = product_id  # 产品ID
        self.components = components  # 原材料及用量 {原料ID: 数量}
        self.process_sequence = process_sequence  # 生产工序顺序


class Inventory:
    """库存模型"""

    def __init__(self, raw_materials: Dict[str, int], finished_products: Dict[str, int]):
        self.raw_materials = raw_materials  # 原材料库存 {原料ID: 数量}
        self.finished_products = finished_products  # 成品库存 {产品ID: 数量}

    def check_availability(self, material_id: str, quantity: int) -> bool:
        """检查原材料是否充足"""
        return self.raw_materials.get(material_id, 0) >= quantity

    def reserve_materials(self, material_id: str, quantity: int) -> bool:
        """预留原材料"""
        if self.check_availability(material_id, quantity):
            self.raw_materials[material_id] -= quantity
            return True
        return False