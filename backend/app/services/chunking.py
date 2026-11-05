"""Markdown 文档切分。

设计要点（详见 docs/chunking.md）：
1. 先按标题层级切"节"，保留章节路径，让每个块自带上下文；
2. 节内按空行分段，段落是天然的语义边界，比定长窗口更少切断语义；
3. 段落超长才退化为定长切分；相邻块保留 overlap，避免答案跨块时被截断；
4. 用于向量化的文本（embed_text）在正文前拼接文档名/类别/章节路径，
   检索时能利用"文档级上下文"，但引用展示仍用原始正文（text）。
"""
from dataclasses import dataclass
from pathlib import Path

from .. import config

# 文档元数据键名（中文）到内部字段的映射
_META_KEYS = {
    "文档名": "title",
    "文档编号": "doc_no",
    "类别": "category",
    "版本": "version",
    "日期": "date",
}


@dataclass
class DocChunk:
    """一个检索单元：正文 + 元数据 + 向量化文本。"""

    doc_id: str
    title: str
    category: str
    version: str
    date: str
    doc_no: str
    file: str
    heading_path: str
    chunk_index: int
    text: str          # 原文片段，用于引用展示
    embed_text: str    # 拼上文档上下文后的文本，用于向量化

    def metadata(self) -> dict:
        """Chroma 的 metadata 只接受 str/int/float/bool。"""
        return {
            "doc_id": self.doc_id,
            "doc_title": self.title,
            "category": self.category,
            "version": self.version,
            "date": self.date,
            "doc_no": self.doc_no,
            "file": self.file,
            "heading_path": self.heading_path,
            "chunk_index": self.chunk_index,
        }


def parse_front_matter(raw: str) -> tuple[dict, str]:
    """解析文首 `--- ... ---` 元数据块，返回（元数据字典, 正文）。"""
    lines = raw.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, raw

    meta: dict[str, str] = {}
    end = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end = i
            break
        if "：" in line or ":" in line:
            # 同时兼容中英文冒号；中文键名统一映射为内部英文字段
            sep = "：" if "：" in line else ":"
            key, value = line.split(sep, 1)
            key = key.strip()
            meta[_META_KEYS.get(key, key)] = value.strip()
    if end is None:  # 没有闭合的 ---，按无元数据处理
        return {}, raw
    return meta, "\n".join(lines[end + 1:]).strip()


def _split_by_headings(body: str) -> list[tuple[str, str]]:
    """按 Markdown 标题切节，返回 [(章节路径, 正文), ...]。

    H1 不进入路径（文档名已由元数据提供），H2/H3/H4 逐级拼成如
    "三、温度异常排查 > 3.2 加热圈检查" 的路径。
    """
    sections: list[tuple[str, str]] = []
    heading_stack: list[tuple[int, str]] = []  # (级别, 标题文本)
    buffer: list[str] = []

    def flush() -> None:
        text = "\n".join(buffer).strip()
        if text:
            path = " > ".join(h for _, h in heading_stack)
            sections.append((path, text))
        buffer.clear()

    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            level = len(stripped) - len(stripped.lstrip("#"))
            title = stripped[level:].strip()
            if level == 1:
                # 文档一级标题不进章节路径；正文仍保留在 buffer 中
                buffer.append(line)
                continue
            flush()
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            heading_stack.append((level, title))
        else:
            buffer.append(line)
    flush()
    return sections


def _split_long_paragraph(paragraph: str, size: int, overlap: int) -> list[str]:
    """单段超过 size 时按字符窗口切分并保留重叠。"""
    pieces = []
    start = 0
    step = max(1, size - overlap)
    while start < len(paragraph):
        pieces.append(paragraph[start:start + size])
        if start + size >= len(paragraph):
            break
        start += step
    return pieces


def _chunk_paragraphs(text: str, size: int, overlap: int) -> list[str]:
    """段落优先的分块：尽量不切断段落，块间保留 overlap 字符。"""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        # 超长段落（如大表格）：独立按窗口切分，不与前后段拼接
        if len(para) > size:
            if current.strip():
                chunks.append(current.strip())
                current = ""
            chunks.extend(piece.strip() for piece in _split_long_paragraph(para, size, overlap))
            continue

        if not current:
            current = para
        elif len(current) + 2 + len(para) <= size:
            current = current + "\n\n" + para
        else:
            chunks.append(current.strip())
            # 新块用上一块的尾部 overlap 开头，保证跨块语义衔接；
            # 后面一定紧跟真实段落，不会产生"只有重叠尾巴"的空壳块
            tail = current[-overlap:] if overlap > 0 else ""
            current = f"{tail}\n\n{para}" if tail else para

    if current.strip():
        chunks.append(current.strip())
    return chunks


def chunk_document(raw: str, file_name: str) -> list[DocChunk]:
    """把一份 Markdown 文档切成若干 DocChunk。"""
    meta, body = parse_front_matter(raw)
    title = meta.get("title") or Path(file_name).stem
    doc_no = meta.get("doc_no", "")
    doc_id = doc_no or Path(file_name).stem
    category = meta.get("category", "未分类")
    version = meta.get("version", "")
    date = meta.get("date", "")

    chunks: list[DocChunk] = []
    index = 0
    for heading_path, section_text in _split_by_headings(body):
        for piece in _chunk_paragraphs(section_text, size=config.CHUNK_SIZE, overlap=config.CHUNK_OVERLAP):
            if heading_path:
                embed_text = f"{title}｜{category}｜{heading_path}\n{piece}"
            else:
                embed_text = f"{title}｜{category}\n{piece}"
            chunks.append(
                DocChunk(
                    doc_id=doc_id,
                    title=title,
                    category=category,
                    version=version,
                    date=date,
                    doc_no=doc_no,
                    file=file_name,
                    heading_path=heading_path,
                    chunk_index=index,
                    text=piece,
                    embed_text=embed_text,
                )
            )
            index += 1
    return chunks
