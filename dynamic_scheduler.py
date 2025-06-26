from typing import List, Dict, Optional
from datetime import datetime
from data_model import Order, Equipment, BOM, Inventory


class DynamicOrderRelease:
    """动态订单释放器"""

    def __init__(self, equipment: List[Equipment], inventory: Dict[str, int]):
        self.equipment = equipment
        self.inventory = inventory  # 原材料库存
        self.equipment_load = {eq.id: 0 for eq in equipment}  # 设备负载（小时）
        self.CRITICAL_EQUIPMENT_THRESHOLD = 0.8  # 关键设备负载阈值

    def update_equipment_load(self, schedule: List[Dict]):
        """根据排产计划更新设备负载"""
        self.equipment_load = {eq.id: 0 for eq in self.equipment}  # 重置负载

        for order_schedule in schedule:
            for process in order_schedule.get("processes", []):
                equipment_id = process.get("equipment_id")
                start_time = process.get("start_time", 0)
                end_time = process.get("end_time", 0)
                duration = end_time - start_time

                if equipment_id in self.equipment_load:
                    self.equipment_load[equipment_id] += duration

    def update_inventory(self, order: Order, bom: BOM):
        """更新库存（扣减已使用的原材料）"""
        for material_id, required_per_unit in bom.components.items():
            total_required = required_per_unit * order.quantity
            if material_id in self.inventory:
                self.inventory[material_id] -= total_required
                if self.inventory[material_id] < 0:
                    print(
                        f"警告：{material_id} 库存不足！当前库存: {self.inventory[material_id] + total_required}，需求: {total_required}")

    def can_release_order(self, order: Order, bom: BOM) -> bool:
        """检查订单是否可以释放（考虑物料和设备）"""
        # 1. 检查物料可用性
        for material_id, required_per_unit in bom.components.items():
            total_required = required_per_unit * order.quantity
            available = self.inventory.get(material_id, 0)
            if available < total_required:
                print(f"订单 {order.id} 因缺少物料 {material_id} 无法释放 (需要: {total_required}, 现有: {available})")
                return False

        # 2. 检查关键设备负载
        required_processes = set(bom.process_sequence)
        critical_equipment = [eq for eq in self.equipment if eq.process_type in required_processes]

        for eq in critical_equipment:
            utilization = self.equipment_load.get(eq.id, 0) / (24 * 30)  # 30天的总产能
            if utilization > self.CRITICAL_EQUIPMENT_THRESHOLD:
                print(
                    f"订单 {order.id} 因设备 {eq.name} 负载过高无法释放 (利用率: {utilization:.2f} > {self.CRITICAL_EQUIPMENT_THRESHOLD})")
                return False

        return True


class IncrementalScheduler:
    """增量排产器"""

    def __init__(self, base_schedule: List[Dict], orders: List[Order],
                 equipment: List[Equipment], boms: Dict[str, BOM],
                 inventory: Inventory):
        self.base_schedule = base_schedule
        self.orders = orders
        self.equipment = equipment
        self.boms = boms
        self.inventory = inventory
        self.equipment_load = {eq.id: 0 for eq in equipment}
        self._update_equipment_load()

    def _update_equipment_load(self):
        """更新设备负载"""
        self.equipment_load = {eq.id: 0 for eq in self.equipment}
        for order_schedule in self.base_schedule:
            for process in order_schedule.get("processes", []):
                equipment_id = process.get("equipment_id")
                start_time = process.get("start_time", 0)
                end_time = process.get("end_time", 0)
                duration = end_time - start_time

                if equipment_id in self.equipment_load:
                    self.equipment_load[equipment_id] += duration

    def add_new_order(self, new_order: Order) -> List[Dict]:
        """添加新订单到排产计划"""
        bom = self.boms.get(new_order.product_id)
        if not bom:
            print(f"警告：未找到产品 {new_order.product_id} 的BOM")
            return self.base_schedule

        # 检查物料是否充足
        for material_id, required_per_unit in bom.components.items():
            total_required = required_per_unit * new_order.quantity
            if not self.inventory.check_availability(material_id, total_required):
                print(f"新订单 {new_order.id} 物料不足，无法添加")
                return self.base_schedule

        # 为新订单生成排产计划
        new_schedule = {
            "order_id": new_order.id,
            "product_id": new_order.product_id,
            "quantity": new_order.quantity,
            "delivery_date": new_order.delivery_date,
            "processes": []
        }

        current_time = max([process["end_time"] for order in self.base_schedule
                            for process in order.get("processes", [])] or [0])

        for process in bom.process_sequence:
            available_equipment = [eq for eq in self.equipment if eq.process_type == process]
            if not available_equipment:
                print(f"警告：无可用设备处理工序 {process}")
                continue

            # 选择负载最低的设备
            best_eq = min(available_equipment, key=lambda eq: self.equipment_load.get(eq.id, 0))

            # 寻找可用时间窗口
            start_time = self._find_available_time(best_eq, current_time)
            processing_time = max(1, int(new_order.quantity / best_eq.production_rate))
            end_time = start_time + processing_time

            new_schedule["processes"].append({
                "process_type": process,
                "equipment_id": best_eq.id,
                "start_time": start_time,
                "end_time": end_time
            })

            # 更新设备负载
            self.equipment_load[best_eq.id] += processing_time
            current_time = end_time

        # 合并到基础计划
        merged_schedule = self.base_schedule.copy()
        merged_schedule.append(new_schedule)
        return merged_schedule

    def _find_available_time(self, equipment: Equipment, start_time: int) -> int:
        """寻找设备的可用时间窗口"""
        # 简化实现：寻找设备在start_time之后的第一个可用时间
        for time in range(start_time, start_time + 24 * 7):  # 查找未来7天
            is_available = True
            for order_schedule in self.base_schedule:
                for process in order_schedule.get("processes", []):
                    if (process.get("equipment_id") == equipment.id and
                            not (process.get("end_time", 0) <= time or process.get("start_time", 0) >= time + 1)):
                        is_available = False
                        break
                if not is_available:
                    break
            if is_available:
                return time
        return start_time  # 未找到可用时间，直接使用start_time