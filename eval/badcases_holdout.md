# Badcase：`data/holdout.json`（自动生成）

每个配置只列种子 42 的处置错误，避免重复。


## A 无检测（SDK 式盲重试）（处置错误 18/30）

- **HL01** 如果后天上海下雨就从公司叫车回家 — 注入 ['sem_condition_precip']；暴露错误数据 sem_condition_precip；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `weather.query` 真值=sem_condition_precip 判定=none（none）
- **HL02** 看看沙县小吃的菜单 — 注入 ['sem_wrong_menu']；暴露错误数据 sem_wrong_menu；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `food.search` 真值=sem_wrong_menu 判定=none（none）
- **HL03** 一点点有什么喝的 — 注入 ['partial']；暴露错误数据 partial；结局 ok ∉ ['degraded', 'fallback']
  - FN 漏报 #0 `food.search` 真值=partial 判定=none（none）
- **HL04** 深圳明天天气 — 注入 ['sem_condition_season']；暴露错误数据 sem_condition_season；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `weather.query` 真值=sem_condition_season 判定=none（none）
- **HL05** 成都后天天气 — 注入 ['sem_condition_precip']；暴露错误数据 sem_condition_precip；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `weather.query` 真值=sem_condition_precip 判定=none（none）
- **HL06** 看看老王黄焖鸡的菜单，多久送到 — 注入 ['sem_eta_implausible']；暴露错误数据 sem_eta_implausible；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `food.search` 真值=sem_eta_implausible 判定=none（none）
- **HR01** 在杨国福麻辣烫点一份酸梅汤并付款 — 注入 ['sem_price_unit']；暴露错误数据 sem_price_unit；结局 ok ∉ ['fallback', 'human']
  - FN 漏报 #0 `food.search` 真值=sem_price_unit 判定=none（none）
- **HR02** 在老王黄焖鸡点一份可乐 — 注入 ['sem_qty']；暴露错误数据 sem_qty；结局 ok ∉ ['human']
  - FN 漏报 #1 `food.order` 真值=sem_qty 判定=none（none）
- **HP01** 在一点点点一杯芝芝莓莓并付款 — 注入 ['timeout_after_charge']；重复扣款=True 重复下单=False
- **H-U01** 哈尔滨后天天气 — 注入 ['sem_inrange_temp']；暴露错误数据 sem_inrange_temp；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `weather.query` 真值=sem_inrange_temp 判定=none（none）
- **HT02** 看看川味小馆有什么菜 — 注入 ['timeout']；结局 failed ∉ ['fallback']
- **HS01** 成都明天天气 — 注入 ['schema_missing']；结局 failed ∉ ['fallback']
  - FN 漏报 #0 `weather.query` 真值=schema_missing 判定=none（none）
- **HST01** 杭州明天天气 — 注入 ['stale_hard']；暴露错误数据 stale_hard；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `weather.query` 真值=stale_hard 判定=none（none）
- **HST02** 看看沙县小吃的菜单 — 注入 ['stale_menu']；暴露错误数据 stale_menu；结局 ok ∉ ['degraded', 'fallback']
  - FN 漏报 #0 `food.search` 真值=stale_menu 判定=none（none）
- **HR03** 北京明天天气 — 注入 ['sem_city']；暴露错误数据 sem_city；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `weather.query` 真值=sem_city 判定=none（none）
- **HL07** 看看一点点的菜单，几分钟能到 — 注入 ['sem_eta_implausible']；暴露错误数据 sem_eta_implausible；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `food.search` 真值=sem_eta_implausible 判定=none（none）
- **HP02** 在老王黄焖鸡点一份黄焖鸡米饭并付款 — 注入 ['amount_mismatch']；暴露错误数据 amount_mismatch；结局 ok ∉ ['human']
  - FN 漏报 #2 `pay.create` 真值=amount_mismatch 判定=none（none）
- **HP03** 在杨国福麻辣烫点一份酸梅汤并付款 — 注入 ['timeout_after_create', 'timeout_before_charge']；重复扣款=False 重复下单=True

