# TigerQuant V7 Apex Pro | 六维 AI 异步量化交易引擎

![Version](https://img.shields.io/badge/version-v7.0%20Apex%20Pro-blue.svg)
![Python](https://img.shields.io/badge/python-3.9%2B-brightgreen.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

TigerQuant V7 是一个专为美股市场设计的高频/波段量化交易系统。基于 Tiger Trade OpenAPI 构建，采用纯异步架构 (Asyncio Queue)，内置六维多因子打分模型与动态凯利仓位管理，旨在提供机构级的执行效率与风控能力。

## 核心架构与特性

* **⚡ 异步高并发底座 (Async Engine)**: 摒弃传统同步阻塞，采用 `asyncio` 生产者-消费者队列，支持对 100+ 只精选标的同时进行高吞吐量的数据抓取与并发订单路由。
* **🧠 六维多因子打分 (Alpha Scoring)**: 独创六维评估体系（技术面、资金面、基本面、情绪面、宏观面、AI 机器学习），通过动态权重计算输出 `0-100` 综合得分。
* **🛡️ 动态风控与资金管理 (Risk Management)**:
  * **凯利公式动态调仓 (Kelly Sizing)**: 根据胜率与盈亏比动态计算单笔最佳下注资金。
  * **ATR 追踪止损 (Trailing Stop Loss)**: 基于真实波动幅度 (ATR)，从建仓后的最高价动态计算防守线。
  * **MTF 多周期共振**: 日线触发信号后，强制进行 15 分钟 (15m) 级别止跌确认，过滤虚假突破。
  * **宏观避险 (Macro Regime)**: 实时监控 SPY 均线状态，大盘进入 `RISK_OFF` 状态时自动锁定建仓权限。

## 快速启动 (Quick Start)

### 1. 环境配置
推荐使用 Conda 隔离环境以避免依赖冲突：
```bash
conda create -n tiger_env python=3.9
conda activate tiger_env

# 安装依赖
pip install -r requirements.txt



2.本项目严格分离代码与隐私。请将您的 Tiger Trade OpenAPI 私钥保存为根目录下的 tiger_private_key.pem。

复制配置模板并填入您的信息：cp config.example.ini config.ini

在 config.ini 中填入您的 tiger_id 和 account_id，并设置 sandbox = True 进行模拟盘测试。

⚠️ 警告：切勿将真实的私钥 (.pem) 与配置文件 (config.ini) 提交至远程开源仓库！请确保在提交前已将它们加入 .gitignore 文件。


3. 点火运行
配置完成后，直接启动核心终端引擎：python pro_terminal.py

免责声明 (Disclaimer)
本项目仅供量化技术研究与学习交流，不构成任何投资建议。
系统生成的任何交易信号均基于历史数据与统计算法，无法预测未来市场绝对走势。使用者因运行本代码产生的任何直接或间接财务损失，作者概不负责。实盘操作风险极高，请务必在 Sandbox 模拟环境中进行充分测试后再做决定。