"""故障排查向导：声明式状态机。

设计要点：
- 流程全部写在 _TOPICS 数据里，节点只描述「问什么、依据哪段手册、选项去哪个节点」，
  执行器不关心业务内容，新增故障主题只需补数据；
- 每个节点和结论都带 basis（文档名/编号/章节/原文），处置单据此生成出处；
- 会话保留答题历史，back 出栈后回到上一节点，满足「每一步可回退」；
- 会话存内存并做 2 小时过期清理，单实例演示足够（不做用户系统）。
"""
import re
import threading
import time
import uuid
from datetime import datetime

# ===== 手册依据（集中定义，结论与步骤复用）=====

B_SAFETY = {
    "doc_title": "故障案例卡——料筒温度异常（A-101）",
    "doc_no": "FC-T-001",
    "heading": "三、排查步骤 第 2 步 / 六、安全提示",
    "quote": "将设备切到手动，停止油泵，切断总电源，挂“禁止合闸”牌，等待料筒冷却至 50 ℃ 以下。"
    "更换加热圈必须断电挂牌，待料筒冷却至 50 ℃ 以下，佩戴耐高温手套。",
}
B_ALARM = {
    "doc_title": "故障案例卡——料筒温度异常（A-101）",
    "doc_no": "FC-T-001",
    "heading": "三、排查步骤 第 1 步",
    "quote": "进入报警历史，确认 A-101 首次出现时间；查看温度趋势，判断是单区异常还是多区同时下降。"
    "单区异常优先查该区加热回路。",
}
B_HEATER = {
    "doc_title": "故障案例卡——料筒温度异常（A-101）",
    "doc_no": "FC-T-001",
    "heading": "三、排查步骤 第 3 步",
    "quote": "该机加热圈额定 3.5 kW/380 V，正常冷态电阻 35～45 Ω；测得无穷大说明开路，需更换。",
}
B_TERMINAL = {
    "doc_title": "故障案例卡——料筒温度异常（A-101）",
    "doc_no": "FC-T-001",
    "heading": "三、排查步骤 第 4 步",
    "quote": "检查加热圈与电箱端子排连接，端子发黑、烧蚀、松动会导致接触电阻过大，"
    "需打磨或更换端子并复紧。",
}
B_THERMO = {
    "doc_title": "故障案例卡——料筒温度异常（A-101）",
    "doc_no": "FC-T-001",
    "heading": "三、排查步骤 第 5 步",
    "quote": "检查热电偶插入深度和固定螺丝，接线端子有无氧化；用标准温度计比对，"
    "偏差超过 ±3 ℃ 更换热电偶。",
}
B_SSR = {
    "doc_title": "故障案例卡——料筒温度异常（A-101）",
    "doc_no": "FC-T-001",
    "heading": "三、排查步骤 第 6 步",
    "quote": "给 SSR 输入信号，测量输出端是否导通；指示灯不亮或输出无电压，"
    "判定 SSR 损坏并更换同规格固态继电器。",
}
B_FUSE = {
    "doc_title": "故障案例卡——料筒温度异常（A-101）",
    "doc_no": "FC-T-001",
    "heading": "三、排查步骤 第 7 步",
    "quote": "确认加热回路保险未熔断；以上均正常仍不加热时，怀疑温控模块输出故障，报设备科检测。",
}
B_RESULT = {
    "doc_title": "故障案例卡——料筒温度异常（A-101）",
    "doc_no": "FC-T-001",
    "heading": "四、本次处置结果",
    "quote": "更换同规格 3.5 kW/380 V 加热圈，紧固接线端子，恢复送电。"
    "重新升温至 225 ℃ 后保温 20 分钟，连续观察 30 分钟温度波动在 ±3 ℃ 以内。",
}
B_PREVENT = {
    "doc_title": "故障案例卡——料筒温度异常（A-101）",
    "doc_no": "FC-T-001",
    "heading": "五、预防措施",
    "quote": "月保养用万用表测量各加热圈电阻并记录，偏差超过 ±10% 提前更换。"
    "周保养检查加热圈接线端子，红外测温枪测端子温度，温差超过 20 ℃ 处理。",
}
B_REFUSE = {
    "doc_title": "故障案例卡——料筒温度异常（A-101）",
    "doc_no": "FC-T-001",
    "heading": "三、排查步骤 第 7 步 / 五、预防措施 第 4 条",
    "quote": "以上均正常仍不加热时，怀疑温控模块输出故障，报设备科检测。"
    "温度偏差报警不得随意放大报警上下限或屏蔽，必须查明原因。",
}


