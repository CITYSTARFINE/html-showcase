"""需求收集、视觉方案校验与单文件组装；仅使用 Python 标准库。"""
from datetime import datetime
from pathlib import Path
import argparse
import hashlib
import html
import json
import re
import secrets
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = Path(__file__).resolve().parent
STYLES = [('极简', 'minimal'), ('科技', 'tech'), ('国风', 'chinese'),
          ('赛博朋克', 'cyberpunk'), ('扁平插画', 'illustration'), ('暗黑', 'dark'), ('学术', 'academic')]
PURPOSES = {'1': ('课堂展示', 'ketangzhanshi'), '2': ('产品介绍', 'chanpinjieshao'), '3': ('其他', 'qita')}
CHOICES = {
    'purpose': ['课堂展示', '产品介绍', '其他'],
    'style': [name for name, _ in STYLES] + ['自定义'],
    'palette_mode': ['沿用风格预设', '从推荐配色中选择', '我指定颜色'],
    'art_quality': ['精细清晰', '编辑级视觉', '最高美术完成度'],
    'tier': ['T1', 'T2', 'T3', '随便'],
    't3_confirmed': ['确认 T3', '重新选择等级'],
    'content_source': ['用户提供', '我搜索整理', '两者结合'],
    'asset_mode': ['程序化', 'AI 生图'],
    'ai_scope': ['背景', '贴图', '装饰', '背景、贴图、装饰'],
    'ai_authorized': ['明确授权内置 imagegen 制作所选最终素材', '改用程序化'],
    'acceptance_confirmed': ['确认验收标准', '提出修改意见'],
}
TITLES = {
    'purpose': '展示用途是什么？', 'style': '选择配色、字体与质感预设（不改变等级）。',
    'palette_mode': '页面颜色怎么选？风格与配色可分别选择，技术等级不变。',
    'palette_selection': '选择一套配色；背景、正文、强调色会用于方案和页面。',
    'color_bg': '背景色想用什么？可填颜色名或色值，例如宣纸色、白色、#f3eddf。',
    'color_text': '正文色想用什么？可填颜色名或色值，例如墨黑、藏青、#242521。',
    'color_accent': '强调色想用什么？可填颜色名或色值，例如朱砂、青色、#b53629。',
    'art_quality': '选择美术完成度（不会自动升级技术等级）。',
    'custom_adjectives': '自定义风格：填写三个形容词，用逗号分隔。',
    'custom_reference': '自定义风格：填写一个真实参考名称或链接，待核验。',
    'tier': '选择技术等级：T1 零依赖章节；T2 滚动叙事；T3 真实三维，固定版本 CDN 需联网。',
    't3_confirmed': '二次确认：是否授权以 T3 三维技术制作？选择等级本身不代表本次确认。',
    'content_source': '内容由谁提供？搜索授权不允许虚构事实。',
    'asset_mode': '最终素材如何制作？程序化 SVG/CSS（Canvas 仅 T3）；或使用内置 imagegen，无需 API key。',
    'ai_scope': 'AI 生图用于哪些最终素材？不会用于视觉方案效果论证。',
    'ai_authorized': '是否明确授权内置 imagegen 制作上述背景/贴图/装饰？只在视觉方案确认后的制作阶段执行。',
    'acceptance_confirmed': '确认验收：桌面和窄屏可读、配色符合批准方案、所有分档交互与降级有效；结论仅通过/小修/返工。',
    'acceptance_notes': '请记录要修改的验收要求；下一轮会重新请你确认。',
}
BOOL_FIELDS = {'t3_confirmed', 'ai_authorized', 'acceptance_confirmed'}
ALLOWED = set(TITLES) | {'academic_use'}



# 中文名称仅作输入便利；生成的 CSS 一律使用经过校验的十六进制值。
COLOR_NAMES = {'白色':'#ffffff','白':'#ffffff','纸白':'#f8f7f3','暖白':'#faf9f6',
               '宣纸色':'#f3eddf','米白':'#f3eddf','黑色':'#111214','黑':'#111214',
               '墨黑':'#242521','深蓝':'#071629','藏青':'#203f67','青色':'#46d9ef',
               '朱砂':'#b53629','红色':'#b53629','金色':'#d8bd89','香槟金':'#d8bd89',
               '浅灰':'#eeeeee','深灰':'#333333','绿色':'#246b4a','蓝色':'#245aa5'}