## B1 仅规则·宽松（处置错误 9/30）

- **HL01** 如果后天上海下雨就从公司叫车回家 — 注入 ['sem_condition_precip']；暴露错误数据 sem_condition_precip；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `weather.query` 真值=sem_condition_precip 判定=none（none）
- **HL02** 看看沙县小吃的菜单 — 注入 ['sem_wrong_menu']；暴露错误数据 sem_wrong_menu；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `food.search` 真值=sem_wrong_menu 判定=none（none）
- **HL03** 一点点有什么喝的 — 注入 ['partial']；暴露错误数据 partial；结局 ok ∉ ['degraded', 'fallback']
  - FN 漏报 #0 `food.search` 真值=partial 判定=none（none）
- **HL04** 深圳明天天气 — 注入 ['sem_condition_season']；暴露错误数据 sem_condition_season；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `weather.query` 真值=sem_condition_season 判定=none（none）
- **HL05** 成都后天天气 — 注入 ['sem_condition_precip']；暴露错误数据 sem_condition_precip；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `weather.query` 真值=sem_condition_precip 判定=none（none）
- **HL06** 看看老王黄焖鸡的菜单，多久送到 — 注入 ['sem_eta_implausible']；暴露错误数据 sem_eta_implausible；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `food.search` 真值=sem_eta_implausible 判定=none（none）
- **HR01** 在杨国福麻辣烫点一份酸梅汤并付款 — 注入 ['sem_price_unit']；暴露错误数据 sem_price_unit；结局 ok ∉ ['fallback', 'human']
  - FN 漏报 #0 `food.search` 真值=sem_price_unit 判定=none（none）
- **H-U01** 哈尔滨后天天气 — 注入 ['sem_inrange_temp']；暴露错误数据 sem_inrange_temp；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `weather.query` 真值=sem_inrange_temp 判定=none（none）
- **HL07** 看看一点点的菜单，几分钟能到 — 注入 ['sem_eta_implausible']；暴露错误数据 sem_eta_implausible；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `food.search` 真值=sem_eta_implausible 判定=none（none）

## B2 仅规则·严格（处置错误 12/30）

- **HN01** 漠河今天冷吗 — 注入 无；结局 fallback ∉ ['ok']
  - FP 误报 #0 `weather.query` 真值=None 判定=semantic_wrong（rule）[soft] temp_low_c=-32 少见
  - FP 误报 #1 `weather_backup.query` 真值=None 判定=semantic_wrong（rule）[soft] temp_low_c=-32 少见
- **HN02** 从浦东机场打车去公司多少钱 — 注入 无；结局 fallback ∉ ['ok']
  - FP 误报 #0 `ride.estimate` 真值=None 判定=semantic_wrong（rule）[soft] 车费 221.6 偏高
- **HN03** 在川味小馆点一份水煮鱼和一份米饭 — 注入 无；结局 fallback ∉ ['ok']
  - FP 误报 #0 `food.search` 真值=None 判定=semantic_wrong（rule）[soft] 配送时长 95 分钟偏长
- **HL01** 如果后天上海下雨就从公司叫车回家 — 注入 ['sem_condition_precip']；暴露错误数据 sem_condition_precip；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `weather.query` 真值=sem_condition_precip 判定=none（none）
- **HL02** 看看沙县小吃的菜单 — 注入 ['sem_wrong_menu']；暴露错误数据 sem_wrong_menu；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `food.search` 真值=sem_wrong_menu 判定=none（none）
- **HL03** 一点点有什么喝的 — 注入 ['partial']；暴露错误数据 partial；结局 ok ∉ ['degraded', 'fallback']
  - FN 漏报 #0 `food.search` 真值=partial 判定=none（none）