def _opt(opt_id: str, label: str, next_node: str, tone: str = "default") -> dict:
    return {"id": opt_id, "label": label, "next": next_node, "tone": tone}


# ===== 流程数据 =====

_TOPICS: dict[str, dict] = {
    "temp-anomaly": {
        "id": "temp-anomaly",
        "title": "料筒温度异常（A-101）",
        "device": "海天 SA-1600II 注塑机（1600 kN）",
        "summary": "覆盖单区降温、温度波动、局部过热、多区同时异常四类现象，"
        "按手册依次排查加热圈、接线端子、热电偶、SSR、保险与温控模块。",
        "estimated_steps": "4～6 步",
        "start": "safety",
        "nodes": {
            "safety": {
                "title": "安全确认",
                "question": "开始排查前，请确认：设备已停机、切断总电源并挂“禁止合闸”牌，"
                "料筒已冷却至 50 ℃ 以下。",
                "hint": "带电或带温检查可能导致触电、烫伤；未完成安全措施不得继续。",
                "basis": [B_SAFETY],
                "options": [
                    _opt("done", "已停机、断电、挂牌并冷却", "symptom", "safe"),
                    _opt("not_yet", "还没有，先做安全措施", "conclusion:safety_stop", "danger"),
                ],
            },
            "symptom": {
                "title": "现象判断",
                "question": "查看报警历史与温度曲线：A-101 出现时，温度主要表现为哪一种？",
                "hint": "先区分单区还是多区、降温还是波动，再决定查哪条回路。",
                "basis": [B_ALARM],
                "options": [
                    _opt("single_drop", "单个温区持续下降、加热不足", "heater_measure"),
                    _opt("fluctuate", "温度波动大、显示值跳变", "sensor_inspect"),
                    _opt("overheat", "实际温度偏高或持续加热不可控", "overheat_inspect"),
                    _opt("multi_drop", "多个温区同时下降", "power_supply"),
                ],
            },
            "heater_measure": {
                "title": "加热圈电阻",
                "question": "断电冷却后，用万用表电阻档测量该区加热圈（额定 3.5 kW/380 V）"
                "的冷态电阻，读数是多少？",
                "hint": "测量前拔下加热圈接线，手不要接触表笔金属部分。",
                "basis": [B_HEATER],
                "options": [
                    _opt("normal", "35～45 Ω（正常范围）", "terminal_inspect", "safe"),
                    _opt("open", "无穷大或明显大于 100 Ω", "conclusion:heater_open", "danger"),
                    _opt("abnormal", "低于 30 Ω 或在 45～100 Ω 之间", "conclusion:heater_abnormal", "warn"),
                    _opt("unknown", "还没测 / 不会测", "measure_guide"),
                ],
            },
            "measure_guide": {
                "type": "info",
                "title": "加热圈电阻测量方法",
                "question": "按以下步骤测量，测完再回来填写读数。",
                "body": "1. 停机断电挂牌，等待料筒冷却至 50 ℃ 以下。\n"
                "2. 拔下该区加热圈接线端子。\n"
                "3. 万用表打到电阻档 200 Ω 量程，两表笔分别接加热圈两根引线。\n"
                "4. 读数稳定后记录：正常冷态 35～45 Ω，无穷大说明内部断丝。\n"
                "5. 测完恢复接线并复紧端子。",
                "hint": "若万用表表笔或接线端子有油污，先擦拭干净再测。",
                "basis": [B_HEATER, B_SAFETY],
                "options": [_opt("back", "已测量，返回填写读数", "heater_measure")],
            },
            "terminal_inspect": {
                "title": "接线端子",
                "question": "检查该区加热圈接线端子，是否有发黑、烧蚀、松动或氧化？",
                "hint": "端子接触电阻过大会发热，严重时烧蚀端子排。",
                "basis": [B_TERMINAL],
                "options": [
                    _opt("yes", "有发黑、烧蚀、松动或氧化", "conclusion:terminal_fix", "warn"),
                    _opt("no", "端子干净、紧固、无烧蚀", "thermocouple_inspect", "safe"),
                    _opt("unknown", "无法判断", "terminal_guide"),
                ],
            },
            "terminal_guide": {
                "type": "info",
                "title": "端子检查方法",
                "question": "断电后按以下要点检查端子。",
                "body": "1. 打开电箱，目视端子排有无发黑、烧蚀、塑料变形。\n"
                "2. 用螺丝刀复紧端子螺丝，若滑牙或端子开裂则更换。\n"
                "3. 无法判断时拍照记录，报设备科处理，不要带电触碰。",
                "basis": [B_TERMINAL, B_SAFETY],
                "options": [_opt("back", "已检查，返回选择", "terminal_inspect")],
            },
            "thermocouple_inspect": {
                "title": "热电偶比对",
                "question": "用标准温度计与显示温度比对，偏差是否超过 ±3 ℃？",
                "hint": "同时检查热电偶插入深度、固定螺丝和接线端子氧化情况。",
                "basis": [B_THERMO],
                "options": [
                    _opt("yes", "偏差超过 ±3 ℃", "conclusion:thermocouple_replace", "warn"),
                    _opt("no", "偏差在 ±3 ℃ 以内", "ssr_test", "safe"),
                    _opt("unknown", "无法比对", "conclusion:equipment_team"),
                ],
            },
            "ssr_test": {
                "title": "固态继电器",
                "question": "给 SSR 输入加热信号，输出端是否导通、指示灯是否点亮？",
                "hint": "此步骤涉及电箱带电测量，必须由持证电工操作；无法确认时不要强行测试。",
                "basis": [B_SSR],
                "options": [
                    _opt("fail", "不导通或指示灯不亮", "conclusion:ssr_replace", "danger"),
                    _opt("ok", "能正常导通、指示灯亮", "fuse_inspect", "safe"),
                    _opt("unknown", "不会测 / 无法确认", "conclusion:equipment_team"),
                ],
            },
            "fuse_inspect": {
                "title": "保险与温控模块",
                "question": "检查加热回路保险是否熔断？",
                "hint": "保险熔断通常是短路或过流的保护动作，不能只换保险不查原因。",
                "basis": [B_FUSE],
                "options": [
                    _opt("blown", "保险已熔断", "conclusion:fuse_replace", "warn"),
                    _opt("ok", "保险正常", "conclusion:control_module", "warn"),
                    _opt("unknown", "无法判断", "conclusion:equipment_team"),
                ],
            },
            "sensor_inspect": {
                "title": "热电偶与接线",
                "question": "温度波动或跳变时，检查热电偶接线是否松动、氧化，"
                "插入深度和固定是否正常？",
                "hint": "测温信号时有时无，会直接反映为温度显示跳变。",
                "basis": [B_THERMO],
                "options": [
                    _opt("abnormal", "接线松动/氧化，或插入深度异常", "conclusion:sensor_fix", "warn"),
                    _opt("normal", "接线、插入深度和固定均正常", "ssr_test", "safe"),
                    _opt("unknown", "无法判断", "conclusion:equipment_team"),
                ],
            },
            "overheat_inspect": {
                "title": "过热来源",
                "question": "实际温度高于设定或持续加热不可控，优先判断是哪一类？",
                "hint": "先排除测温失真，再判断 SSR 是否击穿常通。",
                "basis": [B_THERMO, B_SSR, B_FUSE],
                "options": [
                    _opt("thermo", "热电偶测温偏差，显示值失真", "conclusion:thermocouple_replace", "warn"),
                    _opt("ssr", "SSR 击穿常通，断电后仍持续加热", "conclusion:ssr_replace", "danger"),
                    _opt("module", "两者都正常，怀疑温控模块输出异常", "conclusion:control_module", "warn"),
                    _opt("unknown", "无法判断", "conclusion:equipment_team"),
                ],
            },
            "power_supply": {
                "title": "多区供电",
                "question": "多个温区同时下降时，检查总电源、主保险和温控模块供电是否正常？",
                "hint": "多区同时异常通常不是单个加热圈问题，优先查供电与主回路。",
                "basis": [B_ALARM, B_FUSE],
                "options": [
                    _opt("abnormal", "总电源、主保险或供电异常", "conclusion:power_fix", "danger"),
                    _opt("normal", "供电正常，但多区仍不加热", "conclusion:equipment_team", "warn"),
                ],
            },
        },
        "conclusions": {
            "safety_stop": {
                "title": "未完成安全措施，禁止继续排查",
                "level": "安全中止",
                "summary": "带电或高温检查可能导致触电、烫伤。请先停机、断电、挂牌，"
                "等待料筒冷却至 50 ℃ 以下，再重新开始诊断。",
                "actions": [
                    "设备切手动，停止油泵，切断总电源。",
                    "挂“禁止合闸”牌，确认无人可误送电。",
                    "等待料筒冷却至 50 ℃ 以下，佩戴耐高温手套再作业。",
                    "完成安全措施后重新开始诊断。",
                ],
                "safety": "安全措施未完成前，不得进行任何拆线、测量或接触加热圈的操作。",
                "basis": [B_SAFETY],
            },
            "heater_open": {
                "title": "该区加热圈开路（内部断丝），需更换",
                "level": "立即处置",
                "summary": "冷态电阻为无穷大，符合手册中加热圈内部断丝的判定，"
                "是该故障案例中概率最高的原因。",
                "actions": [
                    "断电挂牌，待料筒冷却至 50 ℃ 以下。",
                    "更换同规格 3.5 kW/380 V 加热圈。",
                    "紧固接线端子，确认无松动、无烧蚀。",
                    "恢复送电，重新升温至工艺设定并保温 20 分钟。",
                    "连续观察 30 分钟，温度波动应控制在 ±3 ℃ 以内；首件检验合格后复产。",
                ],
                "safety": "更换加热圈必须断电挂牌、佩戴耐高温手套；禁止在加热状态下插拔接线。",
                "basis": [B_HEATER, B_RESULT, B_SAFETY],
            },
            "heater_abnormal": {
                "title": "加热圈阻值异常，建议复测并更换",
                "level": "计划处置",
                "summary": "冷态阻值偏离 35～45 Ω 的正常范围，可能存在局部短路、老化或测量误差，"
                "需复测并与同区其他加热圈对比。",
                "actions": [
                    "断电冷却后复测一次，排除表笔接触不良。",
                    "与同规格加热圈对比阻值，偏差超过 ±10% 建议更换。",
                    "检查接线端子有无发热、氧化。",
                    "更换后按正常升温流程验证温度波动。",
                ],
                "safety": "测量和更换必须断电挂牌、冷却至 50 ℃ 以下。",
                "basis": [B_HEATER, B_PREVENT],
            },
            "terminal_fix": {
                "title": "加热圈接线端子接触不良",
                "level": "立即处置",
                "summary": "端子发黑、烧蚀或松动会导致接触电阻过大，加热回路压降增加、"
                "实际加热功率不足，表现为单区温度下降。",
                "actions": [
                    "断电挂牌，待料筒冷却。",
                    "打磨氧化层或更换烧蚀端子，重新复紧。",
                    "用红外测温枪测端子温度，温差超过 20 ℃ 需处理。",
                    "送电试运行，观察温度曲线 30 分钟。",
                ],
                "safety": "电箱作业由持证电工完成，禁止带电紧固端子。",
                "basis": [B_TERMINAL, B_PREVENT],
            },
            "thermocouple_replace": {
                "title": "热电偶测温偏差超差，需更换",
                "level": "立即处置",
                "summary": "标准温度计比对偏差超过 ±3 ℃，测温信号不能反映真实料温，"
                "会导致温控系统误判并持续加热或加热不足。",
                "actions": [
                    "断电冷却后更换同型号热电偶。",
                    "确认插入深度、固定螺丝和接线端子。",
                    "用标准温度计复校，偏差应在 ±3 ℃ 以内。",
                    "观察温度曲线，确认无跳变。",
                ],
                "safety": "禁止在加热状态下插拔热电偶接线。",
                "basis": [B_THERMO],
            },
            "ssr_replace": {
                "title": "固态继电器（SSR）损坏，需更换",
                "level": "立即处置",
                "summary": "SSR 不导通会导致加热输出中断；击穿常通则会造成持续加热、"
                "实际温度不可控，两种情况都需更换同规格 SSR。",
                "actions": [
                    "断电挂牌，确认加热回路无电。",
                    "更换同规格固态继电器，检查散热与负载接线。",
                    "送电测试加热输出通断正常。",
                    "观察温度 30 分钟，确认无持续加热或温度失控。",
                ],
                "safety": "SSR 输出端可能带 380 V 电压，必须由持证电工测量。",
                "basis": [B_SSR],
            },
            "fuse_replace": {
                "title": "加热回路保险熔断",
                "level": "立即处置",
                "summary": "保险熔断是短路或过流的保护动作，不能只更换保险而不排查原因，"
                "否则可能再次熔断甚至引发火灾。",
                "actions": [
                    "断电挂牌，检查加热圈和线路绝缘。",
                    "排查短路、受潮或机械损伤。",
                    "更换同规格保险。",
                    "送电测试；若再次熔断，停止使用并报设备科。",
                ],
                "safety": "禁止用铜丝或大规格保险代替原保险。",
                "basis": [B_FUSE],
            },
            "control_module": {
                "title": "疑似温控模块输出故障，停机报修",
                "level": "停机报修",
                "summary": "加热圈、端子、热电偶、SSR 和保险均正常仍不加热，"
                "按手册应怀疑温控模块输出故障，需设备科检测。",
                "actions": [
                    "停机断电挂牌，保留报警记录和温度曲线。",
                    "记录已排查项与测量值。",
                    "报设备科检测温控模块。",
                    "禁止短接、屏蔽报警或放大报警上下限。",
                ],
                "safety": "温控模块涉及控制回路，非设备科人员不得擅自拆检。",
                "basis": [B_FUSE, B_REFUSE],
            },
            "sensor_fix": {
                "title": "热电偶接线或安装异常，需清理紧固",
                "level": "立即处置",
                "summary": "热电偶接线松动、氧化或插入深度不足，会造成温度显示跳变，"
                "先按手册清理紧固并复校。",
                "actions": [
                    "断电冷却后清理接线端子氧化物并紧固。",
                    "检查热电偶插入深度和固定螺丝。",
                    "用标准温度计比对，偏差超过 ±3 ℃ 更换热电偶。",
                    "观察温度曲线是否稳定。",
                ],
                "safety": "禁止在加热状态下插拔热电偶接线。",
                "basis": [B_THERMO, B_PREVENT],
            },
            "power_fix": {
                "title": "多区供电异常，先查总电源与主回路",
                "level": "立即处置",
                "summary": "多个温区同时下降通常不是单个加热圈问题，应优先检查总电源、"
                "主保险和温控模块供电。",
                "actions": [
                    "停机断电挂牌。",
                    "由持证电工检查总电源、主保险、接触器和供电线路。",
                    "排除缺相、接触器损坏或主保险熔断。",
                    "恢复后逐区升温，观察各温区曲线。",
                ],
                "safety": "主回路电压高、能量大，必须由持证电工操作。",
                "basis": [B_ALARM, B_FUSE],
            },
            "equipment_team": {
                "title": "现场条件不足，转设备科进一步诊断",
                "level": "停机报修",
                "summary": "当前无法完成关键测量或故障超出常规排查范围，"
                "继续尝试可能带来安全风险，应停机报修并保留现场证据。",
                "actions": [
                    "停机、断电、挂牌。",
                    "保留报警历史、温度曲线和参数设定。",
                    "拍照记录端子、SSR、热电偶和温控模块状态。",
                    "报设备科并说明已完成的排查步骤。",
                ],
                "safety": "未确认故障原因前，禁止强制生产或屏蔽报警。",
                "basis": [B_FUSE, B_REFUSE],
            },
        },
    }
}


