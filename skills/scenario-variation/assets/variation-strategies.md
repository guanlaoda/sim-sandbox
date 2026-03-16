# 变体策略参考

## Slot 变体矩阵

| 领域 | 可变 Slot | 变体范围示例 |
|------|-----------|-------------|
| 航班预订 | departure, destination, date | 不同城市、日期组合 |
| 酒店预订 | city, check_in, check_out, room_type | 不同城市、日期、房型 |
| 退款服务 | order_id, reason, amount | 不同金额、理由 |
| 投诉处理 | complaint_type, severity | 不同投诉类别 |

## 难度递增策略

### Easy → Medium
- 添加 1-2 个 hidden_constraints
- 添加 1 个简单 injection (如改日期)

### Medium → Hard
- 添加矛盾约束
- 添加 2+ injections，含需求大幅变更
- 降低 intent_clarity 要求

### Hard → Adversarial
- 加入 prompt injection 尝试
- 加入角色扮演攻击
- 加入连续矛盾请求
