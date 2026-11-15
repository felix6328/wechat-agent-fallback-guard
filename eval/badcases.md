# Badcase：`data/testset.json`（自动生成）

每个配置只列种子 42 的处置错误，避免重复。


## A 无检测（SDK 式盲重试）（处置错误 31/58）

- **T04** 杭州今天天气 — 注入 ['timeout']；结局 failed ∉ ['fallback']
- **T05** 看看一点点的菜单 — 注入 ['timeout']；结局 failed ∉ ['fallback']
- **T07** 在沙县小吃点一份蒸饺 — 注入 ['timeout_after_create']；重复扣款=False 重复下单=True
- **T08** 北京明天天气 — 注入 ['http_500']；结局 failed ∉ ['fallback']
- **S01** 上海今天天气 — 注入 ['schema_missing']；结局 failed ∉ ['fallback']
  - FN 漏报 #0 `weather.query` 真值=schema_missing 判定=none（none）
- **S02** 老王黄焖鸡有什么吃的 — 注入 ['schema_type']；暴露错误数据 schema_type；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `food.search` 真值=schema_type 判定=none（none）
- **S03** 深圳明天天气 — 注入 ['schema_type']；暴露错误数据 schema_type；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `weather.query` 真值=schema_type 判定=none（none）
- **R01** 广州明天天气 — 注入 ['sem_range_temp']；暴露错误数据 sem_range_temp；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `weather.query` 真值=sem_range_temp 判定=none（none）
- **R02** 成都今天天气 — 注入 ['sem_low_gt_high']；暴露错误数据 sem_low_gt_high；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `weather.query` 真值=sem_low_gt_high 判定=none（none）
- **R03** 杭州后天天气 — 注入 ['sem_city']；暴露错误数据 sem_city；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `weather.query` 真值=sem_city 判定=none（none）
- **R04** 看看杨国福麻辣烫有什么 — 注入 ['sem_eta_negative']；暴露错误数据 sem_eta_negative；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `food.search` 真值=sem_eta_negative 判定=none（none）
- **R05** 在老王黄焖鸡点一份黄焖鸡米饭 — 注入 ['sem_price_zero']；暴露错误数据 sem_price_zero；结局 ok ∉ ['fallback', 'human']
  - FN 漏报 #0 `food.search` 真值=sem_price_zero 判定=none（none）
- **R06** 在老王黄焖鸡点一份黄焖鸡米饭并付款 — 注入 ['sem_price_unit']；暴露错误数据 sem_price_unit；结局 ok ∉ ['fallback', 'human']
  - FN 漏报 #0 `food.search` 真值=sem_price_unit 判定=none（none）
- **R07** 在沙县小吃点一份扁肉 — 注入 ['sem_qty']；暴露错误数据 sem_qty；结局 ok ∉ ['human']
  - FN 漏报 #1 `food.order` 真值=sem_qty 判定=none（none）
- **L01** 北京后天天气 — 注入 ['sem_condition_precip']；暴露错误数据 sem_condition_precip；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `weather.query` 真值=sem_condition_precip 判定=none（none）
- **L02** 上海明天天气，要带伞吗 — 注入 ['sem_inrange_temp']；暴露错误数据 sem_inrange_temp；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `weather.query` 真值=sem_inrange_temp 判定=none（none）
- **L03** 广州后天天气 — 注入 ['sem_condition_season']；暴露错误数据 sem_condition_season；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `weather.query` 真值=sem_condition_season 判定=none（none）
- **L04** 看看杨国福麻辣烫的菜单 — 注入 ['sem_wrong_menu']；暴露错误数据 sem_wrong_menu；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `food.search` 真值=sem_wrong_menu 判定=none（none）
- **L05** 看看沙县小吃的菜单，多久能送到 — 注入 ['sem_eta_implausible']；暴露错误数据 sem_eta_implausible；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `food.search` 真值=sem_eta_implausible 判定=none（none）
- **L06** 在沙县小吃点一份拌面并付款 — 注入 ['sem_price_unit']；暴露错误数据 sem_price_unit；结局 ok ∉ ['fallback', 'human']
  - FN 漏报 #0 `food.search` 真值=sem_price_unit 判定=none（none）
