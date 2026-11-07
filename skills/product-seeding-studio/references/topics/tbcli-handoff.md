# tbcli 商品采集

精确解析依赖 tbcli，加载当前 canonical Skill 与买家入口合同。N2 仅需 item-summary-v1。缺失时返回 CLI_UNAVAILABLE 或 CONTRACT_UNSUPPORTED。

通过买家入口执行 `tbcli item summary --item-id ID --out SUMMARY.json --json`，核对 summaryVersion、product.itemId、product.title、product.mainImages 与 product.shop.shopName。逐字段核验 partial 响应，按原顺序保存可用主图及其公开 URL。将原图、来源和事实放入商品资料对应版本，再回到 N2。输出写入新文件。
