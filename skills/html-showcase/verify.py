"""需求、授权、视觉方案门槛与单文件组装回归测试（无需第三方库）。"""
import copy
import importlib.util
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('showcase_new', ROOT / 'new.py')
new = importlib.util.module_from_spec(spec)
spec.loader.exec_module(new)


def complete(tier='T1', style='学术', ai=False):
    answers = {'purpose': '课堂展示', 'style': style, 'art_quality': '最高美术完成度',
               'tier': tier, 'content_source': '我搜索整理', 'asset_mode': 'AI 生图' if ai else '程序化'}
    if tier == 'T3':
        answers['t3_confirmed'] = True
    if style == '自定义':
        answers.update(custom_adjectives='安静、典雅、明亮', custom_reference='真实参考待核验')
    if ai:
        answers.update(ai_scope='背景', ai_authorized=True)
    answers['acceptance_confirmed'] = True
    return new.update({}, answers)


def plan_for(answers):
    plan = {
        'directions': [{'id': code, 'name': name, 'description': '前景留白、中景正文、背景纸白',
                        'key_frame_differences': '强调图解' if code == 'a' else '强调文本',
                        'suitable_for': '课堂展示', 'references': [], 'reference_status': '暂无对标'}
                       for code, name in [('a', '图解方向'), ('b', '文本方向')]],
        'selection': {'direction_id': 'a', 'user_selected': True, 'evidence': '测试夹具：模拟用户选择，不是真实授权'},
        'screens': [{'name': f'第{i}屏', 'composition': '前景留白、中景正文、背景纸白；窄屏纵向排列',
                     'foreground': '留白', 'midground': '正文', 'background': '纸白'} for i in range(1, 4)],
        'key_frames': [{'name': f'画面{i}', 'effect': '清晰正文与克制配色'} for i in range(1, 4)],
        'assets': [{'name': '分隔线', 'producer': 'Codex', 'method': 'CSS', 'size': '1px×100%', 'source': '原创程序化'}],
    }
    if new.academic_use(answers):
        plan['academic'] = {'mainline': '测试主线：概念到证据再到结论',
                            'chapters': [{'name': screen['name'], 'contribution': '推进主线', 'transition': '承接前章并给出本章问题与原因'} for screen in plan['screens']],
                            'relationships': [{'from': '问题', 'to': '证据', 'relation': '递进', 'diagram': '步骤流程图', 'chapter': '第1屏', 'source': '测试夹具'}]}
    if answers['tier'] == 'T3':
        plan['t3'] = {'camera_path': '测试：三章路点，1.5秒飞行，飞行锁定', 'lighting_plan': '半球、主方向、两 rim 与雾', 'postprocessing': '无后处理'}
    approve(answers, plan)
    return plan


def approve(answers, plan):
    plan['approval'] = {'confirmed': True, 'evidence': '测试夹具：模拟方案确认',
                        'intake_digest': new.digest(new.public_answers(answers)), 'plan_digest': new.plan_digest(plan)}