COLOR_FIELDS = {'color_bg':'--bg','color_text':'--text','color_accent':'--accent'}
PALETTE_NAMES = ('预设原色', '柔和强调', '浓郁强调')


def normalize_color(value):
    value = COLOR_NAMES.get(value.strip(), value.strip()).lower()
    if re.fullmatch(r'#[0-9a-f]{3}', value):
        value = '#' + ''.join(c * 2 for c in value[1:])
    if not re.fullmatch(r'#[0-9a-f]{6}', value):
        raise ValueError('请使用支持的中文颜色名或 #RGB/#RRGGBB 色值；不接受 CSS 表达式')
    return value


def blend(first, second, ratio):
    a, b = normalize_color(first), normalize_color(second)
    return '#' + ''.join(f'{round(int(a[i:i+2],16)*(1-ratio)+int(b[i:i+2],16)*ratio):02x}' for i in (1,3,5))


def luminance(color):
    values = [int(normalize_color(color)[i:i+2],16)/255 for i in (1,3,5)]
    linear = [v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in values]
    return sum(v*w for v,w in zip(linear,(.2126,.7152,.0722)))


def contrast(first, second):
    a, b = sorted((luminance(first),luminance(second)))
    return (b+.05)/(a+.05)


def preset_palette(answers):
    code = dict(STYLES).get(answers.get('style'), 'minimal')
    css = (ROOT/'styles'/'presets.css').read_text(encoding='utf-8')
    match = re.search(r'\[data-style="' + re.escape(code) + r'"\]\{([^}]+)\}', css)
    if not match:
        raise ValueError('找不到风格配色变量')
    values = dict(re.findall(r'(--[a-z-]+):([^;]+)',match[1]))
    return {key:normalize_color(values[key]) for key in ('--bg','--surface','--accent','--text','--muted')}


def recommended_palettes(answers):
    original = preset_palette(answers)
    soft = dict(original, **{'--accent':blend(original['--accent'], original['--bg'], .16)})
    strong = dict(original, **{'--accent':blend(original['--accent'], '#000000' if luminance(original['--bg'])>.5 else '#ffffff', .18)})
    return dict(zip(PALETTE_NAMES,(original,soft,strong)))


def palette_label(name, palette):
    return f"{name}｜背景 {palette['--bg']} · 正文 {palette['--text']} · 强调 {palette['--accent']}"


def resolve_palette(answers):
    palette = preset_palette(answers)
    mode = answers.get('palette_mode')
    if mode == '从推荐配色中选择':
        selection = answers.get('palette_selection')
        if selection not in PALETTE_NAMES:
            raise ValueError('尚未选定推荐配色')
        return recommended_palettes(answers)[selection]
    if mode == '我指定颜色':
        if any(k not in answers for k in COLOR_FIELDS):
            raise ValueError('指定配色需要背景色、正文色、强调色')
        for field, variable in COLOR_FIELDS.items():
            palette[variable] = normalize_color(answers[field])
        if contrast(palette['--bg'],palette['--text']) < 4.5:
            raise ValueError('正文与背景的对比度低于 4.5:1，请调整正文色或背景色')
        palette['--surface'] = palette['--bg']
        muted = blend(palette['--text'],palette['--bg'],.22)
        palette['--muted'] = muted if contrast(muted,palette['--bg'])>=4.5 else palette['--text']
    return palette


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def question(key, answers):
    title = TITLES[key]
    if key == 'acceptance_confirmed':
        if academic_use(answers):
            title += '\n学术验收：一句主线、每章贡献与过渡句、概念关系图示；陌生真人看完说不出主线则返工，未测只能小修。'
        title += '\n' + acceptance_text(answers.get('tier', 'T1'))
        if answers.get('acceptance_notes'):
            title += '\n追加要求：' + answers['acceptance_notes']
    if key == 'ai_authorized':
        title += '\n所选用途：' + answers.get('ai_scope', '')
    result = {'id': key, 'title': title}
    if key in CHOICES:
        result['options'] = CHOICES[key]
    if key == 'palette_selection':
        palettes = recommended_palettes(answers)
        result['options'] = [palette_label(name,palette) for name,palette in palettes.items()]
        result['swatches'] = [{'option':palette_label(name,palette),'colors':[palette[k] for k in ('--bg','--text','--accent')]} for name,palette in palettes.items()]
    if key in COLOR_FIELDS:
        result['color_input'] = True
        result['initial_color'] = preset_palette(answers)[COLOR_FIELDS[key]]
    return result


