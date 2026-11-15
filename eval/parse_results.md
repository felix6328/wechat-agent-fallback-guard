# 指令解析基准（自动生成）

生成时间 2026-11-15 19:59（Asia/Shanghai）。exact match = 解析出的计划与金标完全一致。「LLM 单独」= LLM 输出未通过词表校验时记为错；「LLM+兜底」= 校验失败时退回词表解析（线上实际用法）。

| 方法 | 原测试集+留出集（88） | 口语化改写（36） | 全部（124） | 兜底触发 | P50 ms | P95 ms | ¥/千条 |
|---|---|---|---|---|---|---|---|
| 词表规则 | 88/88 | 12/36 | 100/124 | — | 0.03 | — | 0 |
| V4-Flash 单独 | 88/88 | 36/36 | 124/124 | — | 2535 | 14235 | 3.04 |
| V4-Flash + 词表兜底 | 88/88 | 36/36 | 124/124 | 0 | 2535 | 14235 | 3.04 |
| Qwen2.5-7B 单独 | 76/88 | 25/36 | 101/124 | — | 2001 | 6910 | 0.00 |
| Qwen2.5-7B + 词表兜底 | 79/88 | 26/36 | 105/124 | 9 | 2001 | 6910 | 0.00 |

## 错例（V4-Flash + 兜底 与 词表规则）

- **PP01** 帮我瞅瞅魔都明儿个天气
  - 金标 `{"intent": "weather", "city": "上海", "date": "2026-11-16"}`
  - 词表 ✗ `{"intent": "unknown"}`
  - V4F（llm）✓
- **PP02** 帝都今天冷不冷啊
  - 金标 `{"intent": "weather", "city": "北京", "date": "2026-11-15"}`
  - 词表 ✗ `{"intent": "unknown"}`
  - V4F（llm）✓
- **PP03** 羊城后天会不会下雨
  - 金标 `{"intent": "weather", "city": "广州", "date": "2026-11-17"}`
  - 词表 ✗ `{"intent": "unknown"}`
  - V4F（llm）✓
- **PP04** 冰城明天要穿羽绒服吗
  - 金标 `{"intent": "weather", "city": "哈尔滨", "date": "2026-11-16"}`
  - 词表 ✗ `{"intent": "unknown"}`
  - V4F（llm）✓
- **PP05** 蓉城今儿个天儿咋样
  - 金标 `{"intent": "weather", "city": "成都", "date": "2026-11-15"}`
  - 词表 ✗ `{"intent": "unknown"}`
  - V4F（llm）✓
- **PP06** 杭州明天出门要带伞不
  - 金标 `{"intent": "weather", "city": "杭州", "date": "2026-11-16"}`
  - 词表 ✗ `{"intent": "unknown"}`
  - V4F（llm）✓
- **PP07** 深圳后天热吗
  - 金标 `{"intent": "weather", "city": "深圳", "date": "2026-11-17"}`
  - 词表 ✗ `{"intent": "unknown"}`
  - V4F（llm）✓
- **PP08** 漠河那边现在多少度
  - 金标 `{"intent": "weather", "city": "漠河", "date": "2026-11-15"}`
  - 词表 ✗ `{"intent": "unknown"}`
  - V4F（llm）✓
- **PP09** 明天魔都要下雨的话从家给我叫个车去单位
  - 金标 `{"intent": "weather_ride", "city": "上海", "date": "2026-11-16", "origin": "家", "dest": "公司"}`
  - 词表 ✗ `{"intent": "unknown"}`
  - V4F（llm）✓
- **PP11** 帝都明天下雨的话，帮我从家叫车到虹桥火车站
  - 金标 `{"intent": "weather_ride", "city": "北京", "date": "2026-11-16", "origin": "家", "dest": "虹桥火车站"}`
  - 词表 ✗ `{"intent": "ride", "origin": "家", "dest": "虹桥火车站"}`
  - V4F（llm）✓
- **PP12** 杨国福有啥好吃的
  - 金标 `{"intent": "food_menu", "restaurant": "杨国福麻辣烫", "dish": null}`
  - 词表 ✗ `{"intent": "unknown"}`
  - V4F（llm）✓
