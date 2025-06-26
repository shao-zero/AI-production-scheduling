import requests
import json
from typing import List, Dict
from datetime import datetime, timedelta
from data_model import Equipment, Order, BOM, Inventory

class MESAPIClient:
    """MES系统API客户端"""
    def __init__(self, base_url: str = "http://localhost:8080/api"):
        self.base_url = base_url
        self.headers = {"Content-Type": "application/json"}

    def get_equipment_data(self) -> List[Dict]:
        """获取设备数据（含模拟数据）"""
        try:
            response = requests.get(f"{self.base_url}/equipment", headers=self.headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"获取设备数据失败: {e}，使用模拟数据")
            return [
                {"id": "EQ001", "name": "CNC加工中心A", "process_type": "加工",
                 "production_rate": 10.5, "qualified_rate": 0.98, "unqualified_rate": 0.02},
                {"id": "EQ002", "name": "CNC加工中心B", "process_type": "加工",
                 "production_rate": 9.8, "qualified_rate": 0.97, "unqualified_rate": 0.03},
                {"id": "EQ003", "name": "装配线A", "process_type": "装配",
                 "production_rate": 5.2, "qualified_rate": 0.99, "unqualified_rate": 0.01},
                {"id": "EQ004", "name": "检测线A", "process_type": "检测",
                 "production_rate": 20.0, "qualified_rate": 0.995, "unqualified_rate": 0.005}
            ]

    def get_order_data(self) -> List[Dict]:
        """获取订单数据（含模拟数据）"""
        try:
            response = requests.get(f"{self.base_url}/orders", headers=self.headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"获取订单数据失败: {e}，使用模拟数据")
            now = datetime.now()
            return [
                {"id": "ORD001", "product_id": "P001", "quantity": 100,
                 "delivery_date": (now + timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S"), "priority": 2},
                {"id": "ORD002", "product_id": "P002", "quantity": 50,
                 "delivery_date": (now + timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S"), "priority": 1},
                {"id": "ORD003", "product_id": "P001", "quantity": 200,
                 "delivery_date": (now + timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S"), "priority": 3},
                {"id": "ORD004", "product_id": "P003", "quantity": 80,
                 "delivery_date": (now + timedelta(days=4)).strftime("%Y-%m-%d %H:%M:%S"), "priority": 2},
                {"id": "ORD005", "product_id": "P002", "quantity": 120,
                 "delivery_date": (now + timedelta(days=6)).strftime("%Y-%m-%d %H:%M:%S"), "priority": 3}
            ]

    def get_bom_data(self) -> List[Dict]:
        """获取BOM数据（含模拟数据）"""
        try:
            response = requests.get(f"{self.base_url}/boms", headers=self.headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"获取BOM数据失败: {e}，使用模拟数据")
            return [
                {"product_id": "P001", "components": {"M001": 2, "M002": 1, "M003": 3},
                 "process_sequence": ["加工", "装配", "检测"]},
                {"product_id": "P002", "components": {"M002": 2, "M004": 1, "M005": 2},
                 "process_sequence": ["加工", "检测", "装配"]},
                {"product_id": "P003", "components": {"M001": 1, "M003": 2, "M006": 1},
                 "process_sequence": ["加工", "装配", "检测"]}
            ]

    def get_inventory_data(self) -> Dict:
        """获取库存数据（含模拟数据）"""
        try:
            response = requests.get(f"{self.base_url}/inventory", headers=self.headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"获取库存数据失败: {e}，使用模拟数据")
            return {
                "raw_materials": {"M001": 500, "M002": 300, "M003": 400,
                                 "M004": 200, "M005": 250, "M006": 150},
                "finished_products": {"P001": 50, "P002": 30, "P003": 20}
            }

    def submit_production_plan(self, plan: List[Dict]) -> bool:
        """提交排产计划（模拟提交）"""
        print("\n=== 生成的排产计划 ===")
        for order in plan:
            print(f"订单 {order['order_id']}:")
            for process in order['processes']:
                print(f"  {process['process_type']} - {process['equipment_name']}:")
                print(f"    开始时间: {process['start_time'].strftime('%Y-%m-%d %H:%M')}")
                print(f"    结束时间: {process['end_time'].strftime('%Y-%m-%d %H:%M')}")
                print(f"    持续时间: {process['duration']:.2f}小时")
        print("====================\n")
        return True