def academic_use(answers):
    return answers.get('academic_use') is True or answers.get('purpose') == '课堂展示' or answers.get('style') == '学术'


def acceptance_text(tier):
    common = '遮挡正文/关键按钮、横向溢出、正文对比度不足、配色与已确认方案不符、关键交互失效均返工；缺证据或非阻断细节列为小修。'
    extra = {
        'T1': '检查锚点、方向键、空格和 hover；零依赖，无滚动叙事/三维。',
        'T2': '检查滚动显现、视差、平滑导航、进度和每章 hero；最多一个 CDN 动画库。',
        'T3': '检查拾取、拖拽缩放、导览退出、飞行锁定、后台暂停和 WebGL/CDN/上下文丢失降级。目标 60fps：目标设备三机位各测 10 秒；任一平均低于 50fps 返工，50–59fps 小修，未测不得判通过。',
    }
    return common + extra[tier]


def pending(answers):
    """只返回下一轮问题；依赖顺序固定，每轮不超过三问。"""
    if 'purpose' not in answers:
        keys = ['purpose']
    elif 'style' not in answers:
        keys = ['style']
    elif answers['style'] == '自定义' and any(k not in answers for k in ('custom_adjectives', 'custom_reference')):
        keys = [k for k in ('custom_adjectives', 'custom_reference') if k not in answers]
    elif 'palette_mode' not in answers:
        keys = ['palette_mode']
    elif answers['palette_mode'] == '从推荐配色中选择' and 'palette_selection' not in answers:
        keys = ['palette_selection']
    elif answers['palette_mode'] == '我指定颜色' and any(k not in answers for k in COLOR_FIELDS):
        keys = [k for k in COLOR_FIELDS if k not in answers]
    elif 'art_quality' not in answers:
        keys = ['art_quality']
    elif 'tier' not in answers:
        keys = ['tier']
    elif answers['tier'] == 'T3' and answers.get('t3_confirmed') is not True:
        keys = ['t3_confirmed']
    elif 'content_source' not in answers:
        keys = ['content_source']
    elif 'asset_mode' not in answers:
        keys = ['asset_mode']
    elif answers['asset_mode'] == 'AI 生图' and 'ai_scope' not in answers:
        keys = ['ai_scope']
    elif answers['asset_mode'] == 'AI 生图' and answers.get('ai_authorized') is not True:
        keys = ['ai_authorized']
    elif answers.get('acceptance_confirmed') is not True:
        keys = ['acceptance_notes'] if answers.get('_acceptance_edit') else ['acceptance_confirmed']
    else:
        keys = []
    return [question(k, answers) for k in keys][:3]


