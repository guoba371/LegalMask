# LegalMask · 律师文书智能脱敏工具

**本地运行的法律文书脱敏工具：双击打开，不需要安装 Python，文件和当事人信息始终留在本机。**

## 下载桌面版

前往 [最新版本下载页](https://github.com/guoba371/LegalMask/releases/latest)：

| 系统 | 下载哪个文件 |
|------|--------------|
| Windows 10 / 11（64 位） | `LegalMask-Windows-x64-Setup.exe` |
| Mac（Apple M1/M2/M3/M4） | `LegalMask-macOS-AppleSilicon.zip` |
| Mac（Intel 处理器） | `LegalMask-macOS-Intel.zip` |

Mac 下载后解压，把 `LegalMask` 拖进“应用程序”。首次打开时，在 Finder 中按住 **Control** 点按 LegalMask，选择 **打开**，之后再正常双击即可。如果系统没有显示“打开”选项，请前往 **系统设置 → 隐私与安全性**，点击“仍要打开”。

不确定 Mac 芯片类型时，点击左上角苹果菜单 → **关于本机**，查看“芯片”或“处理器”。

> macOS 最低支持版本：**macOS 12**。Windows 首次启动若出现 SmartScreen 提示，可选择“更多信息” →“仍要运行”。

## 三步使用

| 步骤 | 操作 |
|------|------|
| 1. 脱敏 | 上传 Word 或 PDF；如有自动识别遗漏，在“手动补充敏感字段”中每行填写一个词条，再点击“开始脱敏”并下载文件 |
| 2. AI 分析 | 将脱敏版文件提交给 AI，获取分析建议 |
| 3. 还原 | 将 AI 返回的文本粘贴到“还原”区，加载对应的 Mapping 文件，一键替换回真实信息 |

## 支持格式

- Word 文档（`.docx`）
- PDF（文字版或扫描版）

扫描版 PDF 使用内置 OCR 在本机识别，不会上传文件。PDF 脱敏后会保留原版式，页面以高分辨率图像保存，并附可检索文字层。嵌入式 Logo、印章和签名图会被白底遮盖，文件体积通常会大于原 PDF。

自动识别后仍有遗漏时，可在“手动补充敏感字段”中填写项目代号、内部编号或其他特定词条。系统按原文精确匹配，并写入 Mapping，支持后续还原。

> OCR 对模糊、倾斜、手写或低分辨率扫描件可能存在识别误差。提交 AI 前请人工核查脱敏结果。

## 隐私与故障排查

- 完全本地运行，不上传文书
- 程序关闭后自动清理临时文件
- Windows 日志：`%LOCALAPPDATA%\LegalMask\logs\legalmask.log`
- macOS 日志：`~/Library/Application Support/LegalMask/logs/legalmask.log`

如遇问题，请在 [GitHub Issues](https://github.com/guoba371/LegalMask/issues) 反馈，并附上日志文件。
