"""
LegalMask core processor — local redaction engine, no external API.
Extracted and restructured from clean_local_v2.py.
"""

import io
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Tuple, Dict


# ---------------------------------------------------------------------------
# Public data types
# ---------------------------------------------------------------------------

@dataclass
class ProcessResult:
    success: bool
    input_file: str
    output_file: str | None = None
    mapping_file: str | None = None
    mapping_dict: dict = field(default_factory=dict)
    error: str | None = None
    entity_count: int = 0
    ocr_page_count: int = 0


# ---------------------------------------------------------------------------
# Internal: shared redaction vocabulary
# ---------------------------------------------------------------------------

_LEGAL_ROLES = (
    "再审申请人|再审被申请人|申请执行人|被执行人|委托诉讼代理人|委托代理人|"
    "诉讼代理人|反诉原告|反诉被告|本诉原告|本诉被告|法定代表人|执行事务合伙人|"
    "申请人|被申请人|上诉人|被上诉人|原告|被告|第三人|辩护人|联系人|经办人|"
    "授权代表|经纪人|代理人|债权人|债务人|担保人|保证人|抵押人|出质人|"
    "买方|卖方|出租方|承租方|发包方|承包方|委托人|受托人|"
    "甲方|乙方|丙方|丁方|戊方|己方|庚方|辛方|壬方|癸方|负责人|审判长|审判员|书记员"
)

_NAME_STOPWORDS = {
    "认为", "诉称", "辩称", "表示", "主张", "请求", "申请", "起诉", "上诉",
    "答辩", "拒绝", "偿还", "支付", "承担", "同意", "签订", "履行", "违约",
    "本案", "该案", "原告", "被告", "第三人", "甲方", "乙方", "丙方", "丁方",
    "委托", "诉讼", "指派", "聘请", "授权", "本人", "公司", "代理",
}

_NAME_END_STOPWORDS = set(
    "的地得了和与及为是在有无未已应将可能对向自其该本等中上下内外后前时"
    "人方事务权利费用款项日月年据先齐索案作担付收取得到成为于因由把被让给"
    "经按依照诉辩称求请批准签订履行违约赔偿损失责任义务权益利息金额价费税"
    "票账户银行法院律师代理人"
)

_NAME_PHRASE_BLACKLIST = {
    "商业秘密", "实际获得", "下落不明", "已支付", "联系电话", "自行承担",
    "指派其他", "拒不支付", "签字确认", "另行支付", "坚持追求", "应优先",
}

_COMMON_SURNAMES = set(
    "赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜戚谢邹喻柏水窦章云苏潘葛奚范彭郎鲁韦昌马苗凤花方俞任袁柳酆鲍史唐费廉岑薛雷贺倪汤滕殷罗毕郝邬安常乐于时傅皮卞齐康伍余元卜顾孟平黄和穆萧尹姚邵湛汪祁毛禹狄米贝明臧计伏成戴谈宋茅庞熊纪舒屈项祝董梁杜阮蓝闵席季麻强贾路娄危江童颜郭梅盛林刁钟徐邱骆高夏蔡田樊胡凌霍虞万支柯昝管卢莫经房裘缪干解应宗丁宣贲邓郁单杭洪包诸左石崔吉钮龚程嵇邢滑裴陆荣翁荀羊於惠甄曲家封芮羿储靳汲邴糜松井段富巫乌焦巴弓牧隗山谷车侯宓蓬全郗班仰秋仲伊宫宁仇栾暴甘钭厉戎祖武符刘景詹束龙叶幸司韶郜黎蓟薄印宿白怀蒲邰从鄂索咸籍赖卓蔺屠蒙池乔阴胥能苍双闻莘党翟谭贡劳逄姬申扶堵冉宰郦雍却璩桑桂濮牛寿通边扈燕冀郏浦尚农温别庄晏柴瞿阎充慕连茹习宦艾鱼容向古易慎戈廖庾终暨居衡步都耿满弘匡国文寇广禄阙东欧殳沃利蔚越夔隆师巩厍聂晁勾敖融冷訾辛阚那简饶空曾毋沙乜养鞠须丰巢关蒯相查后荆红游竺权逯盖益桓公"
)

_COMPOUND_SURNAMES = (
    "欧阳", "太史", "端木", "上官", "司马", "东方", "独孤", "南宫", "万俟",
    "闻人", "夏侯", "诸葛", "尉迟", "公羊", "赫连", "澹台", "皇甫", "宗政",
    "濮阳", "公冶", "太叔", "申屠", "公孙", "慕容", "仲孙", "钟离", "长孙",
    "宇文", "司徒", "鲜于", "司空", "闾丘", "子车", "亓官", "司寇", "巫马",
    "公西", "颛孙", "壤驷", "公良", "漆雕", "乐正", "宰父", "谷梁", "拓跋",
    "夹谷", "轩辕", "令狐", "段干", "百里", "呼延", "东郭", "南门", "羊舌",
    "微生", "梁丘", "左丘", "东门", "西门",
)

_PERSON_TITLE_SUFFIXES = (
    "律师", "先生", "女士", "经理", "法官", "书记员", "代理人", "代表", "老师",
)

_ORG_SUFFIXES = (
    "有限责任公司", "股份有限公司", "有限公司", "律师事务所", "事务所", "公司",
    "集团", "企业", "银行", "支行", "分行", "信用社", "医院", "大学", "学院",
    "学校", "研究院", "研究所", "委员会", "人民政府", "政府", "法院",
)

_ORG_STOPWORDS = {
    "本公司", "贵公司", "该公司", "甲方公司", "乙方公司", "公司", "集团", "企业",
}