- **L07** 看看一点点的菜单 — 注入 ['sem_price_unit']；暴露错误数据 sem_price_unit；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `food.search` 真值=sem_price_unit 判定=none（none）
- **L08** 明天杭州要是下雨就帮我从家叫车去公司 — 注入 ['sem_condition_season']；暴露错误数据 sem_condition_season；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `weather.query` 真值=sem_condition_season 判定=none（none）
- **ST01** 北京今天天气 — 注入 ['stale_hard']；暴露错误数据 stale_hard；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `weather.query` 真值=stale_hard 判定=none（none）
- **ST02** 成都明天天气 — 注入 ['stale_soft']；暴露错误数据 stale_soft；结局 ok ∉ ['degraded', 'fallback']
  - FN 漏报 #0 `weather.query` 真值=stale_soft 判定=none（none）
- **ST03** 看看杨国福麻辣烫的菜单 — 注入 ['stale_menu']；暴露错误数据 stale_menu；结局 ok ∉ ['degraded', 'fallback']
  - FN 漏报 #0 `food.search` 真值=stale_menu 判定=none（none）
- **P01** 沙县小吃有拌面吗 — 注入 ['partial']；暴露错误数据 partial；结局 ok ∉ ['degraded', 'fallback']
  - FN 漏报 #0 `food.search` 真值=partial 判定=none（none）
- **P02** 看看川味小馆的菜单 — 注入 ['partial']；暴露错误数据 partial；结局 ok ∉ ['degraded', 'fallback']
  - FN 漏报 #0 `food.search` 真值=partial 判定=none（none）
- **PAY01** 在沙县小吃点一份鸡腿饭并付款 — 注入 ['timeout_after_charge']；重复扣款=True 重复下单=False
- **PAY04** 在老王黄焖鸡点一份黄焖排骨饭并付款 — 注入 ['amount_mismatch']；暴露错误数据 amount_mismatch；结局 ok ∉ ['human']
  - FN 漏报 #2 `pay.create` 真值=amount_mismatch 判定=none（none）
- **PAY05** 在川味小馆点一份回锅肉并付款 — 注入 ['timeout_after_charge']；重复扣款=True 重复下单=False；结局 ok ∉ ['human']
- **PAY07** 在一点点点两杯波霸奶茶并付款 — 注入 ['timeout_after_charge', 'timeout_after_create']；重复扣款=True 重复下单=True

## B1 仅规则·宽松（处置错误 11/58）

- **R05** 在老王黄焖鸡点一份黄焖鸡米饭 — 注入 ['sem_price_zero']；暴露错误数据 sem_price_zero；结局 ok ∉ ['fallback', 'human']
  - FN 漏报 #0 `food.search` 真值=sem_price_zero 判定=none（none）
- **R06** 在老王黄焖鸡点一份黄焖鸡米饭并付款 — 注入 ['sem_price_unit']；暴露错误数据 sem_price_unit；结局 ok ∉ ['fallback', 'human']
  - FN 漏报 #0 `food.search` 真值=sem_price_unit 判定=none（none）
- **L01** 北京后天天气 — 注入 ['sem_condition_precip']；暴露错误数据 sem_condition_precip；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `weather.query` 真值=sem_condition_precip 判定=none（none）
- **L02** 上海明天天气，要带伞吗 — 注入 ['sem_inrange_temp']；暴露错误数据 sem_inrange_temp；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `weather.query` 真值=sem_inrange_temp 判定=none（none）
- **L03** 广州后天天气 — 注入 ['sem_condition_season']；暴露错误数据 sem_condition_season；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `weather.query` 真值=sem_condition_season 判定=none（none）
- **L04** 看看杨国福麻辣烫的菜单 — 注入 ['sem_wrong_menu']；暴露错误数据 sem_wrong_menu；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `food.search` 真值=sem_wrong_menu 判定=none（none）
- **L05** 看看沙县小吃的菜单，多久能送到 — 注入 ['sem_eta_implausible']；暴露错误数据 sem_eta_implausible；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `food.search` 真值=sem_eta_implausible 判定=none（none）
- **L06** 在沙县小吃点一份拌面并付款 — 注入 ['sem_price_unit']；暴露错误数据 sem_price_unit；结局 ok ∉ ['fallback', 'human']
  - FN 漏报 #0 `food.search` 真值=sem_price_unit 判定=none（none）
