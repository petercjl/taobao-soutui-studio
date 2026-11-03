# SealSeek图像生成交接

## 依赖与责任

逻辑Skill名为sealseek-media，npm包为@petercjl/sealseek-media-cli，所需合同为有序参考图生成、模型与比例/分辨率发现、dry-run、提交、task_id跟踪恢复和本地交付。已对照0.6.9；运行时读取当前合同，兼容升级允许，缺失功能返回CONTRACT_UNSUPPORTED。

应用决定商品事实、场景、文案、参考角色、生成顺序、模型选择和项目状态；能力包负责鉴权、上传参考、提交与跟踪任务、下载及可验证结果。运行时不复制服务集成，不调用私有模块或自行重建API。

## 主线

1. 从当前宿主公布的Skill目录精确解析sealseek-media，读取完整当前SKILL.md。通过该安装的scripts/run.mjs执行skill source --json并加载其canonical当前版本，资源相对canonical目录解析。普通调用显式传当前Agent和解析的skill-path；不依赖作者机器路径或其他Agent安装。
2. 用capabilities --live --json发现实时能力和鉴权，再models show所选ID --live --json。本应用采用用户指定的Nano Banana Pro，默认显式传--model nano-banana-pro；本次用户明确指定其他模型时遵循该选择。俗称仅在目录唯一对应时规范化为真实模型ID，不能猜测或换到相邻模型。
3. image generate携带prompt、有序reference、ratio、resolution、count=1及新output目录。先--dry-run --json，不上传不计费；验证后，在用户生图授权内用--via sealseek --submit提交一次。每方向八张独立候选各有自己的任务记录。应用只需本地项目时显式--archive none；用户指定canvas/session/placement时完整保留。
4. 保存task_id，用task get/wait查询同一任务；每次等待不超过60秒。失败先task diagnose，断线或超时按当前合同恢复；未知结果不能通过--new、换参数或改提示词自动重新扣费。
5. succeeded后核对输出数量、实际文件、字节摘要、请求模型与实际尺寸，再回N4对照参考逐项检查。模型名是请求参数，不视为已核实服务端实际模型身份。画布归档或下载失败只恢复对应步骤，不重新生成。

## 参数与验收

比例和分辨率必须由模型实时能力给出。当前合同不支持精确像素size和蒙版inpainting；不能把参数说明改写成已支持像素锁定。3:4或2K是请求，实际图像可能采用模型取整尺寸，仍须测量并按发布合同检查。输入参考角色由应用在prompt说明，CLI负责原样保留输入顺序。

成功归一化为ok、artifacts、metadata、task_id、cost、warnings；错误保留原code/message并返回明确恢复点。认证失败回发现节点；不支持要求停止并交用户选择，不自动换供应方或模型。该包安装与更新仅针对当前Agent；正常运行不维护其他Agent目录。