- **HL04** 深圳明天天气 — 注入 ['sem_condition_season']；暴露错误数据 sem_condition_season；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `weather.query` 真值=sem_condition_season 判定=none（none）
- **HL05** 成都后天天气 — 注入 ['sem_condition_precip']；暴露错误数据 sem_condition_precip；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `weather.query` 真值=sem_condition_precip 判定=none（none）
- **HL06** 看看老王黄焖鸡的菜单，多久送到 — 注入 ['sem_eta_implausible']；暴露错误数据 sem_eta_implausible；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `food.search` 真值=sem_eta_implausible 判定=none（none）
- **H-U01** 哈尔滨后天天气 — 注入 ['sem_inrange_temp']；暴露错误数据 sem_inrange_temp；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `weather.query` 真值=sem_inrange_temp 判定=none（none）
- **HN04** 从公司打车去浦东机场 — 注入 无；结局 fallback ∉ ['ok']
  - FP 误报 #0 `ride.estimate` 真值=None 判定=semantic_wrong（rule）[soft] 车费 221.6 偏高
- **HL07** 看看一点点的菜单，几分钟能到 — 注入 ['sem_eta_implausible']；暴露错误数据 sem_eta_implausible；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `food.search` 真值=sem_eta_implausible 判定=none（none）

## E 严格规则 + v2 蒸馏规则（处置错误 8/30）

- **HN01** 漠河今天冷吗 — 注入 无；结局 fallback ∉ ['ok']
  - FP 误报 #0 `weather.query` 真值=None 判定=semantic_wrong（rule）[soft] temp_low_c=-32 少见
  - FP 误报 #1 `weather_backup.query` 真值=None 判定=semantic_wrong（rule）[soft] temp_low_c=-32 少见
- **HN02** 从浦东机场打车去公司多少钱 — 注入 无；结局 fallback ∉ ['ok']
  - FP 误报 #0 `ride.estimate` 真值=None 判定=semantic_wrong（rule）[soft] 车费 221.6 偏高
- **HN03** 在川味小馆点一份水煮鱼和一份米饭 — 注入 无；结局 fallback ∉ ['ok']
  - FP 误报 #0 `food.search` 真值=None 判定=semantic_wrong（rule）[soft] 配送时长 95 分钟偏长
- **HL02** 看看沙县小吃的菜单 — 注入 ['sem_wrong_menu']；暴露错误数据 sem_wrong_menu；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `food.search` 真值=sem_wrong_menu 判定=none（none）
- **HL03** 一点点有什么喝的 — 注入 ['partial']；暴露错误数据 partial；结局 ok ∉ ['degraded', 'fallback']
  - FN 漏报 #0 `food.search` 真值=partial 判定=none（none）
- **HL04** 深圳明天天气 — 注入 ['sem_condition_season']；暴露错误数据 sem_condition_season；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `weather.query` 真值=sem_condition_season 判定=none（none）
- **H-U01** 哈尔滨后天天气 — 注入 ['sem_inrange_temp']；暴露错误数据 sem_inrange_temp；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `weather.query` 真值=sem_inrange_temp 判定=none（none）
- **HN04** 从公司打车去浦东机场 — 注入 无；结局 fallback ∉ ['ok']
  - FP 误报 #0 `ride.estimate` 真值=None 判定=semantic_wrong（rule）[soft] 车费 221.6 偏高

## H-7B 规则 + Qwen2.5-7B（免费）（处置错误 10/30）

- **HC03** 沙县小吃点两份蒸饺，付款 — 注入 无；结局 fallback ∉ ['ok']
  - FP 误报 #0 `food.search` 真值=None 判定=context_mismatch（llm）用户点蒸饺，但返回菜单里没有蒸饺
- **HN01** 漠河今天冷吗 — 注入 无；结局 fallback ∉ ['ok']
  - FP 误报 #0 `weather.query` 真值=None 判定=semantic_wrong（llm）漠河11月最低温-32°C极低，不符合常理
  - FP 误报 #1 `weather_backup.query` 真值=None 判定=semantic_wrong（llm）漠河11月低温应高于-32°C