class DiagnosisError(Exception):
    """业务异常：路由层转成 400/404/409。"""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


_sessions: dict[str, dict] = {}
_lock = threading.Lock()
_TTL_SECONDS = 2 * 60 * 60


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _cleanup() -> None:
    cutoff = time.time() - _TTL_SECONDS
    for sid in [s for s, item in _sessions.items() if item["_ts"] < cutoff]:
        _sessions.pop(sid, None)


def _topic(topic_id: str) -> dict:
    topic = _TOPICS.get(topic_id)
    if topic is None:
        raise DiagnosisError(f"未知故障主题：{topic_id}", 404)
    return topic


def _node(topic: dict, node_id: str) -> dict:
    node = topic["nodes"].get(node_id)
    if node is None:
        raise DiagnosisError(f"流程节点不存在：{node_id}", 500)
    return node


def _public_node(topic: dict, node_id: str, step_no: int) -> dict:
    node = _node(topic, node_id)
    return {
        "id": node_id,
        "step_no": step_no,
        "type": node.get("type", "question"),
        "title": node["title"],
        "question": node["question"],
        "hint": node.get("hint", ""),
        "body": node.get("body", ""),
        "basis": node.get("basis", []),
        "options": [
            {"id": o["id"], "label": o["label"], "tone": o.get("tone", "default")}
            for o in node["options"]
        ],
    }


