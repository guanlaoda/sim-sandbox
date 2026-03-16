# 示例场景库

## 1. 航班预订 — 基础

```yaml
scenario_id: "example_flight_basic"
name: "国内航班预订-基础"
category: "flight_booking"
difficulty: easy
user_goal:
  primary_intent: "book_flight"
  slots:
    departure: "北京"
    destination: "上海"
    date: "2026-04-01"
    cabin_class: "economy"
  success_indicators:
    - "已确认预订"
environment:
  data:
    flights:
      - { flight_no: "CA1234", price: 800, time: "08:00" }
      - { flight_no: "MU5678", price: 650, time: "14:00" }
  tools_available:
    - name: "search_flight"
      mock_responses:
        - condition: {}
          response: "返回两个航班"
```

## 2. 退款处理 — 中等难度

```yaml
scenario_id: "example_refund_medium"
name: "退款申请-有隐含约束"
category: "customer_service"
difficulty: medium
user_goal:
  primary_intent: "request_refund"
  slots:
    order_id: "ORD12345"
    reason: "产品质量问题"
  hidden_constraints:
    - "不接受换货，只要退款"
    - "希望三天内到账"
injections:
  - trigger: { at_turn: 4 }
    event_type: "user_adds_detail"
    description: "用户补充说产品还有安全隐患"
```

## 3. 投诉处理 — 高难度

```yaml
scenario_id: "example_complaint_hard"
name: "客户投诉-情绪激动"
category: "complaint"
difficulty: hard
user_goal:
  primary_intent: "file_complaint"
  hidden_constraints:
    - "之前已经投诉过一次没解决"
    - "如果再敷衍就要投诉到监管部门"
```