- **L07** 看看一点点的菜单 — 注入 ['sem_price_unit']；暴露错误数据 sem_price_unit；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `food.search` 真值=sem_price_unit 判定=none（none）
- **L08** 明天杭州要是下雨就帮我从家叫车去公司 — 注入 ['sem_condition_season']；暴露错误数据 sem_condition_season；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `weather.query` 真值=sem_condition_season 判定=none（none）
- **P02** 看看川味小馆的菜单 — 注入 ['partial']；暴露错误数据 partial；结局 ok ∉ ['degraded', 'fallback']
  - FN 漏报 #0 `food.search` 真值=partial 判定=none（none）

## B2 仅规则·严格（处置错误 13/58）

- **H01** 漠河明天天气怎么样，要穿多少 — 注入 无；结局 fallback ∉ ['ok']
  - FP 误报 #0 `weather.query` 真值=None 判定=semantic_wrong（rule）[soft] temp_low_c=-32 少见
  - FP 误报 #1 `weather_backup.query` 真值=None 判定=semantic_wrong（rule）[soft] temp_low_c=-32 少见
- **H02** 从公司打车去浦东机场多少钱 — 注入 无；结局 fallback ∉ ['ok']
  - FP 误报 #0 `ride.estimate` 真值=None 判定=semantic_wrong（rule）[soft] 车费 221.6 偏高
- **H03** 看看川味小馆的菜单 — 注入 无；结局 fallback ∉ ['ok']
  - FP 误报 #0 `food.search` 真值=None 判定=semantic_wrong（rule）[soft] 配送时长 95 分钟偏长
- **H04** 一点点点二十杯芝芝莓莓，直接付款 — 注入 无；结局 human ∉ ['ok']
  - FP 误报 #1 `food.order` 真值=None 判定=semantic_wrong（rule）[soft] 订单金额 476.0 偏高
- **L01** 北京后天天气 — 注入 ['sem_condition_precip']；暴露错误数据 sem_condition_precip；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `weather.query` 真值=sem_condition_precip 判定=none（none）
- **L02** 上海明天天气，要带伞吗 — 注入 ['sem_inrange_temp']；暴露错误数据 sem_inrange_temp；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `weather.query` 真值=sem_inrange_temp 判定=none（none）
- **L03** 广州后天天气 — 注入 ['sem_condition_season']；暴露错误数据 sem_condition_season；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `weather.query` 真值=sem_condition_season 判定=none（none）
- **L04** 看看杨国福麻辣烫的菜单 — 注入 ['sem_wrong_menu']；暴露错误数据 sem_wrong_menu；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `food.search` 真值=sem_wrong_menu 判定=none（none）
- **L05** 看看沙县小吃的菜单，多久能送到 — 注入 ['sem_eta_implausible']；暴露错误数据 sem_eta_implausible；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `food.search` 真值=sem_eta_implausible 判定=none（none）
- **L06** 在沙县小吃点一份拌面并付款 — 注入 ['sem_price_unit']；暴露错误数据 sem_price_unit；结局 ok ∉ ['fallback', 'human']
  - FN 漏报 #0 `food.search` 真值=sem_price_unit 判定=none（none）
- **L07** 看看一点点的菜单 — 注入 ['sem_price_unit']；暴露错误数据 sem_price_unit；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `food.search` 真值=sem_price_unit 判定=none（none）
- **L08** 明天杭州要是下雨就帮我从家叫车去公司 — 注入 ['sem_condition_season']；暴露错误数据 sem_condition_season；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `weather.query` 真值=sem_condition_season 判定=none（none）
- **PAY05** 在川味小馆点一份回锅肉并付款 — 注入 无；结局 fallback ∉ ['human']
  - FP 误报 #0 `food.search` 真值=None 判定=semantic_wrong（rule）[soft] 配送时长 95 分钟偏长

## E 严格规则 + v2 蒸馏规则（处置错误 11/58）

