# tbcli交接合同

依赖名为tbcli，所需语义为item-summary-v1、soutui-inspect-v1、material-upload-v1、soutui-article-v1及publish默认提交/--prepare只填表。已对照0.11.5-dev.2；兼容升级允许，只要现场发现的合同仍满足这些要求。通过skill source读取当前完整伴随Skill，并按其入口和会话规则执行。找不到依赖返回CLI_UNAVAILABLE；缺少功能返回CONTRACT_UNSUPPORTED，不重建私有API逻辑。

N2使用 `tbcli item summary --item-id ID --out SUMMARY.json --json`。需要summaryVersion=1、product.itemId、product.title、product.mainImages数组（五个URL）及product.shop.shopName。summary的partial不等于没有五图，要逐字段判断。下载这五个明确公开图片地址，只保存图像与来源，不抓浏览器会话。商家操作使用merchant，前台采集使用buyer，两者保持隔离。

`tbcli soutui inspect --item-id ID --shop-name SHOP --out INSPECTION.json --json` 应返回status=inspected，同一itemId与shopName，以及emptySlots>0。用户有商家操作授权时核实归属与剩余位；creative-only仅制作本地创作储备，不访问商家后台。发布前重新检查当前状态和剩余位，保存新回执。

N6先用应用manifest生成明确folderPath和files，再调用 `tbcli material upload-images --input UPLOAD.json --out RECEIPT.json --json`。成功需要status=uploaded、shopName、folderPath、folderId、folderVerified=true、有序imageNames及files里的name/sha256。跨任务复用目录允许；重复图片或状态不清先核对，不盲传。

构建article后默认 `tbcli soutui publish --input ARTICLE.json --out RESULT.json --json`；检查模式加 `--prepare`，不加--yes。article字段为schemaVersion=1、shopName、itemId、imageNames、title、body。prepared状态与published状态分别解释；publish需核对contentId与listVerified，unknown先查持久化记录和列表。使用同一持久化日志位置，不能通过每次创建临时state-dir规避防重。

真实参数由执行Agent逐字段传递；上面的命令为接口格式说明，不是可直接执行的占位参数。所有out必须新建。调用后返回原主线对应节点；让CLI承担鉴权、节奏、目录和表单校验，应用只决定具体商品、图片、文字、归档目录与mode。
