# 怎样生成八张候选并交用户选择

N4触发，读 [参考生成与检查](../topics/generation-and-qa.md)及 [SealSeek交接](../topics/sealseek-generation.md)。输入选定方向、八图分工和真实参考，输出八张独立候选、真实参数与task_id、逐图建议及台账记录。回N4完成验收，再进入N5写整组文案；失败先按同一任务恢复，付费重试需符合能力合同授权。

完整自动八图运行：读取 [自动生成与验收循环](../topics/automatic-image-loop.md)，先确定预算并初始化脚本，再逐镜头生成、评分、修正和整组复核；返回N4最终候选登记。