- **PP16** 老王家黄焖鸡有排骨饭不
  - 金标 `{"intent": "food_menu", "restaurant": "老王黄焖鸡", "dish": "黄焖排骨饭"}`
  - 词表 ✗ `{"intent": "unknown"}`
  - V4F（llm）✓
- **PP18** 沙县整两份蒸饺一碗拌面
  - 金标 `{"intent": "food_order", "restaurant": "沙县小吃", "items": [{"name": "蒸饺", "qty": 2}, {"name": "拌面", "qty": 1}], "pay": false}`
  - 词表 ✗ `{"intent": "food_menu", "restaurant": "沙县小吃", "dish": "拌面"}`
  - V4F（llm）✓
- **PP21** 川味小馆要个水煮鱼
  - 金标 `{"intent": "food_order", "restaurant": "川味小馆", "items": [{"name": "水煮鱼", "qty": 1}], "pay": false}`
  - 词表 ✗ `{"intent": "food_menu", "restaurant": "川味小馆", "dish": "水煮鱼"}`
  - V4F（llm）✓
- **PP22** 帮我订份鸡腿饭，沙县的，付款
  - 金标 `{"intent": "food_order", "restaurant": "沙县小吃", "items": [{"name": "鸡腿饭", "qty": 1}], "pay": true}`
  - 词表 ✗ `{"intent": "food_menu", "restaurant": "沙县小吃", "dish": "鸡腿饭"}`
  - V4F（llm）✓
- **PP24** 老王黄焖鸡点个排骨饭再来瓶可乐
  - 金标 `{"intent": "food_order", "restaurant": "老王黄焖鸡", "items": [{"name": "黄焖排骨饭", "qty": 1}, {"name": "可乐", "qty": 1}], "pay": false}`
  - 词表 ✗ `{"intent": "food_order", "restaurant": "老王黄焖鸡", "items": [{"name": "可乐", "qty": 1}], "pay": false}`
  - V4F（llm）✓
- **PP25** 从单位打车去机场大概多少钱
  - 金标 `{"intent": "ride", "origin": "公司", "dest": "浦东机场"}`
  - 词表 ✗ `{"intent": "unknown"}`
  - V4F（llm）✓
- **PP26** 家到公司打个车要多少
  - 金标 `{"intent": "ride", "origin": "家", "dest": "公司"}`
  - 词表 ✗ `{"intent": "unknown"}`
  - V4F（llm）✓
- **PP27** 机场打车回公司多少钱
  - 金标 `{"intent": "ride", "origin": "浦东机场", "dest": "公司"}`
  - 词表 ✗ `{"intent": "unknown"}`
  - V4F（llm）✓
- **PP28** 帮我叫个车，从家去火车站
  - 金标 `{"intent": "ride", "origin": "家", "dest": "虹桥火车站"}`
  - 词表 ✗ `{"intent": "unknown"}`
  - V4F（llm）✓
- **PP29** 从家走到地铁站要多久
  - 金标 `{"intent": "route", "origin": "家", "dest": "地铁站", "mode": "walk"}`
  - 词表 ✗ `{"intent": "unknown"}`
  - V4F（llm）✓
- **PP30** 家到虹桥站开车怎么走
  - 金标 `{"intent": "route", "origin": "家", "dest": "虹桥火车站", "mode": "drive"}`
  - 词表 ✗ `{"intent": "unknown"}`
  - V4F（llm）✓
- **PP35** 哈尔滨明天零下几度
  - 金标 `{"intent": "weather", "city": "哈尔滨", "date": "2026-11-16"}`
  - 词表 ✗ `{"intent": "unknown"}`
  - V4F（llm）✓
- **PP36** 一点点两杯波霸奶茶，付钱
  - 金标 `{"intent": "food_order", "restaurant": "一点点", "items": [{"name": "波霸奶茶", "qty": 2}], "pay": true}`
  - 词表 ✗ `{"intent": "food_order", "restaurant": "一点点", "items": [{"name": "波霸奶茶", "qty": 2}], "pay": false}`
  - V4F（llm）✓