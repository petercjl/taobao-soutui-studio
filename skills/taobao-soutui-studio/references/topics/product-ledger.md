# 商品持续台账合同

## 定位与数据归属

默认项目路径为用户工作目录下soutui-products/商品ID。显式项目路径优先；在同一根目录跨对话复用。不同根目录不自动全盘索引，多份同ID台账由用户明确选择。Skill中只含方法与脚本，不含真实商品数据、账户或私有路径。

product_ledger.py仅本地执行，不生成媒体、不联网、不上传发布。Python3.10+；图像交接构建器还需Pillow。commands：init --root ROOT --input SEED；show --project PROJECT；commit --project PROJECT --expect-revision N --input EVENT；render --project PROJECT --out NEW.html；export-manifest --project PROJECT --direction ID --batch ID --inspection FILE --date YYYY-MM-DD --mode publish|prepare --out NEW.json。脚本路径相对当前Skill根解析。JSON输入使用真实参数文件，禁止把示例当任务事实。

ledger/00000001.json等递增修订为权威，读取最高完整版本；更新独占.ledger.lock并检查expected revision，追加新文件。保留旧版本和lastEvent；HTML按需生成到新路径，不反向编辑HTML。进程异常留下锁或损坏修订时先核实操作、恢复完整修订并保留证据，不静默删除/覆盖。目录搬迁优先使用相对资产路径；外部引用保持明确并核实可读性。

## 数据

seed：schemaVersion=1，itemId为字符串，product对象，directions为九个唯一id对象。product含title、shopName、productName、productUrl、timezone、references、facts、unknownFacts。每主图含path或url（可同时）、sha256、order、acquiredAt、role；生成前必须有可读本地文件。记录款式、包装/陪体边界及事实来源；新来源保留旧版本。

direction包含id/title/need/scene/style/narrative/copyAngle/difference/selected/batches。batch含id、targetCount=8、candidates、model、planPath、authorization及tasks。历史批次可imported=true并以真实数量作为targetCount，不能伪造八张。candidate含id/path/sha256/decisionQuestion/prompt/orderedReferences/taskId/requestedModel/actualDimensions/cost/qa；选择另存selection.ids（有序）、version、confirmedBy=user及evidence。每批次copy含title/body/review及selectionVersion，receipts独立记录上传、填表和发布。生成费用记录真实值，actual_model为空不声称已核实服务模型身份。

## 事件

- product：values更新允许的商品信息。
- plan-direction：directionId、values；仅无批次方向可重规划。
- add-batch：directionId、batch；不夹带选图或回执。
- task：directionId、batchId、task含candidateId/taskId/status及当前参数、恢复点，提交后即登记，未知先恢复原task。
- add-candidate：directionId、batchId、candidate；完成后校验摘要再登记。
- select：directionId、batchId、ids、confirmedBy=user、evidence；3—8张，无重复、必须存在，改变选择使copy失效。已记回执批次冻结。
- copy：directionId、batchId、copy含title/body/review；绑定当前选择版本。
- intent：directionId、batchId、kind=upload|prepare|publish、requestId、authorization；在外部操作前登记，未配对回执的意图须先核实。
- receipt：directionId、batchId、kind、path、selectionVersion；读取实际回执，核对商品/店铺、已选摘要及发布contentId；unknown保留待核，不能勾选已发布。

权威依据为实际CLI回执与文件内容；脚本校验不能代替平台核验。上传与发布分别完成，published仅凭可核对contentId，listVerified独立存。失败、认证中断、部分成功不消耗方向或假记完成。每批次在调用外部操作前后保留参数文件与回执，相同requestId和原CLI持久化日志用于恢复；本脚本不是跨平台幂等服务。

## 方案版本

replan事件包含planId、reason、directions九项；新方向均无批次且具有完整visual，id在历史和当前计划中全局唯一。旧directions整版保留在directionPlanHistory，当前directionPlanId指向新方案。find_batch可按原方向ID找到历史批次，继续选图、配文案及恢复，原图片与回执不改。视觉对照与用户方案选择保存在项目方案文件，运行不覆盖旧计划。

## 单张调试记录

新批次kind=pilot且targetCount=1表示用户明确要求的单张调试，候选最多一张；正式批次targetCount=8。pilot状态为单张调试中/待确认单张样图，不导出为文章上传，不通过imported伪装历史批次。调试后是否成组由用户后续指令决定。
