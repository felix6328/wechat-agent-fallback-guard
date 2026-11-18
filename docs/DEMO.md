# WXG 网关演示

## 1. 复现本地质量网关

在仓库根目录运行。默认后端使用固定种子模拟。

```bash
python -m unittest discover -s tests
python scripts/demo.py '在沙县小吃点一份鸡腿饭并付款' --fault pay.create=timeout_after_charge --variant naive
python scripts/demo.py '在沙县小吃点一份鸡腿饭并付款' --fault pay.create=timeout_after_charge --variant rules_strict
```

两条轨迹分别展示盲重试和同一幂等键的查单恢复。终端会标注模拟扣款。

## 2. 高德天气

通过 `FB_ENV_FILE` 指定已有配置文件，字段名见 `.env.example`。以下用 `<本机总配置路径>` 占位。

```bash
export FB_ENV_FILE='<本机总配置路径>'
python scripts/demo.py --backend real --case weather_gz
python scripts/demo.py --backend real --case weather_gz --inject sem_city
python eval/run_real_eval.py
```

第一条显示预报来源和发布时间。第二条用同一高德响应模拟串城，结果应说明数据待核对。纯规则评测可加 `--no-llm`。评测先采集真实响应，再将故障回放给各方案。高德网络采样耗时和模型决策回放耗时在评测报告中分别显示。

## 3. 支付宝沙箱

```bash
python -m pip install -r requirements-real.txt
python scripts/pay_sandbox_demo.py start --session portfolio-run-01 --order demo --method page --amount 0.01
```

打开命令打印的沙箱收银台网址。用控制台的沙箱买家账号付款。控制台提供安卓版沙箱工具时，也可用 `--method qr` 进行单独一轮演示。

可以付款后再运行验证，或在付款前加 `--wait-seconds 120`，验证程序会用同一订单号等沙箱状态。

```bash
python scripts/pay_sandbox_demo.py verify --session portfolio-run-01 --order demo --amount 0.01 --drop-paid-response
python scripts/pay_sandbox_demo.py start --session portfolio-run-01 --order demo --amount 0.01
python scripts/pay_sandbox_demo.py refund --session portfolio-run-01 --order demo --amount 0.01
```

网关先取得已支付的验签结果，在本地丢弃该响应，再查同一笔订单并比对交易号和金额。付款确认期间的轨迹应只包含查单。再次进入支付流程应显示同一交易号。退款用另一个明确的命令触发，仍会先确认订单和金额。关单使用另一笔测试单。请打开那笔单的收银台或在沙箱客户端扫码，停留在待付款页面。查单显示待支付后，对那笔单执行 `close`。沙箱有时在打开收银台前返回「交易不存在」，这时还无法确认已关单。 [支付宝关单说明](https://aipay.alipay.com/docs/vibe-pay/ai-web-app-payment-qianyi/api-list/alipay-trade-close.html)

如果网关仍显示待确认，到沙箱控制台核对状态，再用同一会话重查。测试事件日志在 `cache/alipay/events.jsonl`，记录沙箱交易号、状态和动作，买家账号留在控制台。

完成付款恢复、关闭或退款验证后，运行 `python eval/run_real_eval.py --payment-only`。它从本地日志写入 [支付宝沙箱联调记录](../eval/sandbox_log.md)，同时更新现有接口评测中的支付结果。
