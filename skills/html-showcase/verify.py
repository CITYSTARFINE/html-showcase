"""验证单文件组装、默认等级与 T3 确认；测试产物放在临时目录。"""
import importlib.util
from pathlib import Path
import tempfile
from unittest.mock import patch
from html.parser import HTMLParser

spec = importlib.util.spec_from_file_location('generator', Path(__file__).with_name('new.py'))
generator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generator)


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.external = []
        self.chapters = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'data-chapter' in attrs:
            self.chapters += 1
        if tag in ('script', 'link') and ('src' in attrs or 'href' in attrs):
            self.external.append(attrs.get('src', attrs.get('href')))


# 临时产物限制在脚手架目录内，避免受系统临时目录权限影响。
with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent, prefix='.verify-') as temporary:
    for tier in ('T1', 'T2', 'T3'):
        for _, style in generator.STYLES:
            directory = generator.build('课堂展示', 'ketangzhanshi', style, tier, output_root=temporary)
            source = (directory / 'index.html').read_text(encoding='utf-8')
            page = Page()
            page.feed(source)
            assert page.chapters == 3 and not page.external
            assert '../js/' not in source and '../styles/' not in source
            assert ('three@0.170.0' in source) == (tier == 'T3')
            assert 'latest' not in source
            assert len(list(directory.iterdir())) == 1
    directory = generator.build('其他', 'qita', 'custom', 'T1', ('安静、清晰、温暖', '</script><!--参考-->'), temporary)
    assert '&lt;/script&gt;' in (directory / 'index.html').read_text(encoding='utf-8')

for answers, expected in [(['1', '1', '随便'], 'T1'), (['2', '2', '随便'], 'T2'),
                          (['3', '3', '随便', 'T1'], 'T1'),
                          (['1', '1', 'T3', '不确认', 'T1'], 'T1'),
                          (['2', '2', 'T3', '确认 T3'], 'T3'),
                          (['3', '8', '清晰 温暖 安静', '纸质目录', 'T2'], 'T2')]:
    with patch('builtins.input', side_effect=answers):
        assert generator.ask()[3] == expected
print('通过：21 个预设等级组合、单文件资源、自定义转义、默认等级和 T3 确认。')