class _RedactionRegistry:
    """Assign stable, short ASCII placeholders and retain the reverse mapping."""

    _PREFIXES = {
        "PARTY": "P",
        "ID": "ID",
        "PHONE": "PH",
        "CREDIT": "CC",
        "AMOUNT": "M",
        "PERCENT": "PCT",
        "CASE": "C",
        "REFERENCE": "R",
        "ORG": "O",
        "ACCOUNT": "AC",
        "BANK": "B",
        "DATE": "D",
        "ADDRESS": "A",
        "JUDGE": "J",
        "POSTAL": "Z",
        "PLATE": "L",
        "EMAIL": "E",
        "URL": "U",
        "SOCIAL": "S",
        "CONTRACT": "CT",
        "CUSTOM": "X",
    }

    def __init__(self) -> None:
        self.mapping: Dict[str, str] = {}
        self._reverse: Dict[str, str] = {}
        self._counters: Dict[str, int] = {}

    def token(self, category: str, original: str) -> str:
        if original in self._reverse:
            return self._reverse[original]

        number = self._counters.get(category, 0) + 1
        self._counters[category] = number
        prefix = self._PREFIXES[category]
        token = f"[{prefix}{number}]"
        self._reverse[original] = token
        self.mapping[token] = original
        return token

    def replace(self, text: str, pattern: str, category: str, flags: int = 0) -> str:
        return re.sub(
            pattern,
            lambda match: self.token(category, match.group(0)),
            text,
            flags=flags,
        )

    def replace_group(
        self,
        text: str,
        pattern: str,
        category: str,
        group: int = 1,
        flags: int = 0,
    ) -> str:
        def replace_match(match: re.Match) -> str:
            start = match.start(group) - match.start(0)
            end = match.end(group) - match.start(0)
            whole = match.group(0)
            return f"{whole[:start]}{self.token(category, match.group(group))}{whole[end:]}"

        return re.sub(pattern, replace_match, text, flags=flags)


def _valid_person_name(name: str) -> bool:
    if not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", name):
        return False
    if name in _NAME_STOPWORDS or name.startswith(("原告", "被告", "第三人")):
        return False
    if name in _NAME_PHRASE_BLACKLIST or name[-1] in _NAME_END_STOPWORDS:
        return False
    if not (name.startswith(_COMPOUND_SURNAMES) or name[0] in _COMMON_SURNAMES):
        return False
    return not any(name.endswith(suffix) for suffix in _PERSON_TITLE_SUFFIXES)


def _collect_party_names(text: str) -> list[str]:
    names: set[str] = set()

    role_colon_pattern = re.compile(
        rf"({_LEGAL_ROLES})[\s]*[：:][\s]*([\u4e00-\u9fa5]{{2,4}})"
        r"(?=[，,。；;、\s（）()]|$)",
        re.MULTILINE,
    )
    for match in role_colon_pattern.finditer(text):
        name = match.group(2)
        if _valid_person_name(name):
            names.add(name)

    role_direct_pattern = re.compile(
        rf"({_LEGAL_ROLES})([\u4e00-\u9fa5]{{2,4}}?)"
        r"(?=与|和|及|向|对|于|签订|起诉|上诉|申请|请求|诉称|辩称|认为|表示|"
        r"主张|应|未|已|拒绝|系|律师|先生|女士|经理|代理人|法官|书记员|"
        r"[，,。；;、（）()])",
        re.MULTILINE,
    )
    for match in role_direct_pattern.finditer(text):
        name = match.group(2)
        if _valid_person_name(name):
            names.add(name)

    role_link_pattern = re.compile(
        rf"({_LEGAL_ROLES})[\s]*(?:为|是|系)[\s]*([\u4e00-\u9fa5]{{2,4}})"
        r"(?=[，,。；;、\s（）()]|$)",
        re.MULTILINE,
    )
    for match in role_link_pattern.finditer(text):
        name = match.group(2)
        if _valid_person_name(name):
            names.add(name)

    label_pattern = re.compile(
        r"(?:姓名|名字)[\s：:]*([\u4e00-\u9fa5]{2,4})(?=[，,。；;、：:\s（）()]|$)",
        re.MULTILINE,
    )
    for match in label_pattern.finditer(text):
        name = match.group(1)
        if _valid_person_name(name):
            names.add(name)

    for match in re.finditer(r"[\u4e00-\u9fa5]某{1,2}", text):
        name = match.group(0)
        if _valid_person_name(name):
            names.add(name)

    title_suffix = (
        r"(?=\s*(?:律师(?!事务所)|先生|女士|经理|法官|书记员|代理人))"
    )
    title_role_pattern = re.compile(
        r"(?:指派|聘请|委托|由|为|让|请|经|指定)[\s]*"
        r"([\u4e00-\u9fa5]{2,4})"
        + title_suffix,
        re.MULTILINE,
    )
    for match in title_role_pattern.finditer(text):
        name = match.group(1)
        if _valid_person_name(name):
            names.add(name)

    title_line_pattern = re.compile(
        r"(?:^|[\s：:，,。；;、（(])"
        r"(?!(?:指派|聘请|委托|由|为|让|请|经|指定))"
        r"([\u4e00-\u9fa5]{2,4})"
        + title_suffix,
        re.MULTILINE,
    )
    for match in title_line_pattern.finditer(text):
        name = match.group(1)
        if _valid_person_name(name):
            names.add(name)

    return sorted(names, key=len, reverse=True)