- **HL01** 如果后天上海下雨就从公司叫车回家 — 注入 ['sem_condition_precip']；暴露错误数据 sem_condition_precip；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `weather.query` 真值=sem_condition_precip 判定=none（none）
- **HL02** 看看沙县小吃的菜单 — 注入 ['sem_wrong_menu']；暴露错误数据 sem_wrong_menu；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `food.search` 真值=sem_wrong_menu 判定=none（none）
- **HL03** 一点点有什么喝的 — 注入 ['partial']；暴露错误数据 partial；结局 ok ∉ ['degraded', 'fallback']
  - FN 漏报 #0 `food.search` 真值=partial 判定=none（none）
- **HL05** 成都后天天气 — 注入 ['sem_condition_precip']；暴露错误数据 sem_condition_precip；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `weather.query` 真值=sem_condition_precip 判定=none（none）
- **HL06** 看看老王黄焖鸡的菜单，多久送到 — 注入 ['sem_eta_implausible']；暴露错误数据 sem_eta_implausible；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `food.search` 真值=sem_eta_implausible 判定=none（none）
- **HR01** 在杨国福麻辣烫点一份酸梅汤并付款 — 注入 ['sem_price_unit']；暴露错误数据 sem_price_unit；结局 ok ∉ ['fallback', 'human']
  - FN 漏报 #0 `food.search` 真值=sem_price_unit 判定=none（none）LLM 裁决放行：
- **H-U01** 哈尔滨后天天气 — 注入 ['sem_inrange_temp']；暴露错误数据 sem_inrange_temp；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `weather.query` 真值=sem_inrange_temp 判定=none（none）
- **HL07** 看看一点点的菜单，几分钟能到 — 注入 ['sem_eta_implausible']；暴露错误数据 sem_eta_implausible；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `food.search` 真值=sem_eta_implausible 判定=none（none）

## H-V4F 规则 + DeepSeek-V4-Flash（处置错误 3/30）

- **HR01** 在杨国福麻辣烫点一份酸梅汤并付款 — 注入 ['sem_price_unit']；暴露错误数据 sem_price_unit；结局 ok ∉ ['fallback', 'human']
  - FN 漏报 #0 `food.search` 真值=sem_price_unit 判定=none（none）LLM 裁决放行：酸梅汤6元合理，菜单含目标菜品，价格与距离正常
- **H-U01** 哈尔滨后天天气 — 注入 ['sem_inrange_temp']；暴露错误数据 sem_inrange_temp；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `weather.query` 真值=sem_inrange_temp 判定=none（none）
- **HL07** 看看一点点的菜单，几分钟能到 — 注入 ['sem_eta_implausible']；暴露错误数据 sem_eta_implausible；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `food.search` 真值=sem_eta_implausible 判定=none（none）

## H-V3.2 规则 + DeepSeek-V3.2（处置错误 1/30）

- **H-U01** 哈尔滨后天天气 — 注入 ['sem_inrange_temp']；暴露错误数据 sem_inrange_temp；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `weather.query` 真值=sem_inrange_temp 判定=none（none）

## D-V4F 纯 LLM 质检（V4-Flash）（处置错误 6/30）

- **HR01** 在杨国福麻辣烫点一份酸梅汤并付款 — 注入 ['sem_price_unit']；暴露错误数据 sem_price_unit；结局 ok ∉ ['fallback', 'human']
  - FN 漏报 #0 `food.search` 真值=sem_price_unit 判定=none（none）
- **H-U01** 哈尔滨后天天气 — 注入 ['sem_inrange_temp']；暴露错误数据 sem_inrange_temp；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `weather.query` 真值=sem_inrange_temp 判定=none（none）
- **HS01** 成都明天天气 — 注入 ['schema_missing']；结局 failed ∉ ['fallback']
  - FN 漏报 #0 `weather.query` 真值=schema_missing 判定=none（none）
