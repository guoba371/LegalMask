# LegalMask — 中文法律文书智能脱敏工具

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/built%20with-Streamlit-ff4b4b.svg)](https://streamlit.io/)

将含真实当事人信息的法律文书脱敏后安全提交 AI 分析，分析结果可一键还原为真实姓名。**完全本地运行，数据不出本机。**

---

## 为什么需要 LegalMask？

通用 PII 工具（如 OpenAI Privacy Filter）处理中文法律文书时存在结构性缺陷：

| 问题 | 通用工具 | LegalMask |
|------|---------|-----------|
| `第87条` 被误判为数字删除 | ❌ 删除 → 法律分析失效 | ✅ 自动保护，完整保留 |
| 案号 `（2023）京0105民初12345号` | ❌ 无法识别 | ✅ 完整捕获并编号 |
| 18位统一社会信用代码 | ❌ 漏检 | ✅ 含校验位校验 |
| 同一人多处出现不一致替换 | ❌ 每处独立mask | ✅ 指代消解，全文一致 |
| 原告/被告等角色+姓名组合 | ❌ 拆散识别 | ✅ 整体捕获 |
| DOCX 格式被破坏 | ❌ 返回纯文本 | ✅ Run-by-run 格式保留 |
| 脱敏不可逆 | ❌ 无法还原 | ✅ JSON mapping 精确还原 |

---

## 快速开始

```bash
pip install -r requirements.txt
streamlit run app.py
```

浏览器自动打开 `http://localhost:8501`

---

## 核心能力

### 分层脱敏引擎（`core/processor.py`）

```
手动补充 — 自定义字段/词条   [X1]/[X2] 占位，按原文精确匹配
Layer 0   — 法条保护         第X条/第X款 → __LAW_N__ 占位，处理后还原
Layer 0.5 — 指代消解         扫描姓名 → 分配 [P1]/[P2] 编号，全文统一替换
Layer 1   — 唯一标识         身份证号、手机号、统一社会信用代码
Layer 2   — 金额             万元/亿元/元，含百分比
Layer 3   — 案号             （YYYY）X民初XXXXX号，含 mapping 还原
Layer 4   — 机构名称         法院、金融机构、政府部门
Layer 5   — 当事人姓名       基于 Layer 0.5 构建的 surname→code 映射
Layer 6   — 日期与地址
Layer 7   — 其他             车牌、邮箱、URL、社交账号
Layer 8   — 清理             去除多余空白
Layer 9   — 还原法条         __LAW_N__ → 原始法条引用
```

### 格式保留

- **DOCX**：Run-by-run 处理，保留字体、加粗、颜色等格式
- **PDF**：保留原版式，页面以高分辨率图像保存，并附可检索文字层；嵌入式 Logo、印章和签名图会被白底遮盖
- **手动补充字段**：界面上每行填写一个漏检的人名、项目代号或编号，适用于 DOCX、文字版/扫描版 PDF

### 完整双向流程

```
原始文件 → [脱敏] → 脱敏文件 + mapping.json
                          ↓
                     提交 AI 分析
                          ↓
AI 返回文本 → [还原] → 含真实姓名的分析结论
```

---

## 支持格式

| 格式 | 脱敏 | 格式保留 |
|------|------|---------|
| `.docx` | ✅ | ✅ Run-by-run |
| `.pdf`（文字层）| ✅ | ✅ Block-by-block |
| 扫描版 PDF | ✅ 本地 OCR | ✅ 页面图像保留 |
| `.txt` / `.md` | ✅ | 纯文本 |

---

## API 参考

```python
from core.processor import process_document, restore_text, load_mapping

# 脱敏单个文件（可选：补充自动识别遗漏的字段）
result = process_document(
    "contract.docx",
    output_dir="./out",
    custom_terms=["星河计划", "ZX-7788"],
)
# result.output_file  → 脱敏后文件路径
# result.mapping_file → mapping JSON 路径
# result.entity_count → 脱敏实体数量
# result.ocr_page_count → 使用本地 OCR 的扫描页数量

# 还原 AI 分析结果
mapping = load_mapping(result.mapping_file)
restored = restore_text(ai_analysis_text, mapping)
```

---

## 已知限制

- 扫描版 PDF 使用 RapidOCR + ONNX Runtime 在本机识别，首次加载模型或页数较多时会较慢
- OCR 对模糊、倾斜、手写或低分辨率扫描件可能存在识别误差，需人工核查
- PDF 输出为版式保真图像 + 可检索文字层，文件体积会大于原文件
- 建议人工核查脱敏结果，确认无遗漏实体
- 极复杂嵌套法条引用（如"第87条第2款第3项"）可能需要手动校验

---

## 技术栈

- Python 3.10+
- Streamlit（UI）
- python-docx（DOCX 处理）
- PyMuPDF / pdfplumber（PDF 处理）

---

## License

[MIT](LICENSE)