def _conclusion(topic: dict, conclusion_id: str) -> dict:
    item = topic["conclusions"].get(conclusion_id)
    if item is None:
        raise DiagnosisError(f"结论不存在：{conclusion_id}", 500)
    return {"id": conclusion_id, **item}


def _report(session: dict) -> dict:
    topic = _TOPIC_BY_ID[session["topic_id"]]
    steps = session["steps"]
    symptom = next(
        (s["answer"] for s in steps if s["node_id"] == "symptom"),
        steps[0]["answer"] if steps else "未记录",
    )
    references: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for step in steps:
        for b in step["basis"]:
            key = (b["doc_no"], b["heading"])
            if key not in seen:
                seen.add(key)
                references.append(b)
    conclusion = _conclusion(topic, session["conclusion_id"])
    for b in conclusion["basis"]:
        key = (b["doc_no"], b["heading"])
        if key not in seen:
            seen.add(key)
            references.append(b)

    return {
        "report_no": f"CZ-{session['created_at'][:10].replace('-', '')}-"
        f"{session['id'][:6].upper()}",
        "created_at": session["created_at"],
        "completed_at": session.get("completed_at"),
        "topic": {
            "id": topic["id"],
            "title": topic["title"],
            "device": topic["device"],
        },
        "symptom": symptom,
        "process": [
            {
                "step": index,
                "node_id": step["node_id"],
                "title": step["title"],
                "question": step["question"],
                "answer": step["answer"],
                "basis": step["basis"],
            }
            for index, step in enumerate(steps, start=1)
        ],
        "conclusion": {
            "title": conclusion["title"],
            "level": conclusion["level"],
            "summary": conclusion["summary"],
            "actions": conclusion["actions"],
            "safety": conclusion["safety"],
        },
        "references": references,
    }


