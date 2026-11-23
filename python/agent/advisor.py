"""GEMMA ADVISOR for the super worm experiment (2026-11-23, owner's choice: option B, Gemma as ADVISOR until tuned).

Gemma (gemma3:12b on the server 'forest', reached through Forest Chat at http://192.168.1.17:8080/api/chat, which
passes requests to Ollama) reads our recorded results and recommends; NOTHING is queued on her say-so. Every
question, her full answer and (for the quiz) whether she was right are logged, so her advice can be measured and
tuned before she is ever allowed to act.

COMMANDS (run on the workstation through the watcher; no GPU needed)
  python -m agent.advisor quiz     BACKTEST / tuning: 12 past experiments with known outcomes (agent/quiz.json). She
                                   sees only the design, picks an outcome, explains why. Score = share correct.
                                   This both "catches her up" (afterwards she is told the truth) and measures her.
  python -m agent.advisor advise   ADVICE: she reads the briefing + the latest super worm results and picks the next
                                   round from a fixed MENU (below), with reasons and expected effect. Logged only.
  python -m agent.advisor ask "question"   free question with the briefing + results as context.

HOW SHE IS "CAUGHT UP" (no retraining needed): every request carries (1) docs/GEMMA_BRIEFING.md as system prompt,
(2) the relevant result files verbatim (retrieval: only what the question needs, to stay within her context),
(3) for 'advise', the quiz answers she got wrong with the true outcome (lessons). Fine-tuning (LoRA) is a later
option once enough logged advice + outcomes exist.

LOGS: agent/logs/advice_log.jsonl (one JSON record per request), agent/logs/latest_*.md (readable copies).
"""
import json
import pathlib
import sys
import time
import urllib.request

URL, MODEL = 'http://192.168.1.17:8080/api/chat', 'gemma3:12b'
if '--model' in sys.argv:                            # e.g. --model qwen2.5:7b (second advisor)
    i = sys.argv.index('--model'); MODEL = sys.argv[i + 1]; del sys.argv[i:i + 2]
import os
_cfg = HERE_ = pathlib.Path(__file__).resolve().parent / 'forest_url.txt'   # one line, written by Claude; no secrets
URL = os.environ.get('FOREST_URL') or (_cfg.read_text().strip() if _cfg.exists() else URL)              # e.g. http://192.168.1.17:11434/api/chat if Ollama is opened to the LAN
AUTH = os.environ.get('FOREST_AUTH')                 # optional Authorization header value, set by the OWNER on the workstation
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent                                   # .../python
LOG = HERE / 'logs'
BRIEF = ROOT.parent / 'docs' / 'GEMMA_BRIEFING.md'
MENU = {
    'continue': 'keep breeding the current 4-world line unchanged for another 300 generations',
    'more_worlds': 'raise scoring to 8 worlds per brain per generation (costs 2x GPU time)',
    'inject_hall': 'replace the weakest 4 brains of each seed with hall-of-fame champions not used yet',
    'restart_from_super': 'start 16 new seeds from the confirmed super worm + mutants, 4-world scoring',
    'cross_lines': 'mix: each seed starts from the best brains of several different seeds (needs a small code change)',
    'stop': 'stop: gains have stalled; write up',
}