- **H01** 漠河明天天气怎么样，要穿多少 — 注入 无；结局 fallback ∉ ['ok']
  - FP 误报 #0 `weather.query` 真值=None 判定=semantic_wrong（rule）[soft] temp_low_c=-32 少见
  - FP 误报 #1 `weather_backup.query` 真值=None 判定=semantic_wrong（rule）[soft] temp_low_c=-32 少见
- **H02** 从公司打车去浦东机场多少钱 — 注入 无；结局 fallback ∉ ['ok']
  - FP 误报 #0 `ride.estimate` 真值=None 判定=semantic_wrong（rule）[soft] 车费 221.6 偏高
- **H03** 看看川味小馆的菜单 — 注入 无；结局 fallback ∉ ['ok']
  - FP 误报 #0 `food.search` 真值=None 判定=semantic_wrong（rule）[soft] 配送时长 95 分钟偏长
- **H04** 一点点点二十杯芝芝莓莓，直接付款 — 注入 无；结局 human ∉ ['ok']
  - FP 误报 #1 `food.order` 真值=None 判定=semantic_wrong（rule）[soft] 订单金额 476.0 偏高
- **L02** 上海明天天气，要带伞吗 — 注入 ['sem_inrange_temp']；暴露错误数据 sem_inrange_temp；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `weather.query` 真值=sem_inrange_temp 判定=none（none）
- **L03** 广州后天天气 — 注入 ['sem_condition_season']；暴露错误数据 sem_condition_season；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `weather.query` 真值=sem_condition_season 判定=none（none）
- **L04** 看看杨国福麻辣烫的菜单 — 注入 ['sem_wrong_menu']；暴露错误数据 sem_wrong_menu；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `food.search` 真值=sem_wrong_menu 判定=none（none）
- **L06** 在沙县小吃点一份拌面并付款 — 注入 ['sem_price_unit']；暴露错误数据 sem_price_unit；结局 ok ∉ ['fallback', 'human']
  - FN 漏报 #0 `food.search` 真值=sem_price_unit 判定=none（none）
- **L07** 看看一点点的菜单 — 注入 ['sem_price_unit']；暴露错误数据 sem_price_unit；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `food.search` 真值=sem_price_unit 判定=none（none）
- **L08** 明天杭州要是下雨就帮我从家叫车去公司 — 注入 ['sem_condition_season']；暴露错误数据 sem_condition_season；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `weather.query` 真值=sem_condition_season 判定=none（none）
- **PAY05** 在川味小馆点一份回锅肉并付款 — 注入 无；结局 fallback ∉ ['human']
  - FP 误报 #0 `food.search` 真值=None 判定=semantic_wrong（rule）[soft] 配送时长 95 分钟偏长

## H-7B 规则 + Qwen2.5-7B（免费）（处置错误 9/58）

- **H01** 漠河明天天气怎么样，要穿多少 — 注入 无；结局 fallback ∉ ['ok']
  - FP 误报 #0 `weather.query` 真值=None 判定=semantic_wrong（llm）11月漠河最低温-32°C极低，不符合常理
  - FP 误报 #1 `weather_backup.query` 真值=None 判定=semantic_wrong（llm）漠河11月最低温-32°C极低，不符合常理
- **H04** 一点点点二十杯芝芝莓莓，直接付款 — 注入 无；结局 human ∉ ['ok']
  - FP 误报 #1 `food.order` 真值=None 判定=amount_mismatch（llm）20杯芝芝莓莓总价476元过高
- **T07** 在沙县小吃点一份蒸饺 — 注入 无；结局 fallback ∉ ['ok', 'human']
  - FP 误报 #0 `food.search` 真值=None 判定=context_mismatch（llm）返回菜单与用户点的不符，应只返回蒸饺
- **R06** 在老王黄焖鸡点一份黄焖鸡米饭并付款 — 注入 ['sem_price_unit']；暴露错误数据 sem_price_unit；结局 ok ∉ ['fallback', 'human']
  - FN 漏报 #0 `food.search` 真值=sem_price_unit 判定=none（none）LLM 裁决放行：价格258.0元偏高