_TOPIC_BY_ID = _TOPICS


def list_topics() -> list[dict]:
    return [
        {
            "id": t["id"],
            "title": t["title"],
            "device": t["device"],
            "summary": t["summary"],
            "estimated_steps": t["estimated_steps"],
        }
        for t in _TOPICS.values()
    ]


def start_session(topic_id: str) -> dict:
    with _lock:
        _cleanup()
        topic = _topic(topic_id)
        sid = uuid.uuid4().hex[:12]
        session = {
            "id": sid,
            "topic_id": topic_id,
            "current": topic["start"],
            "steps": [],
            "status": "active",
            "conclusion_id": None,
            "created_at": _now(),
            "updated_at": _now(),
            "completed_at": None,
            "_ts": time.time(),
        }
        _sessions[sid] = session
        return {
            "session_id": sid,
            "topic": {"id": topic["id"], "title": topic["title"], "device": topic["device"]},
            "node": _public_node(topic, topic["start"], 1),
            "step_no": 1,
            "done": False,
        }


def _get(session_id: str) -> dict:
    session = _sessions.get(session_id)
    if session is None:
        raise DiagnosisError("诊断会话不存在或已过期，请重新开始", 404)
    return session


def get_session(session_id: str) -> dict:
    with _lock:
        session = _get(session_id)
        topic = _TOPIC_BY_ID[session["topic_id"]]
        result = {
            "session_id": session_id,
            "topic": {"id": topic["id"], "title": topic["title"], "device": topic["device"]},
            "status": session["status"],
            "step_no": len(session["steps"]) + (0 if session["status"] == "done" else 1),
            "done": session["status"] == "done",
            "history": [
                {"step": i, "title": s["title"], "question": s["question"], "answer": s["answer"]}
                for i, s in enumerate(session["steps"], start=1)
            ],
        }
        if session["status"] == "done":
            result["conclusion"] = _conclusion(topic, session["conclusion_id"])
            result["report"] = _report(session)
        else:
            result["node"] = _public_node(topic, session["current"], len(session["steps"]) + 1)
        return result