def update(answers, values):
    """既有明确选择可预填；确认必须是真布尔值或明确的提交文本。"""
    if not isinstance(values, dict) or set(values) - ALLOWED:
        raise ValueError('答案必须是对象，且只包含已定义需求字段')
    values = dict(values)
    if any(k in values for k in COLOR_FIELDS) and 'palette_mode' not in values:
        if answers.get('palette_mode') in CHOICES['palette_mode']:
            try:
                prior = resolve_palette(answers)
                for field, variable in COLOR_FIELDS.items():
                    values.setdefault(field,prior[variable])
            except ValueError:
                pass
        values['palette_mode'] = '我指定颜色'
    elif 'palette_selection' in values and 'palette_mode' not in values:
        values['palette_mode'] = '从推荐配色中选择'
    result = dict(answers)
    for key in [k for k in TITLES if k != 'acceptance_confirmed'] + ['academic_use', 'acceptance_confirmed']:  # 最后记录验收确认。
        if key not in values:
            continue
        value = values[key]
        if key == 'academic_use':
            if type(value) is not bool:
                raise ValueError('academic_use 必须是真布尔值')
            normalized = value
        elif key in BOOL_FIELDS:
            if type(value) is bool:
                normalized = value
            elif isinstance(value, str) and value in CHOICES[key]:
                normalized = value == CHOICES[key][0]
            else:
                raise ValueError(f'{key} 必须为布尔值或明确确认选项，不能用字符串 true/false')
        else:
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f'{key} 不能为空')
            normalized = value.strip()
            if key == 'purpose' and normalized in ('论文答辩', '课程汇报', '学术展示'):
                result['academic_use'] = True
                normalized = '其他'
            if key == 'style':
                normalized = dict((code, name) for name, code in STYLES).get(normalized, normalized)
                if normalized == 'custom':
                    normalized = '自定义'
            if key in COLOR_FIELDS:
                normalized = normalize_color(normalized)
            if key == 'palette_selection':
                aliases = {palette_label(name,palette):name for name,palette in recommended_palettes(result).items()}
                normalized = aliases.get(normalized,normalized)
                if normalized not in PALETTE_NAMES:
                    raise ValueError('请选择列出的推荐配色')
            if key == 'tier':
                result.pop('_default_notice', None)
                normalized = normalized.upper()
                if normalized == '随便':
                    purpose = result.get('purpose')
                    if purpose not in ('课堂展示', '产品介绍'):
                        raise ValueError('其他用途没有默认等级；请明确选择 T1/T2/T3')
                    normalized = 'T1' if purpose == '课堂展示' else 'T2'
                    result['_default_notice'] = f'已明确采用默认：{purpose} → {normalized}；T3 永不默认。'
            if key in CHOICES and normalized not in CHOICES[key]:
                raise ValueError(f'{key} 不是有效选项')
            if key == 'custom_adjectives' and len([w for w in re.split(r'[,，、\s]+', normalized) if w]) != 3:
                raise ValueError('自定义风格需要恰好三个形容词')
        if result.get(key) != normalized:
            # 已批准的标准不能套用到修改后的需求。
            if key != 'acceptance_confirmed':
                result.pop('acceptance_confirmed', None)
            if key == 'palette_mode':
                for field in ('palette_selection', *COLOR_FIELDS):
                    result.pop(field, None)
            if key == 'tier':
                result.pop('t3_confirmed', None)
            if key in ('asset_mode', 'ai_scope'):
                result.pop('ai_authorized', None)
        result[key] = normalized
        if key == 't3_confirmed' and normalized is False:
            result.pop('tier', None)
            result.pop('t3_confirmed', None)
        if key == 'ai_authorized' and normalized is False:
            result['asset_mode'] = '程序化'
            result.pop('ai_scope', None)
            result.pop('ai_authorized', None)
        if key == 'acceptance_confirmed' and normalized is False:
            result['_acceptance_edit'] = True
        if key == 'acceptance_notes':
            result.pop('_acceptance_edit', None)
    if result.get('palette_mode') == '我指定颜色' and all(k in result for k in COLOR_FIELDS):
        resolve_palette(result)
    return result


def load(path):
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding='utf-8-sig'))
    return data


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)


def public_answers(answers):
    return {k: v for k, v in answers.items() if not k.startswith('_')}


def require_complete(answers):
    # 重新校验保存的状态，避免手改 JSON 产生无效等级或字符串授权。
    normalized = update({}, public_answers(answers))
    if pending(normalized):
        raise ValueError('intake 尚未完成：' + ', '.join(q['id'] for q in pending(normalized)))
    return normalized


def plan_digest(plan):
    return digest({k: v for k, v in plan.items() if k != 'approval'})