class IntakeTests(unittest.TestCase):
    def test_sequence_and_three_question_limit(self):
        answers = {}
        submitted = {'purpose': '课堂展示', 'style': '学术', 'art_quality': '编辑级视觉', 'tier': 'T1',
                     'content_source': '我搜索整理', 'asset_mode': '程序化', 'acceptance_confirmed': '确认验收标准'}
        seen = []
        while new.pending(answers):
            questions = new.pending(answers)
            self.assertLessEqual(len(questions), 3)
            seen.extend(q['id'] for q in questions)
            answers = new.update(answers, {q['id']: submitted[q['id']] for q in questions})
        self.assertEqual(seen, list(submitted))
        new.require_complete(answers)

    def test_known_choices_are_skipped(self):
        answers = new.update({}, {'purpose': '课堂展示', 'style': '学术', 'tier': 'T1', 'content_source': '我搜索整理'})
        self.assertEqual([q['id'] for q in new.pending(answers)], ['art_quality'])

    def test_defaults_and_other_no_default(self):
        for purpose, tier in [('课堂展示', 'T1'), ('产品介绍', 'T2')]:
            answers = new.update({}, {'purpose': purpose, 'tier': '随便'})
            self.assertEqual(answers['tier'], tier)
            self.assertIn('已明确采用默认', answers['_default_notice'])
        with self.assertRaises(ValueError):
            new.update({}, {'purpose': '其他', 'tier': '随便'})

    def test_t3_requires_separate_confirmation_and_decline(self):
        answers = complete('T3')
        answers.pop('t3_confirmed')
        self.assertEqual(new.pending(answers)[0]['id'], 't3_confirmed')
        with self.assertRaises(ValueError):
            new.require_complete(answers)
        declined = new.update(answers, {'t3_confirmed': '重新选择等级'})
        self.assertNotIn('tier', declined)
        accepted = new.update(answers, {'t3_confirmed': '确认 T3'})
        self.assertTrue(accepted['t3_confirmed'])
        self.assertEqual(new.pending(accepted)[0]['id'], 'acceptance_confirmed')

    def test_ai_scope_authorization_and_decline(self):
        answers = complete(ai=True)
        answers.pop('ai_authorized')
        self.assertEqual(new.pending(answers)[0]['id'], 'ai_authorized')
        declined = new.update(answers, {'ai_authorized': '改用程序化'})
        self.assertEqual(declined['asset_mode'], '程序化')
        self.assertNotIn('ai_scope', declined)
        for value in ('true', 'false', 1, None):
            with self.assertRaises(ValueError):
                new.update(answers, {'ai_authorized': value})

    def test_revisions_invalidate_acceptance(self):
        answers = complete('T3', ai=True)
        changed = new.update(answers, {'tier': 'T2'})
        self.assertNotIn('t3_confirmed', changed)
        self.assertNotIn('acceptance_confirmed', changed)
        changed = new.update(answers, {'ai_scope': '贴图'})
        self.assertNotIn('ai_authorized', changed)
        self.assertNotIn('acceptance_confirmed', changed)

    def test_acceptance_amendment_and_reconfirmation(self):
        answers = new.update(complete(), {'acceptance_confirmed': '提出修改意见'})
        self.assertEqual(new.pending(answers)[0]['id'], 'acceptance_notes')
        answers = new.update(answers, {'acceptance_notes': '窄屏使用 360px 宽'})
        self.assertEqual(new.pending(answers)[0]['id'], 'acceptance_confirmed')
        answers = new.update(answers, {'acceptance_confirmed': '确认验收标准'})
        new.require_complete(answers)

    def test_custom_validation(self):
        for value in ('一个', '一个，两个', '一，二，三，四'):
            with self.assertRaises(ValueError):
                new.update({}, {'custom_adjectives': value})
        self.assertFalse(new.pending(complete(style='自定义')))