def submit_answer(session_id: str, node_id: str, option_id: str) -> dict:
    with _lock:
        session = _get(session_id)
        if session["status"] == "done":
            raise DiagnosisError("本次诊断已完成，如需修改请先回退", 409)
        topic = _TOPIC_BY_ID[session["topic_id"]]
        if node_id != session["current"]:
            raise DiagnosisError("当前步骤已变化，请刷新后重试", 409)
        node = _node(topic, node_id)
        option = next((o for o in node["options"] if o["id"] == option_id), None)
        if option is None:
            raise DiagnosisError(f"无效选项：{option_id}", 400)

        session["steps"].append(
            {
                "node_id": node_id,
                "title": node["title"],
                "question": node["question"],
                "answer": option["label"],
                "option_id": option["id"],
                "basis": node.get("basis", []),
                "answered_at": _now(),
            }
        )
        session["updated_at"] = _now()
        session["_ts"] = time.time()

        next_id = option["next"]
        if next_id.startswith("conclusion:"):
            conclusion_id = next_id.split(":", 1)[1]
            session["status"] = "done"
            session["conclusion_id"] = conclusion_id
            session["completed_at"] = _now()
            session["current"] = None
            return {
                "session_id": session_id,
                "done": True,
                "step_no": len(session["steps"]),
                "conclusion": _conclusion(topic, conclusion_id),
                "report": _report(session),
            }

        session["current"] = next_id
        return {
            "session_id": session_id,
            "done": False,
            "step_no": len(session["steps"]) + 1,
            "node": _public_node(topic, next_id, len(session["steps"]) + 1),
        }


