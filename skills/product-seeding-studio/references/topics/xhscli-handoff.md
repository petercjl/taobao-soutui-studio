# xhscli 采集与素材归档交接

## 合同与职责

依赖精确 Skill 名 `xhscli`，npm 包 `@petercjl/xhscli`。从宿主的已安装 Skill 目录解析当前入口；若该 Skill 带有 `.runtime/package.json`，按其中 `bin.xhscli` 声明用 Node.js 调用自有运行时，否则发现 PATH 中的 CLI。后续命令统一绑定同一入口。通过该入口 `skill source --json` 返回 canonical source，完整读取其 `SKILL.md`，相对资源从依赖目录加载；再读 version、capabilities 和所需命令 help。

所需合同为 search Excel、schemaVersion=1 的 note JSON，以及 note get 的 `--download-media` 和 media 文件清单。素材能力已在同版 0.1.0 增补，必须检查实时参数与字段，版本号本身不证明能力存在。缺依赖返回 DEPENDENCY_MISSING；缺下载参数或不兼容字段返回 CONTRACT_UNSUPPORTED，并按依赖文档更新当前宿主的安装后返回。

应用负责问题、关键词、选样、研究判断、抽帧、方向包和验收。xhscli 负责会话、搜索、详情及评论分页、资源地址选择、图片/视频/封面/可用 Live 素材下载和文件摘要。应用从 CLI 清单读取实际媒体文件，完成视觉分析。

## 顺序

1. 用当前入口 `capabilities --json` 与 `browser status --json` 检查能力和会话。需要打开小红书时用 `browser open --json`，再 `auth status --json`。页面加载时短暂等待后重查，登录或验证由用户在当前窗口完成。
2. 应用确定关键词和筛选，执行 `search --keyword "搜索词" --pages 1 --output "研究目录/搜索记录/新的文件.xlsx" --json`。保留回执、工作簿和实际页数、条数、hasMore。按笔记 ID 去重，用表内完整“笔记链接”访问候选，保留访问参数。通过组合查询和翻页满足至少 11 篇有效相关笔记的要求，数量不足时报告缺口。
3. 在每个笔记 ID 子目录执行 `note get --url "搜索结果中的笔记链接" --download-media --output "研究目录/笔记ID/笔记导出-001.json" --json`。ID 输入仅在 CLI 可恢复有效链接时使用。按依赖文档顺序运行，评论和笔记请求使用 CLI 内置节奏。
4. 输出 JSON 旁的同名 `.media` 目录为素材归档，如 `笔记导出-001.media/`。保留目录结构，按 JSON 的 `media.files[].path` 相对 JSON 所在目录解析文件。保留 kind、role、index、sourceUrl、status、bytes、sha256 和失败信息，方向包引用清单中的实际文件。
5. 核对 noteId、schemaVersion、回执和本地文件。笔记完整条件为回执 complete=true、mediaComplete=true，文件 completeness.complete=true、completeness.commentsComplete=true、media.complete=true。每个请求的媒体项须为 downloaded 且本地文件可读，字节数与 SHA-256 相符。图片核对实际尺寸；视频读取视频流、时长及尺寸。CLI complete 表示采集与下载完成，视觉可用性另外判断。
6. 从 note.title、note.desc、note.user、note.type、noteUrl 和 comments 派生正文、链接和评论文件，注明原始 JSON 与字段。作者自述、推广表达、购买与出镜身份分别分析。
7. 部分失败保留 JSON、`.media` 目录及原回执，按 completeness.failure、commentsComplete、media.complete 和逐项状态标明缺口。重试用新输出文件名与同名媒体目录，保留历史尝试；已有完整归档可按摘要复用。只有正文而缺媒体的记录按部分采集呈现，不能计入完整归档数量。
8. 抽帧由本地视频工具处理 CLI 保存的文件，记录笔记 ID、视频相对路径、SHA-256、时间点和帧文件。视频主片段、Live 片段和封面按 role 区分，不将同笔记的多个媒体当成独立研究来源。
9. 返回 N2.5 人物与场景策划，按事先列出的具体问题选择并分析证据，结合Agent创作判断补齐可生图设定卡，再输出方向包或停在用户指定的逐环节确认点。

## 产物与验收

研究目录保留搜索工作簿、回执，每个笔记 ID 子目录包含 JSON、同名媒体目录、正文、链接、评论和观察。根索引记录采集入口与版本、搜索条件、独立笔记数、评论完整性、媒体数量与失败项。下游直接消费已归档文件及其来源。

浏览器、登录、验证、限流和过期链接按 xhscli 文档恢复，回到搜索或该篇详情。接入验证通过同一 CLI 的 search→选样→note get --download-media→完整性与本地摘要验证，至少覆盖图文及可用的视频或 Live 文件。其他宿主依靠相同能力合同，按实际验证范围报告。