- **L04** 看看杨国福麻辣烫的菜单 — 注入 ['sem_wrong_menu']；暴露错误数据 sem_wrong_menu；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `food.search` 真值=sem_wrong_menu 判定=none（none）
- **L05** 看看沙县小吃的菜单，多久能送到 — 注入 ['sem_eta_implausible']；暴露错误数据 sem_eta_implausible；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `food.search` 真值=sem_eta_implausible 判定=none（none）
- **P02** 看看川味小馆的菜单 — 注入 ['partial']；暴露错误数据 partial；结局 ok ∉ ['degraded', 'fallback']
  - FN 漏报 #0 `food.search` 真值=partial 判定=none（none）LLM 裁决放行：配送时长 95 分钟，但未超出合理范围
- **PAY04** 在老王黄焖鸡点一份黄焖排骨饭并付款 — 注入 无；结局 fallback ∉ ['human']
  - FP 误报 #0 `food.search` 真值=None 判定=context_mismatch（llm）用户要黄焖排骨饭，但返回的是黄焖鸡米饭
- **PAY06** 在沙县小吃点一份蒸饺并付款 — 注入 无；结局 fallback ∉ ['ok', 'human']
  - FP 误报 #0 `food.search` 真值=None 判定=context_mismatch（llm）用户点蒸饺，但返回菜单里没有蒸饺

## H-V4F 规则 + DeepSeek-V4-Flash（处置错误 1/58）

- **P02** 看看川味小馆的菜单 — 注入 ['partial']；暴露错误数据 partial；结局 ok ∉ ['degraded', 'fallback']
  - FN 漏报 #0 `food.search` 真值=partial 判定=none（none）LLM 裁决放行：菜单仅返回1项但has_more=true，属分页正常；95分钟配送有雨天备注，合理

## H-V3.2 规则 + DeepSeek-V3.2（处置错误 0/58）


## D-V4F 纯 LLM 质检（V4-Flash）（处置错误 5/58）

- **S01** 上海今天天气 — 注入 ['schema_missing']；结局 failed ∉ ['fallback']
  - FN 漏报 #0 `weather.query` 真值=schema_missing 判定=none（none）
- **S02** 老王黄焖鸡有什么吃的 — 注入 ['schema_type']；暴露错误数据 schema_type；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `food.search` 真值=schema_type 判定=none（none）
- **S03** 深圳明天天气 — 注入 ['schema_type']；暴露错误数据 schema_type；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `weather.query` 真值=schema_type 判定=none（none）
- **ST02** 成都明天天气 — 注入 ['stale_soft']；暴露错误数据 stale_soft；结局 ok ∉ ['degraded', 'fallback']
  - FN 漏报 #0 `weather.query` 真值=stale_soft 判定=none（none）
- **ST03** 看看杨国福麻辣烫的菜单 — 注入 ['stale_menu']；暴露错误数据 stale_menu；结局 ok ∉ ['degraded', 'fallback']
  - FN 漏报 #0 `food.search` 真值=stale_menu 判定=none（none）

## CAS 级联 7B→V3.2（7B 判异常才升级）（处置错误 4/58）

- **R06** 在老王黄焖鸡点一份黄焖鸡米饭并付款 — 注入 ['sem_price_unit']；暴露错误数据 sem_price_unit；结局 ok ∉ ['fallback', 'human']
  - FN 漏报 #0 `food.search` 真值=sem_price_unit 判定=none（none）LLM 裁决放行：价格258.0元偏高
- **L04** 看看杨国福麻辣烫的菜单 — 注入 ['sem_wrong_menu']；暴露错误数据 sem_wrong_menu；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `food.search` 真值=sem_wrong_menu 判定=none（none）
- **L05** 看看沙县小吃的菜单，多久能送到 — 注入 ['sem_eta_implausible']；暴露错误数据 sem_eta_implausible；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `food.search` 真值=sem_eta_implausible 判定=none（none）
- **P02** 看看川味小馆的菜单 — 注入 ['partial']；暴露错误数据 partial；结局 ok ∉ ['degraded', 'fallback']
  - FN 漏报 #0 `food.search` 真值=partial 判定=none（none）LLM 裁决放行：配送时长 95 分钟，但未超出合理范围

## CAS 级联 V4F→V3.2（异常或置信<0.9 升级）（处置错误 1/58）

