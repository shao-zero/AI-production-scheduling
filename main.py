import datetime
from typing import List, Dict
from mes_client import MESAPIClient
from data_model import Order, Equipment, BOM, Inventory
from scheduling import SchedulingModel, GeneticAlgorithmScheduler
from dynamic_scheduler import DynamicOrderRelease, IncrementalScheduler


def format_production_plan(schedule: List[Dict], equipment: List[Equipment]) -> List[Dict]:
    """格式化排产计划为易读格式"""
    equipment_map = {eq.id: eq.name for eq in equipment}  # 设备ID到名称的映射
    formatted_plan = []
    for order in schedule:
        formatted_order = {
            "order_id": order["order_id"],
            "product_id": order["product_id"],
            "quantity": order["quantity"],
            "delivery_date": order["delivery_date"].strftime("%Y-%m-%d %H:%M"),
            "processes": []
        }
        for process in order["processes"]:
            formatted_process = {
                "process_type": process["process_type"],
                "equipment_id": process["equipment_id"],
                "equipment_name": equipment_map.get(process["equipment_id"], "未知设备"),  # 添加设备名称
                "start_time": datetime.datetime.now() + datetime.timedelta(hours=process["start_time"]),
                "end_time": datetime.datetime.now() + datetime.timedelta(hours=process["end_time"]),
                "duration": process["end_time"] - process["start_time"]
            }
            formatted_order["processes"].append(formatted_process)
        formatted_plan.append(formatted_order)
    return formatted_plan


def main():
    """主函数：执行AI排产流程"""
    print("=== AI自动排产系统启动 ===")
    current_time = datetime.datetime.now()
    print(f"当前时间: {current_time.strftime('%Y-%m-%d %H:%M:%S')}\n")

    # 1. 从MES系统获取数据
    mes_client = MESAPIClient()
    equipment_data = mes_client.get_equipment_data()
    order_data = mes_client.get_order_data()
    bom_data = mes_client.get_bom_data()
    inventory_data = mes_client.get_inventory_data()

    # 2. 转换为数据模型
    equipment = [Equipment(**eq) for eq in equipment_data]
    orders = [Order(**ord) for ord in order_data]
    boms = {bom["product_id"]: BOM(**bom) for bom in bom_data}
    inventory = Inventory(**inventory_data)

    # 3. 初始化动态订单释放器
    order_releaser = DynamicOrderRelease(
        equipment=equipment,
        inventory=inventory.raw_materials.copy()
    )

    # 4. 按优先级排序订单
    orders.sort(key=lambda o: o.priority)

    # 5. 分批处理订单（简化为一批）
    order_batches = [orders]  # 实际应用中可实现分批逻辑
    final_schedule = []

    for i, batch in enumerate(order_batches):
        print(f"\n处理批次 {i + 1}/{len(order_batches)}: {[o.id for o in batch]}")

        # 5.1 筛选可释放的订单
        release_orders = []
        for order in batch:
            bom = boms.get(order.product_id)
            if bom and order_releaser.can_release_order(order, bom):
                release_orders.append(order)
                # 释放订单后更新库存
                order_releaser.update_inventory(order, bom)
            else:
                print(f"订单 {order.id} 暂不满足释放条件，将在下一批次重新评估")

        if not release_orders:
            print("本批次没有可释放的订单")
            continue

        print(f"本批次可释放订单: {[o.id for o in release_orders]}")

        # 5.2 生成排产计划
        try:
            print("使用精确算法生成排产计划...")
            scheduler = SchedulingModel(release_orders, equipment, boms, inventory)
            scheduler.build_model()
            if scheduler.solve():
                batch_schedule = scheduler.get_schedule()
                print("精确算法生成排产计划成功")
            else:
                print("精确算法求解失败，使用遗传算法...")
                ga_scheduler = GeneticAlgorithmScheduler(release_orders, equipment, boms, inventory)
                solution = ga_scheduler.solve()
                batch_schedule = ga_scheduler.get_schedule(solution)

        except Exception as e:
            print(f"排产算法执行失败: {e}，使用默认排产")
            batch_schedule = []

        # 5.3 更新设备负载
        order_releaser.update_equipment_load(batch_schedule)

        # 5.4 格式化并添加到最终计划
        formatted_batch = format_production_plan(batch_schedule,equipment)
        final_schedule.extend(formatted_batch)
        print(f"批次 {i + 1} 排产计划生成完成，包含 {len(formatted_batch)} 个订单")

    # 6. 提交排产计划到MES系统
    if final_schedule:
        mes_client.submit_production_plan(final_schedule)
    else:
        print("没有生成排产计划")

    print("\n=== AI自动排产系统执行完毕 ===")


if __name__ == "__main__":
    main()