- **HST01** 杭州明天天气 — 注入 ['stale_hard']；暴露错误数据 stale_hard；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `weather.query` 真值=stale_hard 判定=none（none）
- **HST02** 看看沙县小吃的菜单 — 注入 ['stale_menu']；暴露错误数据 stale_menu；结局 ok ∉ ['degraded', 'fallback']
  - FN 漏报 #0 `food.search` 真值=stale_menu 判定=none（none）
- **HL07** 看看一点点的菜单，几分钟能到 — 注入 ['sem_eta_implausible']；暴露错误数据 sem_eta_implausible；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `food.search` 真值=sem_eta_implausible 判定=none（none）

## CAS 级联 7B→V3.2（7B 判异常才升级）（处置错误 8/30）

- **HL01** 如果后天上海下雨就从公司叫车回家 — 注入 ['sem_condition_precip']；暴露错误数据 sem_condition_precip；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `weather.query` 真值=sem_condition_precip 判定=none（none）
- **HL02** 看看沙县小吃的菜单 — 注入 ['sem_wrong_menu']；暴露错误数据 sem_wrong_menu；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `food.search` 真值=sem_wrong_menu 判定=none（none）
- **HL03** 一点点有什么喝的 — 注入 ['partial']；暴露错误数据 partial；结局 ok ∉ ['degraded', 'fallback']
  - FN 漏报 #0 `food.search` 真值=partial 判定=none（none）
- **HL05** 成都后天天气 — 注入 ['sem_condition_precip']；暴露错误数据 sem_condition_precip；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `weather.query` 真值=sem_condition_precip 判定=none（none）
- **HL06** 看看老王黄焖鸡的菜单，多久送到 — 注入 ['sem_eta_implausible']；暴露错误数据 sem_eta_implausible；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `food.search` 真值=sem_eta_implausible 判定=none（none）
- **HR01** 在杨国福麻辣烫点一份酸梅汤并付款 — 注入 ['sem_price_unit']；暴露错误数据 sem_price_unit；结局 ok ∉ ['fallback', 'human']
  - FN 漏报 #0 `food.search` 真值=sem_price_unit 判定=none（none）LLM 裁决放行：
- **H-U01** 哈尔滨后天天气 — 注入 ['sem_inrange_temp']；暴露错误数据 sem_inrange_temp；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `weather.query` 真值=sem_inrange_temp 判定=none（none）
- **HL07** 看看一点点的菜单，几分钟能到 — 注入 ['sem_eta_implausible']；暴露错误数据 sem_eta_implausible；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `food.search` 真值=sem_eta_implausible 判定=none（none）

## CAS 级联 V4F→V3.2（异常或置信<0.9 升级）（处置错误 2/30）

- **HR01** 在杨国福麻辣烫点一份酸梅汤并付款 — 注入 ['sem_price_unit']；暴露错误数据 sem_price_unit；结局 ok ∉ ['fallback', 'human']
  - FN 漏报 #0 `food.search` 真值=sem_price_unit 判定=none（none）LLM 裁决放行：酸梅汤6元合理，菜单含目标菜品，价格与距离正常
- **H-U01** 哈尔滨后天天气 — 注入 ['sem_inrange_temp']；暴露错误数据 sem_inrange_temp；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `weather.query` 真值=sem_inrange_temp 判定=none（none）

## T 分层：决策/写同步 + 展示异步（V4F）（处置错误 8/30）

- **HL02** 看看沙县小吃的菜单 — 注入 ['sem_wrong_menu']；先展示后更正
- **HL03** 一点点有什么喝的 — 注入 ['partial']；先展示后更正
- **HL04** 深圳明天天气 — 注入 ['sem_condition_season']；先展示后更正
- **HL05** 成都后天天气 — 注入 ['sem_condition_precip']；先展示后更正
- **HL06** 看看老王黄焖鸡的菜单，多久送到 — 注入 ['sem_eta_implausible']；先展示后更正
- **HR01** 在杨国福麻辣烫点一份酸梅汤并付款 — 注入 ['sem_price_unit']；暴露错误数据 sem_price_unit；结局 ok ∉ ['fallback', 'human']
  - FN 漏报 #0 `food.search` 真值=sem_price_unit 判定=none（none）LLM 裁决放行：酸梅汤6元合理，菜单含目标菜品，价格与距离正常
