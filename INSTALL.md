# 安装

给当前使用的 Agent 发送：

> 帮我安装 @petercjl/taobao-soutui-studio，并同步和验证当前 Agent 的 Skill。

Agent 通过包自带入口发现完整资源，明确解析当前宿主的 Skill 目标目录，调用管理入口进行物理复制及摘要校验，再检查宿主是否已发现 Skill。管理入口的 capabilities 和子命令帮助声明精确目录及父目录的参数语义。已有未托管或被编辑目录时保留原件，完成对比和可恢复迁移后再安装。禁用 npm 安装脚本时同样执行上述同步。