def _replace_organizations(text: str, registry: _RedactionRegistry) -> str:
    pattern = re.compile(
        r"(^|[\s：:，,。；;、（(]|由|向|在|与|为|和|及|请|对|将|把)"
        r"([\u4e00-\u9fa5A-Za-z0-9（）()·\-]{2,40}"
        rf"(?:{'|'.join(_ORG_SUFFIXES)}))",
        re.MULTILINE,
    )

    def replace_match(match: re.Match) -> str:
        candidate = match.group(2)
        if candidate in _ORG_STOPWORDS or len(candidate) < 3:
            return match.group(0)
        prefix = ""
        if candidate.startswith(
            ("甲方", "乙方", "丙方", "丁方", "原告", "被告", "第三人",
             "本合同", "双方", "根据", "经", "本", "该", "因")
        ):
            separators = ("委托", "聘请", "指派", "指定", "因", "与", "和",
                          "及", "向", "对", "为", "在", "由", "请", "将", "把")
            positions = [
                (candidate.rfind(separator), separator)
                for separator in separators
                if candidate.rfind(separator) >= 0
            ]
            if positions:
                index, separator = max(positions, key=lambda item: item[0])
                end = index + len(separator)
                if len(candidate) - end >= 3:
                    prefix = candidate[:end]
                    candidate = candidate[end:]
        return f"{match.group(1)}{prefix}{registry.token('ORG', candidate)}"

    return pattern.sub(replace_match, text)


# ---------------------------------------------------------------------------
# Internal: core redaction logic (ported from clean_sensitive_info)
# ---------------------------------------------------------------------------

def _clean_sensitive_info(
    text: str, custom_terms: list[str] | None = None
) -> Tuple[str, Dict[str, str]]:
    """脱敏处理，返回 (脱敏后文本, 占位符→原值 mapping_dict)。"""

    registry = _RedactionRegistry()

    # Manual terms run first so automatic rules cannot split a user-specified value.
    normalized_terms = sorted(
        {term.strip() for term in custom_terms or [] if term.strip()},
        key=len,
        reverse=True,
    )
    for term in normalized_terms:
        text = text.replace(term, registry.token("CUSTOM", term))

    # ── Layer 0: protect statute references ──────────────────────────────
    law_refs = []
    law_counter = 1

    law_pattern = (
        r"第"
        r"(?:[零一二三四五六七八九十百千万]+|\d+)"
        r"(?:条|款|项|)?"
        r"(?:之[零一二三四五六七八九十百千万\d]+)?"
        r"(?:第(?:[零一二三四五六七八九十百千万]+|\d+)(?:条|款|项))*"
    )

    def replace_law(match: re.Match) -> str:
        nonlocal law_counter
        ref = match.group(0)
        marker = f"__LAW_{law_counter}__"
        law_refs.append((marker, ref))
        law_counter += 1
        return marker

    text = re.sub(law_pattern, replace_law, text)

    # Collect complete names before any other redaction changes the text.
    party_names = _collect_party_names(text)

    # ── Layer 1: unique identifiers ───────────────────────────────────────
    # Use lookahead/lookbehind instead of \b — Chinese chars are \w in Python
    text = registry.replace(text, r"(?<!\d)\d{17}[\dXx](?!\d)", "ID")
    text = registry.replace_group(
        text,
        r"((?:联系电话|手机号码|手机号|手机|电话|联系方式)[\s：:]*)"
        r"((?:\+?86[- ]?)?(?:1[3-9]\d{9}|0\d{2,3}[- ]?\d{7,8}))",
        "PHONE",
        group=2,
    )
    text = registry.replace(text, r"(?<!\d)1[3-9]\d{9}(?!\d)", "PHONE")
    text = registry.replace(
        text,
        r"(?<![0-9A-Z])[0-9A-HJ-NPQRTUWXY]{2}\d{6}[0-9A-HJ-NPQRTUWXY]{10}(?![0-9A-Z])",
        "CREDIT",
    )

    # ── Layer 2: amounts ──────────────────────────────────────────────────
    text = registry.replace(
        text,
        r"(?<![\d,])(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
        r"(?=\s*(?:万元|亿元|元|美元|英镑|港币))",
        "AMOUNT",
    )
    text = registry.replace(text, r"(?<![\d.])\d+(?:\.\d+)?%", "PERCENT")

    # ── Layer 3: case numbers & reference IDs ─────────────────────────────
    text = registry.replace(
        text,
        r"[（(]\d{4}[）)]"
        r"[\u4e00-\u9fa5]{0,4}"
        r"\d+"
        r"[\u4e00-\u9fa5]*"
        r"\d+"
        r"[a-zA-Z\u4e00-\u9fa5]*"
        r"号",
        "CASE",
    )

    text = registry.replace_group(
        text,
        r"(入库编号[\s：:]*)(\d{4}-\d+-\d+-\d+-\d+)",
        "REFERENCE",
        group=2,
    )
    text = registry.replace_group(
        text, r"(档案编号[\s：:]*)([\w-]+)", "REFERENCE", group=2
    )
    text = registry.replace_group(
        text, r"(案件编号[\s：:]*)([\w-]+)", "REFERENCE", group=2
    )

    # ── Layer 3.5: addresses (before organization names) ──────────────────
    address_label = (
        r"(?:联系地址|户籍地址|注册地址|办公地址|送达地址|通讯地址|现住址|"
        r"住址|住所|地址|居住地|户籍地|合同签订地|合同签署地|签订地|签署地)"
    )
    text = registry.replace_group(
        text,
        rf"^([ \t]*{address_label}[\s：:]*)([^\n]{{2,120}})$",
        "ADDRESS",
        group=2,
        flags=re.MULTILINE,
    )
    text = registry.replace_group(
        text,
        r"((?<!居)住)([\u4e00-\u9fa5\d（）()\-—·#]{4,80}?)"
        r"(?=联系电话|联系方式|电话|邮编|[，。；;\n]|$)",
        "ADDRESS",
        group=2,
        flags=re.MULTILINE,
    )
    text = registry.replace_group(
        text,
        r"((?:[\u4e00-\u9fa5]{2,10}(?:省|自治区))?"
        r"[\u4e00-\u9fa5]{2,10}(?:市|自治州|地区)"
        r"[\u4e00-\u9fa5]{0,12}(?:区|县|旗)"
        r"[\u4e00-\u9fa5\d]{0,30}(?:路|街|道|巷|弄|号)"
        r"[\u4e00-\u9fa5\d]{0,30})",
        "ADDRESS",
        group=1,
    )
    text = registry.replace_group(
        text,
        r"^([ \t]*(?:[\u4e00-\u9fa5]{2,10}(?:省|自治区))?"
        r"[\u4e00-\u9fa5]{2,10}(?:市|县|区|旗)"
        r"(?=[^\n]{2,100}$)"
        r"(?=[^\n]*(?:路|街|道|巷|弄|号|镇|乡|村|社区|小区|大厦|广场|楼|室))"
        r"[^\n]{2,100})$",
        "ADDRESS",
        group=1,
        flags=re.MULTILINE,
    )

    # ── Layer 4: institution names ────────────────────────────────────────
    text = _replace_organizations(text, registry)

    text = registry.replace_group(
        text,
        r"(账户名称[\s：:]*)([\u4e00-\u9fa5A-Za-z0-9（）()]{2,40})",
        "ACCOUNT",
        group=2,
    )
    text = registry.replace_group(
        text, r"(账号[\s：:]*)(\d{10,20})", "ACCOUNT", group=2
    )
    text = registry.replace_group(
        text,
        r"(开户行[\s：:]*)([\u4e00-\u9fa5A-Za-z0-9（）()]{2,40})",
        "ORG",
        group=2,
    )
    text = registry.replace_group(
        text, r"(合同编号[\s：:]*)([\w-]+\d+)", "CONTRACT", group=2
    )
    text = registry.replace_group(
        text,
        r"((?:审判长|审判员|书记员)[\s：:]*)([\u4e00-\u9fa5]{2,4})",
        "JUDGE",
        group=2,
    )
    text = registry.replace(text, r"(?<!\d)\d{16,19}(?!\d)", "BANK")

    # ── Layer 6: dates and addresses ──────────────────────────────────────
    text = registry.replace(text, r"\d{4}年\d{1,2}月\d{1,2}日", "DATE")
    text = registry.replace(text, r"\d{4}年\d{1,2}月", "DATE")
    text = registry.replace(text, r"\d{4}-\d{1,2}-\d{1,2}", "DATE")
    text = registry.replace(text, r"\d{4}/\d{1,2}/\d{1,2}", "DATE")

    text = registry.replace_group(
        text, r"(邮政编码[\s：:]*)(\d{6})", "POSTAL", group=2
    )

    # ── Layer 5: replace every occurrence of the collected party names ─────
    for name in party_names:
        text = text.replace(name, registry.token("PARTY", name))

    # ── Layer 7: miscellaneous ────────────────────────────────────────────
    text = registry.replace(text, r"[\u4e00-\u9fa5][A-Z][A-Z0-9]{5,6}", "PLATE")
    text = registry.replace(text, r"[\w.-]+@[\w.-]+\.\w+", "EMAIL")
    text = registry.replace(text, r"https?://[\w.-]+(?:/[\w./%-]*)?", "URL")
    text = registry.replace_group(
        text,
        r"((?:QQ|微信|微信号)[\s：:]*)([\w-]{6,20})",
        "SOCIAL",
        group=2,
    )

    # ── Layer 9: restore statute references ───────────────────────────────
    for marker, ref in law_refs:
        text = text.replace(marker, ref)

    return text, registry.mapping