class PlanTests(unittest.TestCase):
    def test_21_single_file_combinations(self):
        with tempfile.TemporaryDirectory() as directory:
            for tier in ('T1', 'T2', 'T3'):
                for style, _ in new.STYLES:
                    with self.subTest(tier=tier, style=style):
                        answers = complete(tier, style)
                        output = new.build(answers, plan_for(answers), directory)
                        self.assertEqual([p.name for p in output.iterdir()], ['index.html'])
                        text = (output / 'index.html').read_text(encoding='utf-8')
                        self.assertNotIn('../styles/presets.css', text)
                        self.assertNotIn('<script src="../js/', text)
                        self.assertIn('data-style="' + dict(new.STYLES)[style] + '"', text)
                        if tier == 'T3':
                            self.assertIn('three@0.170.0', text)
                            self.assertNotIn('@latest', text)

    def test_missing_approval_creates_no_directory(self):
        answers = complete()
        plan = plan_for(answers)
        del plan['approval']
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                new.build(answers, plan, directory)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_tampering_requires_new_approval(self):
        answers = complete()
        plan = plan_for(answers)
        plan['key_frames'][0]['effect'] = '不同效果'
        with self.assertRaises(ValueError):
            new.validate_plan(answers, plan)
        answers['art_quality'] = '精细清晰'
        with self.assertRaises(ValueError):
            new.validate_plan(answers, plan_for(complete()))

    def test_direction_and_three_deliverables_required(self):
        answers = complete()
        changes = [lambda p: p.update(directions=p['directions'][:1]),
                   lambda p: p['selection'].update(user_selected=False),
                   lambda p: p.update(screens=[]),
                   lambda p: p['screens'][0].pop('foreground'),
                   lambda p: p.update(key_frames=p['key_frames'][:2]),
                   lambda p: p.pop('assets')]
        for mutation in changes:
            plan = plan_for(answers)
            mutation(plan)
            with self.assertRaises(ValueError):
                new.validate_plan(answers, plan, approved=False)

    def test_real_references_only_or_explicit_no_match(self):
        answers = complete()
        for kind in ('AI 生图', 'AI 效果图', '不明来源'):
            plan = plan_for(answers)
            plan['directions'][0]['references'] = [{'kind': kind, 'source': 'x', 'verification': 'x'}]
            with self.assertRaises(ValueError):
                new.validate_plan(answers, plan, approved=False)
        plan = plan_for(answers)
        del plan['directions'][0]['reference_status']
        with self.assertRaises(ValueError):
            new.validate_plan(answers, plan, approved=False)
        plan['directions'][0]['references'] = [{'kind': '真实画作', 'source': '馆藏原始链接', 'verification': '已打开核验记录'}]
        new.validate_plan(answers, plan, approved=False)

    def test_t3_extra_and_material_scope(self):
        answers = complete('T3')
        for field in ('camera_path', 'lighting_plan', 'postprocessing'):
            plan = plan_for(answers)
            del plan['t3'][field]
            with self.assertRaises(ValueError):
                new.validate_plan(answers, plan, approved=False)
        for method in ('AI 生图', 'Canvas'):
            answers = complete()
            plan = plan_for(answers)
            plan['assets'][0]['method'] = method
            with self.assertRaises(ValueError):
                new.validate_plan(answers, plan, approved=False)
        answers = complete(ai=True)
        plan = plan_for(answers)
        plan['assets'][0].update(method='AI 生图', scope='背景')
        new.validate_plan(answers, plan, approved=False)
        plan['assets'][0]['scope'] = '贴图'
        with self.assertRaises(ValueError):
            new.validate_plan(answers, plan, approved=False)

    def test_academic_purpose_independent_of_style(self):
        answers = new.update(complete(style='科技'), {'purpose': '论文答辩'})
        answers = new.update(answers, {'acceptance_confirmed': True})
        self.assertTrue(new.academic_use(answers))
        self.assertEqual(answers['purpose'], '其他')
        plan = plan_for(answers)
        for field in ('mainline', 'chapters', 'relationships'):
            broken = copy.deepcopy(plan)
            broken['academic'].pop(field)
            with self.assertRaises(ValueError):
                new.validate_plan(answers, broken, approved=False)
        plan['academic']['chapters'][0]['transition'] = ''
        with self.assertRaises(ValueError):
            new.validate_plan(answers, plan, approved=False)
        self.assertIn('陌生真人', new.question('acceptance_confirmed', answers)['title'])

    def test_custom_comment_escaping(self):
        answers = complete(style='自定义')
        answers['custom_reference'] = '--><script>恶意</script>'
        with tempfile.TemporaryDirectory() as directory:
            output = new.build(answers, plan_for(answers), directory)
            text = (output / 'index.html').read_text(encoding='utf-8')
            self.assertNotIn('<script>恶意</script>', text)
            self.assertIn('&lt;script&gt;', text)


