"""
Apply Typora Orange Heart theme CSS to Zotero note.
"""

import asyncio
from zotero_mcp.services import get_data_service

# Typora Orange Heart Theme CSS (完整370行)
TYPORA_CSS = """
/* 全局属性 */
#write {
  max-width: 860px;
  font-size: 1rem;
  color: black;
  padding: 0 10px;
  line-height: 1.6;
  word-spacing: 0px;
  letter-spacing: 0px;
  word-break: break-word;
  word-wrap: break-word;
  text-align: left;
  font-family: Optima-Regular, Optima, PingFangSC-light, PingFangTC-light, 'PingFang SC', Cambria, Cochin, Georgia, Times, 'Times New Roman', serif;
}

/*段落*/
#write + p, 
#write blockquote p {
  font-size: 1rem;
  padding-top: .5rem;
  padding-bottom: .5rem;
  margin: 0;
  line-height: 1.5rem;
  color: black;
}
#write div[mdtype=toc] {
  font-size: 1rem;
}

/*标题*/
#write h1,
#write h2,
#write h3,
#write h4,
#write h5,
#write h6 {
  margin: 1.2em 0 1em;
  padding: 0px;
  font-weight: bold;
  color: black;
}
#write h1 {
  font-size: 1.5rem;
}
#write h2 {
  font-size: 1.3rem;
  border-bottom: 2px solid rgb(239, 112, 96);
}
@media print {
  /* 为解决和 border-bottom 之间的 1px 空白 */
  #write h2 *  {
    margin-bottom:-1px;   /* 把背景区域往下拖 1 px */
  }
}

#write h2 a,
#write h2 span {
 font-weight: bold;
 background: rgb(239, 112, 96);
 color: #ffffff;
 padding-top: 3px;
 padding-bottom: 1px;
 border-bottom: none; /* html 结构下 a 标签的 border 会绘制出来  */
}
#write h2 > a,
#write h2 > span {
display: inline-block;
  word-spacing: 0;  /* 把空格宽度压成 0（负值可根据需要微调） */
}
@media print {
  /* 为解决和 相邻元素 之间的 1px 空白 */
  #write h2 > * + * {
    margin-left: -1px;   /* 把背景区域往左拖 1 px */
  }
  #write h2 > *:nth-child(2) { 
    margin-left: 0; /* pdf 打印前面多了一个元素，所以这个元素需要回位  */
  }
}

#write h2 > *:first-child {
padding-left: 10px;
border-top-left-radius: 3px;
}
@media print {
  #write h2 > *:nth-child(2) { 
    padding-left: 10px;
    border-top-left-radius: 3px;
  }
}

#write h2 > *:last-child {
  margin-right: 3px; 
  padding-right: 10px;
  border-top-right-radius: 3px;
}
#write h2:after {
display: inline-block;
content: "";
vertical-align: bottom;
border-bottom: 1.25rem solid #efebe9;
border-right: 1.25rem solid transparent;
}

#write h3 {
  font-size: 1.3rem;
}
#write h4 {
  font-size: 1.2rem;
}
#write h5 {
  font-size: 1.1rem;
}
#write h6 {
  font-size: 1rem;
}

/*列表*/
#write ul,
#write ol {
  margin-top: 8px;
  margin-bottom: 8px;
  padding-left: 25px;
  color: black;
}
#write ul {
  list-style-type: disc;
}
#write ul ul {
  list-style-type: square;
}
#write ol {
  list-style-type: decimal;
}
#write li section {
  margin-top: 5px;
  margin-bottom: 5px;
  line-height: 1.7rem;
  text-align: left;
  color: rgb(1,1,1);
  font-weight: 500;
}

/*引用*/
#write blockquote {
  display: block;
  font-size: .9em;
  overflow: auto;
  border-left: 3px solid rgb(239, 112, 96);
  color: #6a737d;
  padding: 10px 10px 10px 20px;
  margin-bottom: 20px;
  margin-top: 20px;
  background: #fff9f9;
}

/*链接*/
#write a {
  text-decoration: none;
  word-wrap: break-word;
  font-weight: bold;
  color: rgb(239, 112, 96);
  border-bottom: 1px solid rgb(239, 112, 96);
}

/*行内代码*/
#write p code,
#write li code {
  font-size: .9rem;
  word-wrap: break-word;
  padding: 2px 4px;
  border-radius: 4px;
  margin: 0 2px;
  color:  rgb(239, 112, 96);
  background-color: rgba(27,31,35,.05);
  font-family: Operator Mono, Consolas, Monaco, Menlo, monospace;
  word-break: break-all;
}

/*图片*/
#write img {
  display: block;
  margin: 0 auto;
  max-width: 100%;
}

#write span img {
  display: inline-block;
  border-right: 0px;
  border-left: 0px;
}

/*表格*/
#write table {
  display: table;
  text-align: left;
}
#write tbody {
  border: 0;
}
#write table tr {
  border: 0;
  border-top: 1px solid #ccc;
  background-color: white;
}
#write table tr:nth-child(2n) {
  background-color: #F8F8F8;
}
#write table tr th,
#write table tr td {
  font-size: 1rem;
  border: 1px solid #ccc;
  padding: 5px 10px;
  text-align: left;
}
#write table tr th {
  font-weight: bold;
  background-color: #f0f0f0;
}

/* 脚注上标 */
#write .md-footnote {
font-weight: bold;
color: rgb(239, 112, 96);
}
#write .md-footnote > .md-text:before {
content: '['
}
#write .md-footnote > .md-text:after {
content: ']'
}

/* 脚注定义 */
#write .md-def-name {
  padding-right: 1.8ch;
}
#write .md-def-name:before {
  content: '[';
  color: #000;
}

/* 代码块主题 */
.md-fences:before {
  content: ' ';
  display: block;
  width: 100%;
  background-color: #282c34;
  margin-bottom: -7px;
  border-radius: 5px;
}

/* CodeMirror (语法高亮) */
.cm-s-inner.CodeMirror {
  padding: .5rem;
  background-color: #292d3e;
  color: #a6accd;
  font-family: Consolas;
  border-radius: 4px;
}
.cm-s-inner .cm-keyword { color: #c792ea !important; }
.cm-s-inner .cm-operator { color: #89ddff !important; }
.cm-s-inner .cm-builtin { color: #ffcb6b !important; }
.cm-s-inner .cm-number { color: #ff5370 !important; }
.cm-s-inner .cm-string { color: #c3e88d !important; }
.cm-s-inner .cm-comment { color: #676e95 !important; }
.cm-s-inner .cm-variable { color: #f07178 !important; }
.cm-s-inner .cm-tag { color: #ff5370 !important; }

.CodeMirror div.CodeMirror-cursor {
  border-left: 1px solid rgb(239, 112, 96);
}
"""


