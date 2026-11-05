// Markdown 渲染：marked 解析 + DOMPurify 消毒，再把 [1] 变成可点击引用
import DOMPurify from 'dompurify'
import { marked } from 'marked'

marked.setOptions({ gfm: true, breaks: true })

export function renderMarkdown(text: string): string {
  const raw = marked.parse(text || '', { async: false }) as string
  const clean = DOMPurify.sanitize(raw, {
    ADD_ATTR: ['target'],
  })
  return clean.replace(
    /\[(\d{1,2})\]/g,
    '<sup class="cite" data-cite="$1" title="查看第 $1 条依据">[$1]</sup>',
  )
}
