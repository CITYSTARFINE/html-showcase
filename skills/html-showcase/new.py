"""交互生成无需构建的单文件 HTML；仅使用 Python 标准库。"""
from datetime import datetime
from pathlib import Path
import html
import re

ROOT = Path(__file__).resolve().parent
STYLES = [('极简', 'minimal'), ('科技', 'tech'), ('国风', 'chinese'),
          ('赛博朋克', 'cyberpunk'), ('扁平插画', 'illustration'), ('暗黑', 'dark'), ('学术', 'academic')]
PURPOSES = {'1': ('课堂展示', 'ketangzhanshi'), '2': ('产品介绍', 'chanpinjieshao'), '3': ('其他', 'qita')}


def choose(prompt, choices):
    while True:
        answer = input(prompt).strip()
        if answer in choices:
            return choices[answer]
        print('请输入列出的编号或名称。')


def ask():
    purposes = {**PURPOSES, **{value[0]: value for value in PURPOSES.values()}}
    purpose, slug = choose('用途：1 课堂展示 / 2 产品介绍 / 3 其他：', purposes)
    custom = None
    choices = {str(i): key for i, (_, key) in enumerate(STYLES, 1)}
    choices.update({name: key for name, key in STYLES})
    choices.update({'8': 'custom', '自定义': 'custom', '随便': 'minimal'})
    style = choose('风格：' + ' / '.join(f'{i} {name}' for i, (name, _) in enumerate(STYLES, 1)) + ' / 8 自定义：', choices)
    if style == 'custom':
        while True:
            adjectives = input('自定义：输入三个形容词，用逗号或空格分隔：').strip()
            words = [word for word in re.split(r'[,，、\s]+', adjectives) if word]
            if len(words) == 3:
                break
            print('请恰好输入三个形容词。')
        reference = ''
        while not reference:
            reference = input('输入一个参考（名称、链接或描述）：').strip()
        custom = ('、'.join(words), reference)
        print('已记录自定义方向；先以极简变量生成占位，请根据参考调整七个核心变量。不会自动访问或复制参考。')
    while True:
        tier = input('等级：T1 轻量 / T2 精美 / T3 极致（或“随便”）：').strip().upper()
        if tier == '随便':
            if purpose == '其他':
                print('其他用途没有默认等级，请明确选择 T1、T2 或 T3。')
                continue
            tier = 'T1' if purpose == '课堂展示' else 'T2'
            print(f'已采用默认：{purpose} → {tier}。')
        if tier not in ('T1', 'T2', 'T3'):
            print('请选择 T1、T2 或 T3。')
            continue
        if tier == 'T3' and input('T3 使用固定版本 three.js CDN，需要联网。动工前请亲口确认，输入“确认 T3”：').strip().upper() != '确认 T3':
            print('未确认 T3，尚未生成；请重新选择等级。')
            continue
        return purpose, slug, style, tier, custom


def build(purpose, slug, style, tier, custom=None, output_root=None):
    """内部组装函数；交互入口负责取得 T3 授权。"""
    if tier not in ('T1', 'T2', 'T3') or style not in {key for _, key in STYLES} | {'custom'}:
        raise ValueError('未知等级或风格')
    source = (ROOT / 'templates' / f'{tier.lower()}.html').read_text(encoding='utf-8')
    presets = (ROOT / 'styles' / 'presets.css').read_text(encoding='utf-8')
    source = source.replace('data-style="minimal"', f'data-style="{style}"', 1)
    extra = ''
    if custom:
        brief = html.escape(f'自定义方向：{custom[0]}；参考：{custom[1]}', quote=True).replace('--', '—')
        extra = f'\n<!-- {brief}；下面变量待按参考调整。 -->\n<style>[data-style="custom"]{{--bg:#faf9f6;--surface:#fff;--accent:#e35235;--text:#202328;--muted:#687078;--font-display:Georgia,"Songti SC",serif;--font-body:system-ui,"Microsoft YaHei",sans-serif}}</style>'
    source = source.replace('<link rel="stylesheet" href="../styles/presets.css">', f'<style>\n{presets}\n</style>{extra}')
    for name in ('nav.js', 't3-base.js'):
        marker = f'<script src="../js/{name}"></script>'
        if marker in source:
            js = (ROOT / 'js' / name).read_text(encoding='utf-8')
            source = source.replace(marker, f'<script>\n{js}\n</script>')
    parent = Path(output_root) if output_root is not None else Path.cwd()
    stem = f'{slug}-{datetime.now().astimezone().strftime("%Y%m%d")}'
    directory = parent / stem
    suffix = 2
    while True:
        try:
            directory.mkdir(parents=True, exist_ok=False)
            break
        except FileExistsError:
            directory = parent / f'{stem}-{suffix}'
            suffix += 1
    (directory / 'index.html').write_text(source, encoding='utf-8')
    return directory


def main():
    try:
        purpose, slug, style, tier, custom = ask()
        directory = build(purpose, slug, style, tier, custom)
        print(f'已生成：{directory.resolve() / "index.html"}')
        print(f'用途：{purpose}；等级：{tier}。请先补齐真实材料，再截图验收。')
        if tier == 'T3':
            print('three.js 锁定 0.170.0；CDN 或 WebGL 不可用时显示静态摘要。')
    except (EOFError, KeyboardInterrupt):
        print('\n已取消，未继续生成。')


if __name__ == '__main__':
    main()