class InterfaceTests(unittest.TestCase):
    def test_json_bridge_and_no_auto_build(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / 'intake.json'
            known = Path(directory) / 'known.json'
            known.write_text(json.dumps({'purpose': '课堂展示', 'style': '学术', 'tier': 'T1'}, ensure_ascii=False), encoding='utf-8')
            run = subprocess.run([sys.executable, '-X', 'utf8', str(ROOT / 'new.py'), '--state', str(state), '--known', str(known), '--questions'], capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(run.returncode, 0, run.stderr)
            data = json.loads(run.stdout)
            self.assertEqual(data['questions'][0]['id'], 'art_quality')
            self.assertEqual(data['tool_questions'][0]['options'], new.CHOICES['art_quality'])
            self.assertFalse(list(Path(directory).glob('*/index.html')))

    def test_cli_build_gate_and_complete_plan(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / 'intake.json'
            plan_path = Path(directory) / 'visual-plan.json'
            answers = complete()
            plan = plan_for(answers)
            plan.pop('approval')
            new.save(state, answers)
            new.save(plan_path, plan)
            command = [sys.executable, '-X', 'utf8', str(ROOT / 'new.py'), '--state', str(state), '--plan', str(plan_path)]
            check = subprocess.run(command + ['--check-plan'], capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(check.returncode, 0, check.stderr)
            self.assertEqual(set(json.loads(check.stdout)), {'intake_digest', 'plan_digest'})
            failed = subprocess.run(command + ['--build', '--output-root', directory], capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(failed.returncode, 1)
            self.assertFalse(list(Path(directory).glob('*/index.html')))
            approve(answers, plan)
            new.save(plan_path, plan)
            built = subprocess.run(command + ['--build', '--output-root', directory], capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(built.returncode, 0, built.stderr)
            self.assertTrue(Path(built.stdout.strip()).is_file())

    def test_local_button_api_token_and_round_enforcement(self):
        with tempfile.TemporaryDirectory() as directory:
            sock = socket.socket()
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
            sock.close()
            state = Path(directory) / 'intake.json'
            process = subprocess.Popen([sys.executable, '-X', 'utf8', str(ROOT / 'new.py'), '--state', str(state), '--web', '--no-open', '--port', str(port)], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            base = f'http://127.0.0.1:{port}'
            try:
                for _ in range(100):
                    try:
                        with urlopen(base + '/api/state', timeout=1) as response:
                            data = json.load(response)
                        break
                    except OSError:
                        time.sleep(.05)
                else:
                    self.fail('本地向导未启动')
                self.assertEqual(data['questions'][0]['id'], 'purpose')
                with urlopen(base) as response:
                    page = response.read().decode()
                import re
                token = json.loads(re.search(r'const token=("[^"]+")', page).group(1))
                def post(values, csrf=token):
                    return urlopen(Request(base + '/api/answer', data=json.dumps(values).encode(), headers={'Content-Type': 'application/json', 'X-Intake-Token': csrf}), timeout=2)
                with self.assertRaises(HTTPError) as failure:
                    post({'purpose': '课堂展示'}, 'wrong')
                self.assertEqual(failure.exception.code, 403)
                with self.assertRaises(HTTPError) as failure:
                    post({'tier': 'T3'})
                self.assertEqual(failure.exception.code, 400)
                with post({'purpose': '课堂展示'}) as response:
                    self.assertTrue(json.load(response)['saved'])
                self.assertEqual(new.load(state)['purpose'], '课堂展示')
                with urlopen(base + '/api/state') as response:
                    self.assertEqual(json.load(response)['questions'][0]['id'], 'style')
                self.assertFalse(list(Path(directory).glob('*/index.html')))
            finally:
                process.terminate()
                process.wait(timeout=5)
                process.stderr.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
