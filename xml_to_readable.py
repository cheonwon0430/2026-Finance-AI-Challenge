"""
DART 감사보고서 document.xml을 사람이 읽기 좋은 순수 텍스트(.txt)로 변환.
원본 XML이 이스케이프 안 된 태그(예: <당기말>) 때문에 깨져있어도
lxml recover 파서로 넘어가서 끝까지 처리한다.

사용법:
    python xml_to_readable.py 트래블월렛_doc/20260331000341_00760.xml
    -> 트래블월렛_doc/20260331000341_00760.txt 생성

한번에 다 변환:
    python xml_to_readable.py --all
"""
import sys
from pathlib import Path
from lxml import etree as ET

_PARSER = ET.XMLParser(recover=True)

TITLE_TAGS = {"TITLE", "COVER-TITLE"}
ROW_END_TAGS = {"TR", "P", "PGBRK"}


def convert(xml_path: Path) -> Path:
    text = xml_path.read_text(encoding="utf-8")
    root = ET.fromstring(text.encode("utf-8"), parser=_PARSER)

    lines: list[str] = []
    buf: list[str] = []

    def flush():
        if buf:
            lines.append(" ".join(buf))
            buf.clear()

    for elem in root.iter():
        tag = elem.tag
        if tag in TITLE_TAGS:
            flush()
            title_text = "".join(elem.itertext()).strip()
            if title_text:
                lines.append("")
                lines.append(f"===== {title_text} =====")
            continue
        if len(elem) == 0:  # 리프 노드만 (중복 방지)
            t = (elem.text or "").strip()
            if t:
                buf.append(t)
        if tag in ROW_END_TAGS:
            flush()

    flush()

    out_path = xml_path.with_suffix(".txt")
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--all":
        base = Path(__file__).parent
        for xml_file in base.glob("*_doc/*.xml"):
            out = convert(xml_file)
            print(f"변환 완료: {out}")
    else:
        if len(sys.argv) < 2:
            print("사용법: python xml_to_readable.py <xml파일 경로>  또는  --all")
            sys.exit(1)
        out = convert(Path(sys.argv[1]))
        print(f"변환 완료: {out}")