def _count_entities(mapping_dict: Dict[str, str], redacted_text: str) -> int:
    """Count distinct placeholders that actually appear in the redacted text."""
    static_tags = re.findall(r"\{\{[A-Z_]+(?:_\d+)?\}\}", redacted_text)
    all_keys = set(mapping_dict.keys()) | set(static_tags)
    return len(all_keys)


def _safe_output_stem(stem: str, mapping_dict: Dict[str, str]) -> str:
    """Keep captured values out of generated file names."""
    safe = stem
    for value in sorted({v for v in mapping_dict.values() if v}, key=len, reverse=True):
        if value in safe:
            safe = safe.replace(value, "redacted")
    safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", safe)
    safe = re.sub(r"\s+", " ", safe).strip(" .")
    return safe or "document"


def _unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    for index in range(2, 1000):
        candidate = path.with_name(f"{path.stem}_{index}{path.suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"无法为输出文件生成唯一名称: {path.name}")


# ---------------------------------------------------------------------------
# Internal: file extraction helpers
# ---------------------------------------------------------------------------

def _extract_text_plain(filepath: Path) -> str:
    """Extract text from .txt or .md."""
    return filepath.read_text(encoding="utf-8", errors="ignore")


def _iter_table_paragraphs(table):
    for row in table.rows:
        for cell in row.cells:
            yield from cell.paragraphs
            for nested in cell.tables:
                yield from _iter_table_paragraphs(nested)


def _iter_docx_paragraphs(doc):
    yield from doc.paragraphs
    for table in doc.tables:
        yield from _iter_table_paragraphs(table)

    for section in doc.sections:
        for container in (
            section.header,
            section.first_page_header,
            section.even_page_header,
            section.footer,
            section.first_page_footer,
            section.even_page_footer,
        ):
            yield from container.paragraphs
            for table in container.tables:
                yield from _iter_table_paragraphs(table)


def _extract_text_docx(filepath: Path) -> str:
    """Extract plain text from a .docx file."""
    import docx  # python-docx
    doc = docx.Document(str(filepath))
    paragraphs = [p.text.strip() for p in _iter_docx_paragraphs(doc) if p.text.strip()]
    return "\n\n".join(paragraphs)


def _extract_text_pdf_fitz(filepath: Path) -> str:
    """Extract text from a digital PDF using PyMuPDF."""
    import pymupdf
    doc = pymupdf.open(str(filepath))
    parts = [doc[i].get_text() for i in range(len(doc)) if doc[i].get_text().strip()]
    doc.close()
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Internal: replacement across run boundaries
# ---------------------------------------------------------------------------

def _replace_in_paragraph(paragraph, reverse_map: Dict[str, str]) -> None:
    """Replace values across runs while leaving each run object and its style intact."""
    runs = paragraph.runs
    if not runs:
        return

    texts = [run.text for run in runs]
    for original, placeholder in sorted(
        reverse_map.items(), key=lambda item: len(item[0]), reverse=True
    ):
        while True:
            combined = "".join(texts)
            start = combined.find(original)
            if start < 0:
                break
            end = start + len(original)

            offsets = []
            cursor = 0
            for value in texts:
                offsets.append((cursor, cursor + len(value)))
                cursor += len(value)

            first = next(
                (i for i, (run_start, run_end) in enumerate(offsets) if run_start <= start < run_end),
                None,
            )
            last = next(
                (i for i, (run_start, run_end) in enumerate(offsets) if run_start < end <= run_end),
                None,
            )
            if first is None or last is None:
                break

            first_start = start - offsets[first][0]
            last_end = end - offsets[last][0]
            if first == last:
                texts[first] = (
                    texts[first][:first_start] + placeholder + texts[first][last_end:]
                )
            else:
                texts[first] = texts[first][:first_start] + placeholder
                for index in range(first + 1, last):
                    texts[index] = ""
                texts[last] = texts[last][last_end:]

    for run, value in zip(runs, texts):
        if run.text != value:
            run.text = value


# ---------------------------------------------------------------------------
# Internal: format-preserving redaction
# ---------------------------------------------------------------------------

def _process_docx(
    input_path: Path,
    output_path: Path,
    custom_terms: list[str] | None = None,
) -> Dict[str, str]:
    """Apply a document-wide mapping across runs, preserving formatting."""
    import docx

    full_text = _extract_text_docx(input_path)
    _, mapping_dict = _clean_sensitive_info(full_text, custom_terms)
    reverse_map = {v: k for k, v in mapping_dict.items()}

    doc = docx.Document(str(input_path))
    for paragraph in _iter_docx_paragraphs(doc):
        _replace_in_paragraph(paragraph, reverse_map)

    properties = doc.core_properties
    properties.author = "LegalMask"
    properties.last_modified_by = "LegalMask"
    properties.title = ""
    properties.subject = ""
    properties.comments = ""
    properties.keywords = ""

    doc.save(str(output_path))
    return mapping_dict


_PDF_OCR_ENGINE = None


def _get_ocr_engine():
    global _PDF_OCR_ENGINE
    if _PDF_OCR_ENGINE is not None:
        return _PDF_OCR_ENGINE
    try:
        from rapidocr_onnxruntime import RapidOCR
    except ImportError as exc:
        raise RuntimeError(
            "扫描版 PDF 需要本地 OCR 依赖，请先运行 pip install -r requirements.txt"
        ) from exc
    _PDF_OCR_ENGINE = RapidOCR()
    return _PDF_OCR_ENGINE


def _ocr_pdf_page(page, engine, resolution: int = 300) -> tuple[list[dict], float]:
    """Run local OCR and return normalized text rectangles plus image contrast."""
    import numpy as np
    from PIL import Image, ImageStat

    import pymupdf

    scale = resolution / 72
    pixmap = page.get_pixmap(
        matrix=pymupdf.Matrix(scale, scale),
        alpha=False,
        colorspace=pymupdf.csRGB,
    )
    image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
    image_array = np.asarray(image)[:, :, ::-1].copy()
    result, _ = engine(image_array)

    lines = []
    for row in result or []:
        box, text, score = row
        text = str(text).strip()
        if not text:
            continue
        xs = [float(point[0]) / scale for point in box]
        ys = [float(point[1]) / scale for point in box]
        rect = (min(xs), min(ys), max(xs), max(ys))
        if rect[2] <= rect[0] or rect[3] <= rect[1]:
            continue
        lines.append({"text": text, "rect": rect, "score": float(score)})

    lines.sort(key=lambda line: (line["rect"][1], line["rect"][0]))
    contrast = float(ImageStat.Stat(image.convert("L")).stddev[0])
    return lines, contrast


def _replace_known_values(text: str, replacements: list[tuple[str, str]]) -> str:
    for original, placeholder in replacements:
        text = text.replace(original, placeholder)
    return text


def _normalize_ocr_text(text: str) -> str:
    """Remove form-fill underscores that otherwise interrupt OCR entities."""
    text = re.sub(r"[_＿]+", "", text)
    return re.sub(r"[ \t]+", " ", text).strip()


def _draw_fitted_text(
    draw,
    rect,
    text: str,
    scale: float,
    font_path: str,
    font_cache: dict,
    image_width: int,
    image_height: int,
) -> None:
    """White-cover one OCR line and redraw its redacted text inside that area."""
    from PIL import ImageFont

    x0 = max(0, int(rect.x0 * scale) - 2)
    y0 = max(0, int(rect.y0 * scale) - 2)
    x1 = min(image_width, int(rect.x1 * scale) + 2)
    y1 = min(image_height, int(rect.y1 * scale) + 2)
    draw.rectangle((x0, y0, x1, y1), fill=(255, 255, 255))

    max_width = max(1, x1 - x0 - 4)
    max_height = max(1, y1 - y0 - 2)
    pixel_size = max(8, int(max_height * 0.78))
    while pixel_size > 6:
        font = font_cache.get(pixel_size)
        if font is None:
            font = ImageFont.truetype(font_path, pixel_size)
            font_cache[pixel_size] = font
        text_box = draw.textbbox((0, 0), text, font=font)
        text_width = text_box[2] - text_box[0]
        text_height = text_box[3] - text_box[1]
        if text_width <= max_width and text_height <= max_height:
            break
        pixel_size -= 1

    text_box = draw.textbbox((0, 0), text, font=font)
    text_height = text_box[3] - text_box[1]
    text_x = x0 + 2
    text_y = y0 + max(0, (y1 - y0 - text_height) // 2) - text_box[1]
    draw.text((text_x, text_y), text, font=font, fill=(0, 0, 0))


def _is_law_firm_logo_caption(text: str) -> bool:
    compact = re.sub(r"[^A-Z]", "", text.upper())
    return "LAWFIRM" in compact and len(compact) >= 10


def _process_pdf_fitz(
    input_path: Path,
    output_path: Path,
    custom_terms: list[str] | None = None,
) -> tuple[Dict[str, str], int]:
    """Flatten each page to an image, cover sensitive text, and add a clean text layer.

    Keeping a high-resolution page image avoids PDF font subsetting and content-stream
    reordering issues while an invisible text layer keeps the result searchable and
    usable by AI document ingestion. Pages without a usable text layer are processed
    with the bundled local OCR model.
    """
    from PIL import Image, ImageDraw, ImageFont

    import pymupdf

    doc = pymupdf.open(str(input_path))
    new_doc = None
    try:
        ocr_pages: dict[int, list[dict]] = {}
        page_texts = []
        ocr_engine = None
        for page in doc:
            native_text = page.get_text().strip()
            if len(re.sub(r"\s+", "", native_text)) >= 20:
                page_texts.append(native_text)
                continue

            if ocr_engine is None:
                ocr_engine = _get_ocr_engine()
            ocr_lines, contrast = _ocr_pdf_page(page, ocr_engine)
            if not ocr_lines and contrast > 4:
                raise ValueError(
                    f"第 {page.number + 1} 页 OCR 未识别到有效文字，"
                    "请检查扫描清晰度或手动 OCR 后再试。"
                )
            ocr_pages[page.number] = ocr_lines
            page_texts.append(
                "\n".join(_normalize_ocr_text(line["text"]) for line in ocr_lines)
            )

        full_text = "\n\n".join(part for part in page_texts if part.strip())
        if not full_text.strip():
            raise ValueError("PDF 中没有识别到可脱敏文字。")

        _, mapping_dict = _clean_sensitive_info(full_text, custom_terms)
        reverse_map = {v: k for k, v in mapping_dict.items()}
        replacements = sorted(
            reverse_map.items(), key=lambda item: len(item[0]), reverse=True
        )
        cjk_font = _find_cjk_font()
        token_font = _find_latin_font() or cjk_font
        text_layer_font = pymupdf.Font(fontfile=cjk_font)
        scale = 200 / 72
        font_cache = {}
        new_doc = pymupdf.open()

        for page in doc:
            ocr_lines = ocr_pages.get(page.number)
            lines = [] if ocr_lines is not None else list(_iter_pdf_line_chars(page))
            boxes = []
            insertions = []
            ocr_redraws = []
            found_on_page = set()

            if ocr_lines is not None:
                for line in ocr_lines:
                    normalized_line = _normalize_ocr_text(line["text"])
                    cleaned_line = _replace_known_values(
                        normalized_line, replacements
                    )
                    if cleaned_line == normalized_line:
                        continue
                    rect = pymupdf.Rect(line["rect"])
                    boxes.append(rect)
                    ocr_redraws.append((rect, cleaned_line))

                for line in ocr_lines:
                    if _is_law_firm_logo_caption(line["text"]):
                        boxes.append(pymupdf.Rect(line["rect"]))
            else:
                for chars, _origin, _size in lines:
                    line_text = "".join(item["char"] for item in chars)
                    taken = [False] * len(chars)

                    for original, placeholder in replacements:
                        start = 0
                        while original:
                            start = line_text.find(original, start)
                            if start < 0:
                                break
                            end = start + len(original)
                            if any(taken[start:end]):
                                start += 1
                                continue

                            rect = pymupdf.Rect(chars[start]["bbox"])
                            for item in chars[start + 1:end]:
                                rect |= pymupdf.Rect(item["bbox"])
                            if rect.is_empty:
                                start = end
                                continue

                            boxes.append(rect)
                            insertions.append(
                                {
                                    "origin": pymupdf.Point(chars[start]["origin"]),
                                    "rect": rect,
                                    "text": placeholder,
                                    "size": chars[start]["size"],
                                }
                            )
                            for index in range(start, end):
                                taken[index] = True
                            found_on_page.add(original)
                            start = end

                # A few PDFs expose a value only through search, not rawdict chars.
                for original, placeholder in replacements:
                    if original in found_on_page or "\n" in original:
                        continue
                    for rect in page.search_for(original):
                        if rect.is_empty:
                            continue
                        boxes.append(rect)
                        insertions.append(
                            {
                                "origin": pymupdf.Point(rect.x0, rect.y1 - 2),
                                "rect": rect,
                                "text": placeholder,
                                "size": min(8.0, rect.height),
                            }
                        )
                        found_on_page.add(original)
                        break

            # Embedded images can contain logos, seals, or signatures that are
            # invisible to the text-layer detector. Keep full-page backgrounds.
            page_area = page.rect.get_area()
            for image in page.get_images(full=True):
                for rect in page.get_image_rects(image[0]):
                    if not rect.is_empty and rect.get_area() < page_area * 0.85:
                        boxes.append(rect)

            pixmap = page.get_pixmap(
                matrix=pymupdf.Matrix(scale, scale),
                alpha=False,
                colorspace=pymupdf.csRGB,
            )
            image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
            draw = ImageDraw.Draw(image)

            for rect in boxes:
                x0 = max(0, int(rect.x0 * scale) - 2)
                y0 = max(0, int(rect.y0 * scale) - 2)
                x1 = min(image.width, int(rect.x1 * scale) + 2)
                y1 = min(image.height, int(rect.y1 * scale) + 2)
                draw.rectangle((x0, y0, x1, y1), fill=(255, 255, 255))

            if ocr_lines is not None:
                for rect, cleaned_line in ocr_redraws:
                    _draw_fitted_text(
                        draw,
                        rect,
                        cleaned_line,
                        scale,
                        cjk_font,
                        font_cache,
                        image.width,
                        image.height,
                    )

            for item in insertions:
                pixel_size = max(8, int(min(item["size"], 8.0) * scale))
                font = font_cache.get(pixel_size)
                if font is None:
                    try:
                        font = ImageFont.truetype(token_font, pixel_size)
                    except OSError:
                        font = ImageFont.load_default(size=pixel_size)
                    font_cache[pixel_size] = font

                token_width = draw.textlength(item["text"], font=font)
                max_width = max((item["rect"].x1 - item["rect"].x0) * scale * 1.8, pixel_size * 1.5)
                if token_width > max_width:
                    pixel_size = max(7, int(pixel_size * max_width / token_width))
                    font = font_cache.get(pixel_size)
                    if font is None:
                        try:
                            font = ImageFont.truetype(token_font, pixel_size)
                        except OSError:
                            font = ImageFont.load_default(size=pixel_size)
                        font_cache[pixel_size] = font

                draw.text(
                    (item["origin"].x * scale, item["origin"].y * scale),
                    item["text"],
                    font=font,
                    fill=(0, 0, 0),
                    anchor="ls",
                )

            image_buffer = io.BytesIO()
            image.save(image_buffer, format="JPEG", quality=92, optimize=True)
            new_page = new_doc.new_page(width=page.rect.width, height=page.rect.height)
            new_page.insert_image(new_page.rect, stream=image_buffer.getvalue())

            if ocr_lines is not None:
                text_lines = []
                for line in ocr_lines:
                    cleaned_line = (
                        ""
                        if _is_law_firm_logo_caption(line["text"])
                        else _replace_known_values(
                            _normalize_ocr_text(line["text"]), replacements
                        )
                    )
                    text_lines.append(
                        (
                            cleaned_line,
                            (line["rect"][0], line["rect"][3]),
                            (line["rect"][3] - line["rect"][1]) * 0.75,
                            line["rect"],
                        )
                    )
            else:
                text_lines = [
                    (
                        _replace_known_values(
                            "".join(item["char"] for item in chars),
                            replacements,
                        ),
                        origin,
                        size,
                        None,
                    )
                    for chars, origin, size in lines
                ]

            for cleaned_line, origin, size, text_rect in text_lines:
                cleaned_line = _safe_pdf_text(cleaned_line, text_layer_font)
                if cleaned_line.strip():
                    if text_rect is not None:
                        origin = (
                            text_rect[0],
                            text_rect[3] - (text_rect[3] - text_rect[1]) * 0.18,
                        )
                    new_page.insert_text(
                        origin,
                        cleaned_line,
                        fontsize=max(float(size), 1.0),
                        fontname="cjk",
                        fontfile=cjk_font,
                        color=(0, 0, 0),
                        render_mode=3,
                        overlay=True,
                    )

        new_doc.set_metadata(
            {
                "title": "",
                "author": "",
                "subject": "",
                "keywords": "",
                "creator": "LegalMask",
                "producer": "LegalMask",
                "creationDate": "",
                "modDate": "",
                "trapped": "",
            }
        )
        new_doc.save(str(output_path), garbage=3, deflate=True)
    finally:
        if new_doc is not None:
            new_doc.close()
        doc.close()

    output_text = _extract_text_pdf_fitz(output_path)
    if not output_text.strip():
        output_path.unlink(missing_ok=True)
        raise RuntimeError("PDF 脱敏失败：输出文字层为空。")

    leftovers = [value for value in mapping_dict.values() if value and value in output_text]
    if leftovers:
        output_path.unlink(missing_ok=True)
        raise RuntimeError("PDF 脱敏校验失败：输出中仍有敏感文本残留。")

    return mapping_dict, len(ocr_pages)


def _iter_pdf_line_chars(page):
    raw = page.get_text("rawdict")
    for block in raw.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            chars = []
            for span in line.get("spans", []):
                size = float(span.get("size", 10))
                for char in span.get("chars", []):
                    chars.append(
                        {
                            "char": char.get("c", ""),
                            "bbox": tuple(char.get("bbox", (0, 0, 0, 0))),
                            "origin": tuple(char.get("origin", (0, 0))),
                            "size": size,
                        }
                    )
            if chars:
                first_span = line.get("spans", [{}])[0]
                yield (
                    chars,
                    tuple(first_span.get("origin", chars[0]["origin"])),
                    float(first_span.get("size", chars[0]["size"])),
                )


def _find_cjk_font() -> str:
    candidates = [
        r"C:\Windows\Fonts\simsun.ttc",
        r"C:\Windows\Fonts\msyh.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    ]
    for path in candidates:
        if Path(path).exists():
            return path
    raise RuntimeError("未找到可用的中文字体，无法生成 PDF 文字层。")


def _find_latin_font() -> str | None:
    candidates = [
        r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\segoeui.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    return next((path for path in candidates if Path(path).exists()), None)


def _safe_pdf_text(text: str, font) -> str:
    symbols = {
        "☑": "[x]",
        "√": "[x]",
        "■": "[x]",
        "●": "[x]",
        "□": "[ ]",
        "☐": "[ ]",
        "○": "[ ]",
    }
    result = []
    for char in text:
        if char in symbols:
            result.append(symbols[char])
        elif char == "\x00" or not font.has_glyph(ord(char)):
            result.append("?")
        else:
            result.append(char)
    return "".join(result)


def _process_pdf_fallback(
    input_path: Path,
    output_path: Path,
    custom_terms: list[str] | None = None,
) -> Dict[str, str]:
    """Fallback: extract text with pdfplumber, save redacted .txt."""
    try:
        import pdfplumber
        parts = []
        with pdfplumber.open(str(input_path)) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    parts.append(t.strip())
        raw = "\n\n".join(parts)
    except Exception:
        raw = ""

    cleaned, mapping_dict = _clean_sensitive_info(raw, custom_terms)
    txt_output = output_path.with_suffix(".txt")
    txt_output.write_text(cleaned, encoding="utf-8")
    return mapping_dict


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def process_document(
    input_path: str | Path,
    output_dir: str | Path,
    custom_terms: list[str] | None = None,
) -> ProcessResult:
    """处理单个DOCX或数字PDF文件。
    - 脱敏后文件保存到 output_dir/<原文件名>_cleaned.<ext>
    - mapping保存到 output_dir/<原文件名>_mapping.json
    - 返回ProcessResult
    """
    input_path = Path(input_path)
    output_dir = Path(output_dir)

    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        return ProcessResult(
            success=False,
            input_file=str(input_path),
            error=f"无法创建输出目录: {exc}",
        )

    suffix = input_path.suffix.lower()
    stem = input_path.stem
    output_file = _unique_path(output_dir / f"{stem}_cleaned{suffix}")
    mapping_file = _unique_path(output_dir / f"{stem}_mapping.json")
    ocr_page_count = 0

    try:
        if suffix == ".docx":
            mapping_dict = _process_docx(input_path, output_file, custom_terms)
        elif suffix == ".pdf":
            try:
                mapping_dict, ocr_page_count = _process_pdf_fitz(
                    input_path, output_file, custom_terms
                )
            except ImportError:
                output_file = output_dir / f"{stem}_cleaned.txt"
                mapping_dict = _process_pdf_fallback(
                    input_path, output_file, custom_terms
                )
        elif suffix in {".txt", ".md"}:
            raw = _extract_text_plain(input_path)
            cleaned, mapping_dict = _clean_sensitive_info(raw, custom_terms)
            output_file = output_dir / f"{stem}_cleaned{suffix}"
            output_file.write_text(cleaned, encoding="utf-8")
        else:
            return ProcessResult(
                success=False,
                input_file=str(input_path),
                error=f"不支持的文件格式: {suffix}",
            )

        safe_stem = _safe_output_stem(stem, mapping_dict)
        if safe_stem != stem:
            renamed_output = _unique_path(
                output_dir / f"{safe_stem}_cleaned{output_file.suffix}"
            )
            if output_file.exists():
                output_file.replace(renamed_output)
                output_file = renamed_output
            mapping_file = _unique_path(output_dir / f"{safe_stem}_mapping.json")

        mapping_file.write_text(
            json.dumps(mapping_dict, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        entity_count = len(mapping_dict)

        return ProcessResult(
            success=True,
            input_file=str(input_path),
            output_file=str(output_file),
            mapping_file=str(mapping_file),
            mapping_dict=mapping_dict,
            entity_count=entity_count,
            ocr_page_count=ocr_page_count,
        )

    except Exception as exc:
        return ProcessResult(
            success=False,
            input_file=str(input_path),
            error=str(exc),
        )


def batch_process(
    input_paths: list,
    output_dir: str | Path,
    custom_terms: list[str] | None = None,
) -> list:
    """批量处理多个文件，返回 list[ProcessResult]"""
    output_dir = Path(output_dir)
    return [
        process_document(p, output_dir, custom_terms)
        for p in input_paths
    ]


def restore_text(ai_text: str, mapping_dict: dict) -> str:
    """把AI分析文字里的占位符（如{{PARTY_甲方}}）还原为真实姓名。
    遍历mapping_dict，把每个key替换为value。"""
    result = ai_text
    for placeholder, original in mapping_dict.items():
        result = result.replace(placeholder, original)
    return result


def load_mapping(mapping_json_path: str | Path) -> dict:
    """从JSON文件加载mapping_dict"""
    mapping_json_path = Path(mapping_json_path)
    with open(mapping_json_path, encoding="utf-8") as f:
        return json.load(f)
