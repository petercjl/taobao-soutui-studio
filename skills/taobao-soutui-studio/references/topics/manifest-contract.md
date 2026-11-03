# 选图manifest与交接构建器

新流程用product_ledger.py export-manifest导出schemaVersion=2。包含itemId、shopName、productName、localDate、mode、merchantInspection、title、body、review、images和selectionProof。images为用户选中的3—8项，字段path/candidateId/decisionQuestion/reviewed；selectionProof含project/revision/directionId/batchId/version。脚本从当前台账验证选择证据、顺序、真实路径与摘要、文案和检查版本，不能夹带未选候选。

review含productIdentity、sceneAndUse、claims、imageText四个布尔项。AI查看与事实核对后填写；用户对整体画面的接受单独记录，不能替代未知性能证明或发布参数校验。schemaVersion=1历史manifest继续兼容3—8张，已有五图文件不改；新流程必须走版本2台账选择合同。

上传前运行build_inputs.py upload-input --manifest FILE --out NEW.json；生成article前运行article-input --manifest FILE --upload-result RECEIPT --out NEW.json。Python3.10+及Pillow，按当前Skill相对路径解析脚本。验证商品店铺、可用位、标题5—20与正文10—1000个UTF-16单位、每张200KB—20MB、普通非动画JPEG/PNG/WebP、精确统一3:4或1:1及不同摘要。近似比例需要先用已授权工具处理，再登记派生资产和重新确认选择；不拉伸或补字节绕过。

上传回执须status=uploaded、folderVerified=true、店铺和目录一致，imageNames数量/顺序和files摘要逐项对应。article输出保持tbcli schemaVersion=1，不携带应用台账私有字段；mode由应用选择publish或--prepare。输出只创建新文件，现有路径返回OUTPUT_EXISTS；新选择/新台账版本须重新导出，已有上传批次复用原版本文件及回执恢复，不盲传。
