import pulp
import random
from typing import List, Dict, Union, Optional
from datetime import datetime, timedelta
from data_model import Order, Equipment, BOM, Inventory


class SchedulingModel:
    """基于线性规划的精确排产模型"""

    def __init__(self, orders: List[Order], equipment: List[Equipment],
                 boms: Dict[str, BOM], inventory: Inventory):
        self.orders = orders
        self.equipment = equipment
        self.boms = boms
        self.inventory = inventory
        self.model = pulp.LpProblem("Production_Scheduling", pulp.LpMinimize)
        self.variables = {}
        self.solution = None
        self.TIME_HORIZON = 24 * 30  # 30天的时间范围（小时）

    def build_model(self):
        """构建线性规划模型"""
        # 定义决策变量：x[order_id, equipment_id, start_time] = 1 表示订单在设备上start_time开始加工
        for order in self.orders:
            bom = self.boms[order.product_id]
            for process in bom.process_sequence:
                valid_equipment = [eq for eq in self.equipment if eq.process_type == process]
                for eq in valid_equipment:
                    for time in range(self.TIME_HORIZON):
                        var_name = f"x_{order.id}_{eq.id}_{time}"
                        self.variables[var_name] = pulp.LpVariable(var_name, cat='Binary')

        # 定义目标函数：最小化总完成时间
        self.model += pulp.lpSum([
            self.variables[f"x_{order.id}_{eq.id}_{time}"] * (time + self._get_processing_time(order, eq))
            for order in self.orders
            for eq in self.equipment
            for time in range(self.TIME_HORIZON)
            if f"x_{order.id}_{eq.id}_{time}" in self.variables
        ])

        # 添加约束条件
        self._add_process_constraints()
        self._add_equipment_constraints()
        self._add_sequence_constraints()
        self._add_material_constraints()

    def _get_processing_time(self, order: Order, equipment: Equipment) -> int:
        """计算工序处理时间"""
        return max(1, int(order.quantity / equipment.production_rate))  # 向上取整

    def _add_process_constraints(self):
        """添加工序处理约束"""
        for order in self.orders:
            bom = self.boms[order.product_id]
            for process in bom.process_sequence:
                valid_equipment = [eq for eq in self.equipment if eq.process_type == process]
                self.model += pulp.lpSum([
                    self.variables[f"x_{order.id}_{eq.id}_{time}"]
                    for eq in valid_equipment
                    for time in range(self.TIME_HORIZON)
                    if f"x_{order.id}_{eq.id}_{time}" in self.variables
                ]) == 1

    def _add_equipment_constraints(self):
        """添加设备资源约束"""
        for eq in self.equipment:
            for time in range(self.TIME_HORIZON):
                self.model += pulp.lpSum([
                    self.variables[f"x_{order.id}_{eq.id}_{t}"]
                    for order in self.orders
                    for t in range(max(0, time - 10), time + 10)  # 考虑加工时间窗口
                    if f"x_{order.id}_{eq.id}_{t}" in self.variables
                ]) <= 1

    def _add_sequence_constraints(self):
        """添加工序顺序约束"""
        for order in self.orders:
            bom = self.boms[order.product_id]
            for i in range(len(bom.process_sequence) - 1):
                current_process = bom.process_sequence[i]
                next_process = bom.process_sequence[i + 1]
                current_eq = [eq for eq in self.equipment if eq.process_type == current_process]
                next_eq = [eq for eq in self.equipment if eq.process_type == next_process]

                for c_eq in current_eq:
                    for n_eq in next_eq:
                        for t1 in range(self.TIME_HORIZON):
                            for t2 in range(self.TIME_HORIZON):
                                proc_time = self._get_processing_time(order, c_eq)
                                if t2 < t1 + proc_time:
                                    self.model += (
                                            self.variables[f"x_{order.id}_{c_eq.id}_{t1}"] +
                                            self.variables[f"x_{order.id}_{n_eq.id}_{t2}"] <= 1
                                    )

    def _add_material_constraints(self):
        """添加物料约束"""
        for order in self.orders:
            bom = self.boms[order.product_id]
            for eq in self.equipment:
                if eq.process_type in bom.process_sequence:
                    for time in range(self.TIME_HORIZON):
                        # 检查所有原材料是否充足
                        if not all(self.inventory.check_availability(material, qty * order.quantity)
                                   for material, qty in bom.components.items()):
                            self.model += self.variables[f"x_{order.id}_{eq.id}_{time}"] == 0

    def solve(self) -> bool:
        """求解排产模型"""
        try:
            self.model.solve(pulp.PULP_CBC_CMD(msg=False, timeLimit=30))
            if pulp.LpStatus[self.model.status] == 'Optimal':
                self._extract_solution()
                return True
            print(f"精确算法求解状态: {pulp.LpStatus[self.model.status]}")
            return False
        except Exception as e:
            print(f"精确算法求解失败: {e}")
            return False

    def _extract_solution(self):
        """提取求解结果"""
        self.solution = []
        for var_name, var in self.variables.items():
            if var.value() == 1:
                parts = var_name.split('_')
                order_id = parts[1]
                equipment_id = parts[2]
                start_time = int(parts[3])

                # 找到对应的订单和设备
                order = next((o for o in self.orders if o.id == order_id), None)
                equipment = next((eq for eq in self.equipment if eq.id == equipment_id), None)
                if not order or not equipment:
                    continue

                # 计算处理时间
                processing_time = self._get_processing_time(order, equipment)
                end_time = start_time + processing_time

                # 添加到解决方案
                self.solution.append({
                    "order_id": order_id,
                    "equipment_id": equipment_id,
                    "process_type": equipment.process_type,
                    "start_time": start_time,
                    "end_time": end_time
                })

    def get_schedule(self) -> List[Dict]:
        """获取排产计划"""
        if not self.solution:
            return []

        # 按订单分组
        schedule = {}
        for item in self.solution:
            order_id = item["order_id"]
            if order_id not in schedule:
                schedule[order_id] = {"processes": []}
            schedule[order_id]["processes"].append({
                "process_type": item["process_type"],
                "equipment_id": item["equipment_id"],
                "start_time": item["start_time"],
                "end_time": item["end_time"]
            })

        # 转换为列表格式
        result = []
        for order_id, data in schedule.items():
            order = next((o for o in self.orders if o.id == order_id), None)
            if order:
                result.append({
                    "order_id": order_id,
                    "product_id": order.product_id,
                    "quantity": order.quantity,
                    "delivery_date": order.delivery_date,
                    "processes": data["processes"]
                })
        return result