def chat(system, user, fmt_json=True, ctx=16384, predict=900):
    body = {'model': MODEL, 'stream': False, 'keep_alive': '1h',
            'options': {'num_ctx': ctx, 'num_predict': predict, 'temperature': 0.2},
            'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}]}
    if fmt_json:
        body['format'] = 'json'
    t = time.time()
    req = urllib.request.Request(URL, data=json.dumps(body).encode(), headers={'Content-Type': 'application/json', **({'Authorization': AUTH} if AUTH else {})})
    r = json.loads(urllib.request.urlopen(req, timeout=600).read())
    return r['message']['content'], dict(seconds=round(time.time() - t, 1), prompt_tokens=r.get('prompt_eval_count'),
                                          reply_tokens=r.get('eval_count'))


def log(kind, record):
    LOG.mkdir(exist_ok=True)
    record = dict(time=time.strftime('%Y-%m-%d %H:%M:%S'), kind=kind, model=MODEL, **record)
    with open(LOG / 'advice_log.jsonl', 'a', encoding='utf-8') as fh:
        fh.write(json.dumps(record) + '\n')
    return record


def read(p):
    p = ROOT / p
    return p.read_text(encoding='utf-8') if p.exists() else f'({p.name} not found)'


def quiz():
    Q = json.loads((HERE / 'quiz.json').read_text())
    sysmsg = ('You are the research advisor for a worm-brain evolution project. Predict the outcome of a past '
              'experiment from its design only. Answer as JSON: {"choice": <one option, copied exactly>, '
              '"confidence": <0-1>, "reason": <one or two sentences>}.')
    right, rows = 0, []
    for q in Q:
        user = f"Experiment: {q['design']}\nOptions: {json.dumps(q['options'])}"
        raw, meta = chat(sysmsg, user)
        try:
            a = json.loads(raw); ch = str(a.get('choice', '')).strip()
        except Exception:
            a, ch = {'raw': raw}, ''
        ok = ch.lower() == q['truth'].lower(); right += ok
        rows.append(dict(id=q['id'], choice=ch, truth=q['truth'], correct=ok, confidence=a.get('confidence'),
                         reason=a.get('reason'), **meta))
        print(f"{q['id']:14s} {'RIGHT' if ok else 'wrong'}  she said: {ch!r}  truth: {q['truth']!r}  ({meta['seconds']} s)", flush=True)
    score = right / len(Q)
    log('quiz', dict(score=score, answers=rows))
    md = [f'# {MODEL} backtest quiz ({time.strftime("%Y-%m-%d %H:%M")}): {right}/{len(Q)} correct ({score:.0%})',
          '(chance level with 3 options: ~33 %)', '']
    md += [f"- **{r['id']}**: {'RIGHT' if r['correct'] else 'WRONG'} - said *{r['choice']}* (truth: *{r['truth']}*), "
           f"confidence {r['confidence']}. Reason: {r['reason']}" for r in rows]
    (LOG / f"latest_quiz_{MODEL.replace(':', '_')}.md").write_text('\n'.join(md) + '\n', encoding='utf-8')
    print(f'QUIZ SCORE {right}/{len(Q)} ({score:.0%})\nADVISOR_QUIZ_DONE', flush=True)


def lessons():
    """Quiz items she got wrong last time, with the truth: fed back so she learns from recorded data."""
    p = LOG / 'advice_log.jsonl'
    if not p.exists():
        return ''
    last = [json.loads(l) for l in p.read_text(encoding='utf-8').splitlines() if '"kind": "quiz"' in l]
    last = [r for r in last if r.get('model') == MODEL]
    if not last:
        return ''
    Q = {q['id']: q for q in json.loads((HERE / 'quiz.json').read_text())}
    wrong = [a for a in last[-1]['answers'] if not a['correct']]
    return '\n'.join(f"- {Q[a['id']]['design']} You predicted '{a['choice']}'; the TRUE outcome was '{a['truth']}'."
                     for a in wrong)


def advise():
    brief = BRIEF.read_text(encoding='utf-8')
    data = '\n\n'.join(f'=== {f} ===\n' + read(f) for f in
                       ('results/step30_hall.txt', 'results/step30_stats.txt', 'results/step30_confirm.txt',
                        'results/step30_rep_stats.txt'))
    les = lessons()
    sysmsg = brief + ('\n\nYou are the ADVISOR for the super worm experiment. You recommend; a human decides. '
                      'Answer as JSON: {"choice": <one menu key>, "why": <3-5 sentences citing the numbers>, '
                      '"expected_effect": <what should change and by how much>, "risk": <what could go wrong>, '
                      '"confidence": <0-1>}.')
    user = ('Latest super worm results:\n' + data + '\n\nLessons from past predictions you got wrong:\n' + (les or '(none yet)')
            + '\n\nMENU of next rounds:\n' + '\n'.join(f'- {k}: {v}' for k, v in MENU.items())
            + '\n\nWhich ONE should the next round be?')
    raw, meta = chat(sysmsg, user, predict=700)
    try:
        a = json.loads(raw)
    except Exception:
        a = {'raw': raw}
    rec = log('advise', dict(advice=a, context_files=['step30_hall', 'step30_stats', 'step30_confirm', 'step30_rep_stats'],
                             lessons_given=bool(les), **meta))
    md = [f"# {MODEL} advice ({rec['time']}, {meta['seconds']} s, {meta['prompt_tokens']} prompt tokens)", '',
          f"**Choice:** {a.get('choice')} ({MENU.get(a.get('choice'), 'not on the menu!')})", '',
          f"**Why:** {a.get('why')}", '', f"**Expected effect:** {a.get('expected_effect')}", '',
          f"**Risk:** {a.get('risk')}", '', f"**Confidence:** {a.get('confidence')}", '',
          '_Advisor mode: nothing was queued. A human (or Claude) decides._']
    (LOG / f"latest_advice_{MODEL.replace(':', '_')}.md").write_text('\n'.join(md) + '\n', encoding='utf-8')
    print('\n'.join(md)); print('ADVISOR_ADVICE_DONE', flush=True)


def ask(q):
    raw, meta = chat(BRIEF.read_text(encoding='utf-8'), q + '\n\nRecent super worm results:\n' + read('results/step30_stats.txt'),
                     fmt_json=False)
    log('ask', dict(question=q, answer=raw, **meta)); print(raw)


if __name__ == '__main__':
    a = sys.argv[1:]
    {'quiz': quiz, 'advise': advise}.get(a[0] if a else '', lambda: ask(' '.join(a[1:])) if a[:1] == ['ask'] else print(__doc__))()