- **P02** 看看川味小馆的菜单 — 注入 ['partial']；暴露错误数据 partial；结局 ok ∉ ['degraded', 'fallback']
  - FN 漏报 #0 `food.search` 真值=partial 判定=none（none）LLM 裁决放行：菜单仅返回1项但has_more=true，属分页正常；95分钟配送有雨天备注，合理

## T 分层：决策/写同步 + 展示异步（V4F）（处置错误 7/58）

- **L01** 北京后天天气 — 注入 ['sem_condition_precip']；先展示后更正
- **L02** 上海明天天气，要带伞吗 — 注入 ['sem_inrange_temp']；先展示后更正
- **L03** 广州后天天气 — 注入 ['sem_condition_season']；先展示后更正
- **L04** 看看杨国福麻辣烫的菜单 — 注入 ['sem_wrong_menu']；先展示后更正
- **L05** 看看沙县小吃的菜单，多久能送到 — 注入 ['sem_eta_implausible']；先展示后更正
- **L07** 看看一点点的菜单 — 注入 ['sem_price_unit']；先展示后更正
- **P02** 看看川味小馆的菜单 — 注入 ['partial']；暴露错误数据 partial；结局 ok ∉ ['degraded', 'fallback']
  - FN 漏报 #0 `food.search` 真值=partial 判定=none（none）LLM 裁决放行：菜单仅返回1项但has_more=true，属分页正常；95分钟配送有雨天备注，合理

## T+C 分层 + 判定缓存（V4F）（处置错误 7/58）

- **L01** 北京后天天气 — 注入 ['sem_condition_precip']；先展示后更正
- **L02** 上海明天天气，要带伞吗 — 注入 ['sem_inrange_temp']；先展示后更正
- **L03** 广州后天天气 — 注入 ['sem_condition_season']；先展示后更正
- **L04** 看看杨国福麻辣烫的菜单 — 注入 ['sem_wrong_menu']；先展示后更正
- **L05** 看看沙县小吃的菜单，多久能送到 — 注入 ['sem_eta_implausible']；先展示后更正
- **L07** 看看一点点的菜单 — 注入 ['sem_price_unit']；先展示后更正
- **P02** 看看川味小馆的菜单 — 注入 ['partial']；暴露错误数据 partial；结局 ok ∉ ['degraded', 'fallback']
  - FN 漏报 #0 `food.search` 真值=partial 判定=none（none）LLM 裁决放行：菜单仅返回1项但has_more=true，属分页正常；95分钟配送有雨天备注，合理

## T 分层：决策/写同步 + 展示异步（V3.2）（处置错误 7/58）

- **L01** 北京后天天气 — 注入 ['sem_condition_precip']；先展示后更正
- **L02** 上海明天天气，要带伞吗 — 注入 ['sem_inrange_temp']；先展示后更正
- **L03** 广州后天天气 — 注入 ['sem_condition_season']；先展示后更正
- **L04** 看看杨国福麻辣烫的菜单 — 注入 ['sem_wrong_menu']；先展示后更正
- **L05** 看看沙县小吃的菜单，多久能送到 — 注入 ['sem_eta_implausible']；先展示后更正
- **L07** 看看一点点的菜单 — 注入 ['sem_price_unit']；先展示后更正
- **P02** 看看川味小馆的菜单 — 注入 ['partial']；先展示后更正

## T+C 分层 + 判定缓存（V3.2）（处置错误 7/58）

- **L01** 北京后天天气 — 注入 ['sem_condition_precip']；先展示后更正
- **L02** 上海明天天气，要带伞吗 — 注入 ['sem_inrange_temp']；先展示后更正
- **L03** 广州后天天气 — 注入 ['sem_condition_season']；先展示后更正
- **L04** 看看杨国福麻辣烫的菜单 — 注入 ['sem_wrong_menu']；先展示后更正
- **L05** 看看沙县小吃的菜单，多久能送到 — 注入 ['sem_eta_implausible']；先展示后更正
- **L07** 看看一点点的菜单 — 注入 ['sem_price_unit']；先展示后更正
- **P02** 看看川味小馆的菜单 — 注入 ['partial']；先展示后更正