async def apply_css_and_update():
    """Apply Typora Orange Heart CSS to the AI analysis note."""
    service = get_data_service()
    note_key = "KEHRHZZE"

    print(f"📖 获取note: {note_key}")
    # Get full note object (with version for optimistic locking)
    note = await service.get_item(note_key)

    original_html = note["data"]["note"]
    version = note["version"]

    print(f"✅ Note获取成功")
    print(f"   Version: {version}")
    print(f"   Original length: {len(original_html)} chars")

    # Create styled HTML
    styled_html = f"""<style>
{TYPORA_CSS}
</style>
<div id="write">
{original_html}
</div>"""

    print(f"\n🎨 应用Typora Orange Heart主题")
    print(f"   Styled length: {len(styled_html)} chars")

    # Update note content
    note["data"]["note"] = styled_html

    print(f"\n📤 更新note到Zotero...")
    try:
        result = await service.update_item(note)
        print(f"✅ 更新成功！")
        print(f"   Result: {result}")

        # Verify update
        print(f"\n🔍 验证更新...")
        updated_note = await service.get_item(note_key)
        updated_content = updated_note["data"]["note"]

        checks = [
            ("<style>" in updated_content, "CSS style tag present"),
            ('id="write"' in updated_content, "Write container present"),
            (
                "rgb(239, 112, 96)" in updated_content or "#EF7060" in updated_content,
                "Orange Heart color present",
            ),
            (len(updated_content) > len(original_html), "Content size increased"),
        ]

        all_pass = True
        for passed, desc in checks:
            status = "✅" if passed else "❌"
            print(f"   {status} {desc}")
            all_pass = all_pass and passed

        if all_pass:
            print(f"\n🎉 所有验证通过！")
            print(f"\n📌 请在Zotero桌面客户端中打开note查看效果：")
            print(f"   Item Key: 7INN7H7H")
            print(f"   Note Key: {note_key}")
        else:
            print(f"\n⚠️ 部分验证未通过，请检查")

        return True

    except Exception as e:
        print(f"❌ 更新失败: {str(e)}")
        return False


if __name__ == "__main__":
    success = asyncio.run(apply_css_and_update())
    exit(0 if success else 1)