class GeneticAlgorithmScheduler:
    """基于遗传算法的启发式排产算法"""

    def __init__(self, orders: List[Order], equipment: List[Equipment],
                 boms: Dict[str, BOM], inventory: Inventory):
        self.orders = orders
        self.equipment = equipment
        self.boms = boms
        self.inventory = inventory
        self.population_size = 50
        self.generations = 100
        self.crossover_rate = 0.8
        self.mutation_rate = 0.1
        self.TIME_HORIZON = 24 * 30  # 30天的时间范围（小时）

    def create_individual(self) -> List[Dict]:
        """创建一个随机个体（排产方案）"""
        individual = []
        for order in self.orders:
            bom = self.boms[order.product_id]
            order_schedule = {
                "order_id": order.id,
                "processes": []
            }
            current_time = 0
            for process in bom.process_sequence:
                available_equipment = [eq for eq in self.equipment if eq.process_type == process]
                if not available_equipment:
                    continue

                # 按生产效率加权选择设备
                rates = [eq.production_rate for eq in available_equipment]
                total = sum(rates)
                probs = [r / total for r in rates]
                selected_eq = random.choices(available_equipment, weights=probs)[0]

                # 计算处理时间
                processing_time = max(1, int(order.quantity / selected_eq.production_rate))

                # 随机选择开始时间（考虑工序顺序）
                start_time = max(current_time, random.randint(0, self.TIME_HORIZON - processing_time))
                end_time = start_time + processing_time

                order_schedule["processes"].append({
                    "process_type": process,
                    "equipment_id": selected_eq.id,
                    "start_time": start_time,
                    "end_time": end_time
                })
                current_time = end_time

            individual.append(order_schedule)
        return individual

    def initialize_population(self) -> List[List[Dict]]:
        """初始化种群"""
        return [self.create_individual() for _ in range(self.population_size)]

    def fitness_function(self, individual: List[Dict]) -> float:
        """计算适应度（值越大越好）"""
        total_completion_time = 0
        late_orders = 0
        equipment_load = {eq.id: 0 for eq in self.equipment}

        for order_schedule in individual:
            order_id = order_schedule["order_id"]
            order = next((o for o in self.orders if o.id == order_id), None)
            if not order:
                continue

            # 计算订单完成时间
            if not order_schedule["processes"]:
                continue
            completion_time = max(process["end_time"] for process in order_schedule["processes"])
            total_completion_time += completion_time

            # 检查是否延迟
            delivery_time = (order.delivery_date - datetime(1970, 1, 1)).total_seconds() / 3600  # 转换为小时
            if completion_time > delivery_time:
                late_orders += 1

            # 计算设备负载
            for process in order_schedule["processes"]:
                equipment_id = process["equipment_id"]
                duration = process["end_time"] - process["start_time"]
                equipment_load[equipment_id] += duration

        # 计算设备负载均衡度
        load_values = list(equipment_load.values())
        load_balance = 1 - (max(load_values) - min(load_values)) / (self.TIME_HORIZON * 0.5) if load_values else 1

        # 适应度函数：完成时间越短、延迟订单越少、设备越均衡，适应度越高
        fitness = 1 / (1 + total_completion_time / 1000 + late_orders * 500 - load_balance * 100)
        return max(0.0001, fitness)  # 避免适应度为0

    def crossover(self, parent1: List[Dict], parent2: List[Dict]) -> List[Dict]:
        """交叉操作"""
        if random.random() > self.crossover_rate:
            return parent1.copy()

        child = parent1.copy()
        if len(parent1) > 1:
            crossover_point = random.randint(1, len(parent1) - 1)
            child = parent1[:crossover_point] + parent2[crossover_point:]
        return child

    def mutate(self, individual: List[Dict]) -> List[Dict]:
        """变异操作"""
        if random.random() > self.mutation_rate:
            return individual

        if not individual:
            return individual

        # 随机选择一个订单进行变异
        order_index = random.randint(0, len(individual) - 1)
        order_schedule = individual[order_index]
        order_id = order_schedule["order_id"]
        order = next((o for o in self.orders if o.id == order_id), None)
        if not order:
            return individual

        bom = self.boms[order.product_id]
        if not order_schedule["processes"] or len(bom.process_sequence) == 0:
            return individual

        # 随机选择一个工序进行变异
        process_index = random.randint(0, len(order_schedule["processes"]) - 1)
        process = order_schedule["processes"][process_index]

        # 尝试改变设备
        available_equipment = [eq for eq in self.equipment if eq.process_type == process["process_type"]]
        if len(available_equipment) > 1:
            current_eq_id = process["equipment_id"]
            new_eq = random.choice([eq for eq in available_equipment if eq.id != current_eq_id])
            process["equipment_id"] = new_eq.id

            # 重新计算处理时间
            processing_time = max(1, int(order.quantity / new_eq.production_rate))
            process["end_time"] = process["start_time"] + processing_time

            # 更新后续工序的开始时间
            for i in range(process_index + 1, len(order_schedule["processes"])):
                order_schedule["processes"][i]["start_time"] = max(
                    order_schedule["processes"][i]["start_time"],
                    order_schedule["processes"][i - 1]["end_time"] + random.randint(0, 2)
                )
                order_schedule["processes"][i]["end_time"] = (
                        order_schedule["processes"][i]["start_time"] +
                        (order_schedule["processes"][i]["end_time"] - order_schedule["processes"][i]["start_time"])
                )

        return individual

    def evolve(self, population: List[List[Dict]]) -> List[List[Dict]]:
        """进化一代"""
        # 计算适应度并排序
        fitness_scores = [(self.fitness_function(ind), ind) for ind in population]
        fitness_scores.sort(key=lambda x: x[0], reverse=True)

        # 精英保留
        new_population = [fitness_scores[0][1]]  # 保留最佳个体

        # 锦标赛选择
        while len(new_population) < self.population_size:
            tournament = random.sample(fitness_scores, min(5, len(fitness_scores)))
            parent1 = max(tournament, key=lambda x: x[0])[1]
            tournament.remove(max(tournament, key=lambda x: x[0]))
            parent2 = max(tournament, key=lambda x: x[0])[1]

            # 交叉和变异
            child1 = self.crossover(parent1, parent2)
            child1 = self.mutate(child1)
            new_population.append(child1)

            if len(new_population) < self.population_size:
                child2 = self.crossover(parent2, parent1)
                child2 = self.mutate(child2)
                new_population.append(child2)

        return new_population

    def solve(self) -> List[Dict]:
        """运行遗传算法求解"""
        population = self.initialize_population()
        best_fitness = 0
        best_individual = population[0]

        print("遗传算法迭代过程:")
        for gen in range(self.generations):
            population = self.evolve(population)
            current_best = max(population, key=lambda ind: self.fitness_function(ind))
            current_fitness = self.fitness_function(current_best)

            if current_fitness > best_fitness:
                best_fitness = current_fitness
                best_individual = current_best

            if gen % 10 == 0:
                print(f"第 {gen} 代: 最佳适应度 = {best_fitness:.6f}")

        return best_individual

    def get_schedule(self, solution: List[Dict]) -> List[Dict]:
        """将遗传算法解转换为排产计划"""
        result = []
        for order_schedule in solution:
            order_id = order_schedule["order_id"]
            order = next((o for o in self.orders if o.id == order_id), None)
            if not order:
                continue

            result.append({
                "order_id": order_id,
                "product_id": order.product_id,
                "quantity": order.quantity,
                "delivery_date": order.delivery_date,
                "processes": order_schedule["processes"]
            })
        return result