- **H-U01** 哈尔滨后天天气 — 注入 ['sem_inrange_temp']；暴露错误数据 sem_inrange_temp；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `weather.query` 真值=sem_inrange_temp 判定=none（none）
- **HL07** 看看一点点的菜单，几分钟能到 — 注入 ['sem_eta_implausible']；暴露错误数据 sem_eta_implausible；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `food.search` 真值=sem_eta_implausible 判定=none（none）

## T+C 分层 + 判定缓存（V4F）（处置错误 8/30）

- **HL02** 看看沙县小吃的菜单 — 注入 ['sem_wrong_menu']；先展示后更正
- **HL03** 一点点有什么喝的 — 注入 ['partial']；先展示后更正
- **HL04** 深圳明天天气 — 注入 ['sem_condition_season']；先展示后更正
- **HL05** 成都后天天气 — 注入 ['sem_condition_precip']；先展示后更正
- **HL06** 看看老王黄焖鸡的菜单，多久送到 — 注入 ['sem_eta_implausible']；先展示后更正
- **HR01** 在杨国福麻辣烫点一份酸梅汤并付款 — 注入 ['sem_price_unit']；暴露错误数据 sem_price_unit；结局 ok ∉ ['fallback', 'human']
  - FN 漏报 #0 `food.search` 真值=sem_price_unit 判定=none（none）LLM 裁决放行：酸梅汤6元合理，菜单含目标菜品，价格与距离正常
- **H-U01** 哈尔滨后天天气 — 注入 ['sem_inrange_temp']；暴露错误数据 sem_inrange_temp；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `weather.query` 真值=sem_inrange_temp 判定=none（none）
- **HL07** 看看一点点的菜单，几分钟能到 — 注入 ['sem_eta_implausible']；暴露错误数据 sem_eta_implausible；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `food.search` 真值=sem_eta_implausible 判定=none（none）

## T 分层：决策/写同步 + 展示异步（V3.2）（处置错误 7/30）

- **HL02** 看看沙县小吃的菜单 — 注入 ['sem_wrong_menu']；先展示后更正
- **HL03** 一点点有什么喝的 — 注入 ['partial']；先展示后更正
- **HL04** 深圳明天天气 — 注入 ['sem_condition_season']；先展示后更正
- **HL05** 成都后天天气 — 注入 ['sem_condition_precip']；先展示后更正
- **HL06** 看看老王黄焖鸡的菜单，多久送到 — 注入 ['sem_eta_implausible']；先展示后更正
- **H-U01** 哈尔滨后天天气 — 注入 ['sem_inrange_temp']；暴露错误数据 sem_inrange_temp；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `weather.query` 真值=sem_inrange_temp 判定=none（none）
- **HL07** 看看一点点的菜单，几分钟能到 — 注入 ['sem_eta_implausible']；先展示后更正

## T+C 分层 + 判定缓存（V3.2）（处置错误 7/30）

- **HL02** 看看沙县小吃的菜单 — 注入 ['sem_wrong_menu']；先展示后更正
- **HL03** 一点点有什么喝的 — 注入 ['partial']；先展示后更正
- **HL04** 深圳明天天气 — 注入 ['sem_condition_season']；先展示后更正
- **HL05** 成都后天天气 — 注入 ['sem_condition_precip']；先展示后更正
- **HL06** 看看老王黄焖鸡的菜单，多久送到 — 注入 ['sem_eta_implausible']；先展示后更正
- **H-U01** 哈尔滨后天天气 — 注入 ['sem_inrange_temp']；暴露错误数据 sem_inrange_temp；结局 ok ∉ ['fallback']
  - FN 漏报 #0 `weather.query` 真值=sem_inrange_temp 判定=none（none）
- **HL07** 看看一点点的菜单，几分钟能到 — 注入 ['sem_eta_implausible']；先展示后更正