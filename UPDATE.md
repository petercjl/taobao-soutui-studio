# 更新

给当前使用的 Agent 发送：

> 帮我更新 @petercjl/product-seeding-studio，并同步和验证当前 Agent 的 Skill。

Agent 在更新前解析并校验选定的 Skill 目录，保留本地改动与备份，使用包自带管理入口同步并核对包、独立运行时与 Skill 的版本和摘要。同版本也检查和修复托管目标状态。安装后重新检查宿主发现结果；如果只安装了 npm 包，继续完成 Skill 同步。