def nonempty(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(label + '不能为空')


def validate_plan(answers, plan, approved=True):
    """校验记录完整性；真实来源仍需 Codex 打开来源人工核验。"""
    answers = require_complete(answers)
    if plan.get('palette') != resolve_palette(answers):
        raise ValueError('视觉方案须记录与用户选择一致的具体配色色值；配色变化后重新确认')
    directions = plan.get('directions', [])
    if not isinstance(directions, list) or not 2 <= len(directions) <= 3:
        raise ValueError('先给用户 2–3 个方向，不允许直接提交最终方案')
    ids = set()
    for direction in directions:
        nonempty(direction.get('id'), '方向 id')
        if direction['id'] in ids:
            raise ValueError('方向 id 重复')
        ids.add(direction['id'])
        for field in ('name', 'description', 'key_frame_differences', 'suitable_for'):
            nonempty(direction.get(field), '方向 ' + field)
        references = direction.get('references', [])
        if not references:
            if direction.get('reference_status') != '暂无对标':
                raise ValueError('无真实参考必须明确标注“暂无对标”')
        else:
            for reference in references:
                if reference.get('kind') not in ('真实照片', '真实画作', '真实项目截图'):
                    raise ValueError('方案参考只能是真实照片、真实画作或真实项目截图；禁止 AI 效果图')
                for field in ('source', 'verification'):
                    nonempty(reference.get(field), '真实参考 ' + field)
    selection = plan.get('selection', {})
    if selection.get('user_selected') is not True or selection.get('direction_id') not in ids:
        raise ValueError('需要用户实际选定方向；预选、默认和超时不算选择')
    nonempty(selection.get('evidence'), '方向选择记录')
    screens = plan.get('screens', [])
    if not screens:
        raise ValueError('缺少逐屏构图草案')
    if len({screen.get('name') for screen in screens}) != len(screens):
        raise ValueError('逐屏名称不能重复')
    for screen in screens:
        for field in ('name', 'composition', 'foreground', 'midground', 'background'):
            nonempty(screen.get(field), '逐屏构图 ' + field)
    frames = plan.get('key_frames', [])
    if not 3 <= len(frames) <= 5:
        raise ValueError('关键画面必须为 3–5 个')
    for frame in frames:
        for field in ('name', 'effect'):
            nonempty(frame.get(field), '关键画面 ' + field)
    assets = plan.get('assets')
    if not isinstance(assets, list):
        raise ValueError('必须有素材计划，零素材可用空清单并说明理由')
    if not assets:
        nonempty(plan.get('no_assets_reason'), '零素材理由')
    for asset in assets:
        for field in ('name', 'producer', 'size', 'source'):
            nonempty(asset.get(field), '素材 ' + field)
        method = asset.get('method')
        if method not in ('SVG', 'CSS', 'Canvas', 'AI 生图', '用户提供', '授权真实图片'):
            raise ValueError('未知素材制作方式')
        if method == 'Canvas' and answers['tier'] != 'T3':
            raise ValueError('Canvas 动态纹理和粒子只用于 T3')
        if method == 'AI 生图':
            if answers.get('asset_mode') != 'AI 生图' or answers.get('ai_authorized') is not True:
                raise ValueError('AI 最终素材需要明确授权')
            scope = asset.get('scope')
            if scope not in ('背景', '贴图', '装饰') or scope not in answers.get('ai_scope', ''):
                raise ValueError('AI 素材用途超出授权')
    if academic_use(answers):
        academic = plan.get('academic', {})
        nonempty(academic.get('mainline'), '学术核心论点/逻辑主线')
        chapters = academic.get('chapters', [])
        if len(chapters) != len(screens) or {c.get('name') for c in chapters} != {s.get('name') for s in screens}:
            raise ValueError('学术章节贡献与过渡句必须覆盖每一屏')
        for chapter in chapters:
            for field in ('name', 'contribution', 'transition'):
                nonempty(chapter.get(field), '学术章节 ' + field)
        relationships = academic.get('relationships', [])
        if not relationships:
            raise ValueError('学术概念关系必须图示化，不能只堆文字')
        for relationship in relationships:
            for field in ('from', 'to', 'diagram', 'chapter', 'source'):
                nonempty(relationship.get(field), '学术关系图示 ' + field)
            if relationship.get('relation') not in ('因果', '对比', '递进', '总分', '并列'):
                raise ValueError('请明确学术概念关系类型')
            if relationship['chapter'] not in {s['name'] for s in screens}:
                raise ValueError('关系图示必须位于已规划章节')
    if answers['tier'] == 'T3':
        t3 = plan.get('t3', {})
        for field in ('camera_path', 'lighting_plan', 'postprocessing'):
            nonempty(t3.get(field), 'T3 视觉方案 ' + field)
    if approved:
        approval = plan.get('approval', {})
        if approval.get('confirmed') is not True:
            raise ValueError('完整视觉方案尚未得到用户明确确认')
        nonempty(approval.get('evidence'), '方案确认记录')
        if approval.get('intake_digest') != digest(public_answers(answers)) or approval.get('plan_digest') != plan_digest(plan):
            raise ValueError('方案或需求已变更，请重新确认；批准摘要不匹配')
    return {'intake_digest': digest(public_answers(answers)), 'plan_digest': plan_digest(plan)}


def build(answers, plan, output_root=None):
    validate_plan(answers, plan)
    answers = require_complete(answers)
    purpose = answers['purpose']
    slug = next(value[1] for value in PURPOSES.values() if value[0] == purpose)
    style = dict(STYLES).get(answers['style'], 'custom')
    custom = (answers['custom_adjectives'], answers['custom_reference']) if style == 'custom' else None
    return _assemble(purpose, slug, style, answers['tier'], custom, output_root, resolve_palette(answers))

def _assemble(purpose, slug, style, tier, custom=None, output_root=None, palette=None):
    """内部组装函数；仅由经过需求和视觉方案校验的 build 调用。"""
    if tier not in ('T1', 'T2', 'T3') or style not in {key for _, key in STYLES} | {'custom'}:
        raise ValueError('未知等级或风格')
    source = (ROOT / 'templates' / f'{tier.lower()}.html').read_text(encoding='utf-8')
    presets = (ROOT / 'styles' / 'presets.css').read_text(encoding='utf-8')
    source = source.replace('data-style="minimal"', f'data-style="{style}"', 1)
    extra = ''
    if custom:
        brief = html.escape(f'自定义方向：{custom[0]}；参考：{custom[1]}', quote=True).replace('--', '—')
        extra = f'\n<!-- {brief}；下面变量待按参考调整。 -->\n<style>[data-style="custom"]{{--bg:#faf9f6;--surface:#fff;--accent:#e35235;--text:#202328;--muted:#687078;--font-display:Georgia,"Songti SC",serif;--font-body:system-ui,"Microsoft YaHei",sans-serif}}</style>'
    if palette:
        declarations = ';'.join(key+':'+normalize_color(value) for key,value in palette.items())
        extra += '\n<!-- 用户选定的项目配色；不修改七套预设源文件。 -->\n<style>[data-style="'+style+'"]{'+declarations+'}</style>'
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



WIZARD = r'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>展示页需求向导</title><style>body{margin:0;background:#f5f4f0;color:#172d42;font:17px/1.7 system-ui,sans-serif}main{max-width:760px;margin:5vh auto;padding:30px}h1{font-size:30px}fieldset{border:0;padding:0;margin:24px 0}legend{font-weight:650;white-space:pre-line;margin-bottom:12px}label{display:block;padding:12px;border:1px solid #b5bec6;border-radius:10px;margin:8px 0;cursor:pointer;background:white}label:has(input:checked){outline:2px solid #176072}input[type=text]{box-sizing:border-box;width:100%;padding:12px;font:inherit}button{padding:12px 24px;border:0;border-radius:8px;background:#17475b;color:white;font:inherit;cursor:pointer}#error{color:#aa2828}small{display:block}</style><main><h1>HTML 展示页 · 需求向导</h1><p>一次确认一个阶段，保存后由 Codex 提供视觉方向供你选择。</p><p id="notice"></p><form id="form"><div id="questions"></div><button id="submit">提交本轮选择</button></form><p id="error" role="alert"></p><small id="status"></small></main><script>
const token=__TOKEN__;let round=[];
function el(tag,text){const n=document.createElement(tag);if(text)n.textContent=text;return n}
async function render(){const response=await fetch('/api/state');const data=await response.json();round=data.questions;document.body.dataset.stage=round[0]?.id||'complete';document.querySelector('#notice').textContent=data.notice||'';const box=document.querySelector('#questions');box.replaceChildren();document.querySelector('#submit').hidden=!round.length;
for(const q of round){const field=el('fieldset');field.append(el('legend',q.title));if(q.options){for(const option of q.options){const label=el('label');const input=el('input');input.type='radio';input.name=q.id;input.value=option;input.required=true;label.append(input,document.createTextNode(' '+option));const swatch=q.swatches?.find(s=>s.option===option);if(swatch){const colors=el('span');colors.style.cssText='display:flex;gap:7px;margin:8px 0 0 24px';for(const color of swatch.colors){const chip=el('span');chip.style.cssText='display:inline-block;width:30px;height:22px;border:1px solid #aab0b7;border-radius:3px';chip.style.backgroundColor=color;chip.title=color;chip.setAttribute('aria-label',color);colors.append(chip)}label.append(colors)}field.append(label)}}else{const input=el('input');input.type='text';input.name=q.id;input.required=true;field.append(input);if(q.color_input){const picker=el('input');picker.type='color';picker.value=q.initial_color;picker.setAttribute('aria-label','取色器：'+q.title);picker.style.cssText='width:64px;height:38px;margin-top:8px;cursor:pointer';picker.addEventListener('input',()=>{input.value=picker.value});field.append(picker)}}box.append(field)}
document.querySelector('#status').textContent=round.length?'未提交的选项不算确认。':'需求已保存。尚未生成项目：下一步先选 2–3 个视觉方向之一，再确认完整方案。';}
document.querySelector('#form').addEventListener('submit',async event=>{event.preventDefault();const answers=Object.fromEntries(new FormData(event.target));document.querySelector('#submit').disabled=true;try{const response=await fetch('/api/answer',{method:'POST',headers:{'Content-Type':'application/json','X-Intake-Token':token},body:JSON.stringify(answers)});const data=await response.json();if(!response.ok)throw Error(data.error);document.querySelector('#error').textContent='';await render()}catch(error){document.querySelector('#error').textContent=error.message}finally{document.querySelector('#submit').disabled=false}});render();</script></html>'''


def serve(state_path, answers, port=0, open_browser=True):
    token = secrets.token_urlsafe(32)
    state = {'answers': answers}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def respond(self, code, data, mime='application/json; charset=utf-8'):
            encoded = data.encode() if isinstance(data, str) else json.dumps(data, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header('Content-Type', mime)
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Length', str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def local_request(self):
            expected = f'127.0.0.1:{self.server.server_port}'
            return self.headers.get('Host') == expected and self.headers.get('Origin', f'http://{expected}') == f'http://{expected}'

        def do_GET(self):
            if not self.local_request():
                return self.respond(403, {'error': '仅允许本机访问'})
            if self.path == '/':
                return self.respond(200, WIZARD.replace('__TOKEN__', json.dumps(token)), 'text/html; charset=utf-8')
            if self.path == '/api/state':
                return self.respond(200, {'questions': pending(state['answers']), 'notice': state['answers'].get('_default_notice', ''), 'answers': public_answers(state['answers'])})
            self.respond(404, {'error': '没有此资源'})

        def do_POST(self):
            if not self.local_request() or self.headers.get('X-Intake-Token') != token:
                return self.respond(403, {'error': '请求来源或令牌无效'})
            if self.path != '/api/answer':
                return self.respond(404, {'error': '没有此资源'})
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 32768:
                    raise ValueError('请求长度无效')
                values = json.loads(self.rfile.read(length))
                expected = {q['id'] for q in pending(state['answers'])}
                if not expected or not isinstance(values, dict) or set(values) != expected:
                    raise ValueError('只允许提交当前轮问题的完整答案')
                state['answers'] = update(state['answers'], values)
                save(state_path, state['answers'])
                self.respond(200, {'saved': True})
            except (ValueError, TypeError) as error:
                self.respond(400, {'error': str(error)})

    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    url = f'http://127.0.0.1:{server.server_port}'
    print('本机按钮向导：' + url, flush=True)
    print('需求文件：' + str(state_path.resolve()) + '；关闭终端可停止向导。', flush=True)
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def cli(state_path, answers):
    while pending(answers):
        values = {}
        for q in pending(answers):
            print('\n' + q['title'])
            options = q.get('options', [])
            for index, option in enumerate(options, 1):
                print(f'{index}. {option}')
            value = input('请输入编号或答案：').strip()
            if value.isdigit() and 1 <= int(value) <= len(options):
                value = options[int(value) - 1]
            values[q['id']] = value
        try:
            answers = update(answers, values)
            save(state_path, answers)
            if answers.get('_default_notice'):
                print(answers['_default_notice'])
        except ValueError as error:
            print(error)
    print('需求已保存，尚未生成项目。请由 Codex 提供方向选项并完善视觉方案。')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', type=Path, default=Path('intake.json'))
    parser.add_argument('--known', type=Path, help='已明确的选择 JSON；不重复询问')
    parser.add_argument('--answers', type=Path, help='提交下一轮答案 JSON')
    parser.add_argument('--questions', action='store_true', help='输出下一轮问题 JSON，供 Codex 原生按钮显示')
    parser.add_argument('--cli', action='store_true', help='终端备用模式；不提供按钮')
    parser.add_argument('--web', action='store_true', help='本机按钮向导，默认模式')
    parser.add_argument('--no-open', action='store_true')
    parser.add_argument('--port', type=int, default=0)
    parser.add_argument('--plan', type=Path)
    parser.add_argument('--check-plan', action='store_true', help='检查方案结构并输出待确认摘要，不创建项目')
    parser.add_argument('--build', action='store_true', help='仅在明确批准的视觉方案下组装')
    parser.add_argument('--output-root', type=Path)
    args = parser.parse_args()
    if args.questions or args.check_plan:
        sys.stdout.reconfigure(encoding='utf-8')
    try:
        stored = load(args.state)
        answers = update({}, public_answers(stored))
        answers.update({k: v for k, v in stored.items() if k.startswith('_')})
        if args.known and not args.known.is_file():
            raise ValueError('--known 文件不存在')
        if args.answers and not args.answers.is_file():
            raise ValueError('--answers 文件不存在')
        if args.known:
            answers = update(answers, load(args.known))
        if args.answers:
            values = load(args.answers)
            if set(values) != {q['id'] for q in pending(answers)}:
                raise ValueError('--answers 只接受当前轮的完整答案；预填已有选择请用 --known')
            answers = update(answers, values)
        save(args.state, answers)
        if args.build or args.check_plan:
            if not args.plan:
                raise ValueError('需要 --plan visual-plan.json')
            plan = load(args.plan)
            hashes = validate_plan(answers, plan, approved=args.build)
            if args.build:
                print(str(build(answers, plan, args.output_root).resolve() / 'index.html'))
            else:
                print(json.dumps(hashes, ensure_ascii=False, indent=2))
        elif args.questions:
            questions = pending(answers)
            print(json.dumps({'questions': questions, 'tool_questions': [{k: v for k, v in q.items() if k in ('title','options')} for q in questions], 'complete': not questions, 'palette': resolve_palette(answers) if not questions else None, 'notice': answers.get('_default_notice', '')}, ensure_ascii=False, indent=2))
        elif args.cli:
            cli(args.state, answers)
        else:
            serve(args.state, answers, args.port, not args.no_open)
    except (ValueError, TypeError, KeyError, AttributeError, OSError) as error:
        print('未生成：' + str(error), file=sys.stderr)
        return 1
    except (EOFError, KeyboardInterrupt):
        print('已取消；已保存选择可继续，未继续生成。')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
