# 设计说明索引（答辩复习材料）

> 每个核心模块完成后在此登记一页**讲义式**设计说明：为什么这么做、关键参数怎么定、有什么取舍。
> 目标：决赛答辩能用自己的话讲清全部代码。只写思路和决策依据，不贴大段代码。

| 模块 | 状态 | 说明页 |
| --- | --- | --- |
| 文档切分与入库 | ✅ 完成 | [chunking.md](chunking.md) |
| 检索与拒答阈值（30 条校准） | ✅ 完成 | [retrieval.md](retrieval.md)、[calibration.md](calibration.md) |
| RAG 问答生成（含引用） | ✅ 完成 | [rag-generation.md](rag-generation.md) |
| 端云协同路由 | ✅ 完成（本地/云端/拒答三路径实测） | [routing.md](routing.md) |
| 故障诊断状态机与处置单 | ✅ 完成（完整链路 + A4 导出） | [diagnosis.md](diagnosis.md) |
| MCP 工具封装 | ✅ 完成（客户端实测可调用） | [mcp.md](mcp.md) |
| 前端工程 | ✅ 完成（问答/排查/知识库三视图） | [frontend.md](frontend.md) |
| 部署 | ✅ 本地生产态已跑通；公网待服务器信息 | [deployment.md](deployment.md)、[deploy/README.md](../deploy/README.md) |
| 逐项验收与证据 | ✅ 完成 | [acceptance.md](acceptance.md) |
| 交接与维护 | ✅ 完成 | [handover.md](handover.md) |

## 原始记录

- 阈值校准原始数据：[calibration-data.json](calibration-data.json)
- 路由、诊断、MCP 实测输出：[evidence/](evidence/)
- 30 条问句与组别定义：`backend/scripts/calibrate.py`