def go_back(session_id: str) -> dict:
    with _lock:
        session = _get(session_id)
        if not session["steps"]:
            raise DiagnosisError("已经回到第一步，无法继续回退", 409)
        last = session["steps"].pop()
        session["status"] = "active"
        session["conclusion_id"] = None
        session["completed_at"] = None
        session["current"] = last["node_id"]
        session["updated_at"] = _now()
        session["_ts"] = time.time()
        topic = _TOPIC_BY_ID[session["topic_id"]]
        return {
            "session_id": session_id,
            "done": False,
            "step_no": len(session["steps"]) + 1,
            "node": _public_node(topic, last["node_id"], len(session["steps"]) + 1),
        }


def get_report(session_id: str) -> dict:
    with _lock:
        session = _get(session_id)
        if session["status"] != "done":
            raise DiagnosisError("诊断尚未完成，不能生成处置单", 409)
        return _report(session)


def _cell(text: str) -> str:
    """Markdown 表格转义：竖线会破坏表格。"""
    return str(text).replace("|", "\\|").replace("\n", " ")


def report_markdown(session_id: str) -> str:
    report = get_report(session_id)
    lines = [
        "# 设备故障处置单",
        "",
        f"| 项目 | 内容 |",
        f"| --- | --- |",
        f"| 处置单编号 | {report['report_no']} |",
        f"| 生成时间 | {report['completed_at'] or report['created_at']} |",
        f"| 设备 | {_cell(report['topic']['device'])} |",
        f"| 故障主题 | {_cell(report['topic']['title'])} |",
        f"| 故障现象 | {_cell(report['symptom'])} |",
        "",
        "## 一、排查过程",
        "",
        "| 步骤 | 检查项 | 结果 | 手册依据 |",
        "| --- | --- | --- | --- |",
    ]
    for item in report["process"]:
        basis = "；".join(f"{b['doc_no']} {b['heading']}" for b in item["basis"])
        lines.append(
            f"| {item['step']} | {_cell(item['title'])} | {_cell(item['answer'])} | {_cell(basis)} |"
        )

    conclusion = report["conclusion"]
    lines += [
        "",
        "## 二、诊断结论",
        "",
        f"**{conclusion['title']}**（{conclusion['level']}）",
        "",
        conclusion["summary"],
        "",
        "## 三、处置建议",
        "",
    ]
    for index, action in enumerate(conclusion["actions"], start=1):
        lines.append(f"{index}. {action}")
    lines += ["", "## 四、安全提示", "", conclusion["safety"], "", "## 五、依据出处", ""]
    for index, ref in enumerate(report["references"], start=1):
        lines.append(
            f"{index}. 《{ref['doc_title']}》（{ref['doc_no']}）{ref['heading']}："
            f"{ref['quote']}"
        )
    lines += [
        "",
        "## 六、签字确认",
        "",
        "处置人：____________________    审核人：____________________",
        "",
        "日期：____________________",
        "",
        "> 本处置单由「车间智答」故障排查向导依据厂内知识库生成，"
        "处置前请由设备主管复核。",
        "",
    ]
    return "\n".join(lines)
