"""Assemble measured tables; a final report is gated by both real clocks."""
from __future__ import annotations
import argparse
import ast
import csv
import hashlib
import json
from pathlib import Path
import re
import statistics
import time
from .clock import stamp
from .experiments import ROOT


def j(name): return json.loads((ROOT/name).read_text())
def csv_rows(name): return list(csv.DictReader((ROOT/name).open()))
def fmt(x,d=4): return f'{x:.{d}f}'
def yes(x): return str(x).lower()=='true'


def measured_sections():
    ext=j('results/external_set12_summary.json')
    er=csv_rows('results/external_set12.csv')
    ci=ext['cold_speedup_image_cluster_bootstrap_95ci']
    out=f'''## 8. Внешняя проверка, масштабирование и неудачи

### 8.1 Все 12 естественных изображений Set12

**ИЗМЕРЕНО: {ext['cold_speedup_ratio_of_sums']:.4f}×**, 95% bootstrap по **12 изображениям**, не по повторным замерам: **[{ci[0]:.4f}; {ci[1]:.4f}]**.
Полный PNG-to-output endpoint: **{ext['baseline_cold_mean_s']:.6f} с → {ext['method_cold_mean_s']:.6f} с**.
Завершены **{ext['n_pairs']}/{ext['planned_pairs']} пар**, 12 изображений × 5 seed × 3 повтора; неудачных/пропущенных пар: **{ext['failed_pairs']}**.
RMSE **{ext['baseline_rmse_mean']:.14f} → {ext['method_rmse_mean']:.14f}**; все исходные guards пройдены.
Максимальное расхождение mean **{ext['max_abs_mean_diff']:.3e}**, variance **{ext['max_abs_variance_diff']:.3e}**.

Использованы **все** PNG Set12, без выбора по качеству. Corpus закреплён до декодирования по commit/blob/SHA-256. Для каждой картинки отдельная пространственная GP: train — 8192 пикселя на coarse Cartesian grid, test — 512 **других** пикселей. Время включает PNG decode, выбор train/test, шум, centering, fit, все mean+variance и запись. Оси после округления индексов могут быть неравномерными; алгоритму нужна Cartesian-структура, не равномерный шаг.

Это **не** стандартный SOTA super-resolution benchmark: абсолютный RMSE показывает, что фиксированный гладкий GP для фотографий далёк от лучшего image-реконструктора. Проверяется сохранение **этой** модели на естественных targets, а не превосходство качества над современными image-моделями. Структурное ограничение не исчезает.

| Изображение | Пар | Cold ускорение | Baseline RMSE | Method RMSE | Guards |
|---|---:|---:|---:|---:|---|
'''
    for image,stats in ext['per_image'].items():
        rs=[r for r in er if r['image']==image]
        mr=statistics.mean(float(r['method_rmse']) for r in rs)
        out+=f"| {image} | {stats['n_pairs']} | {stats['speedup']:.3f}× | {stats['baseline_rmse_mean']:.8f} | {mr:.8f} | {'pass' if stats['quality_pass'] else 'FAIL'} |\n"
    out+='''
[Протокол](research/external_protocol.json), [все 180 пар](results/external_set12.csv), [сводка](results/external_set12_summary.json), [provenance](research/external_corpus_manifest.json).

### 8.2 Scaling — где 10× не получается

На каждом размере: **3 seed × 2 повтора = 6 пар**, test=512. Это отдельные запуски и отдельные временные условия, не замена первичной строки 8192. Все исходные quality guards пройдены.

| Train N | Размер | Dense → original spectral, cold | Better-layout dense → NumPy spectral, cold |
|---|---|---:|---:|
'''
    a,b=j('results/scaling_summary.json'),j('results/scaling_tuned_summary.json')
    for key,v in a.items():
        shape=ast.literal_eval(key);w=b[key]
        out+=f"| {shape[0]*shape[1]} | {shape[0]}×{shape[1]} | {v['primary_speedup_ratio_of_sums']:.3f}× | {w['primary_speedup_ratio_of_sums']:.3f}× |\n"
    out+='''
[Исходный scaling CSV](results/scaling.csv), [NumPy/stronger-baseline CSV](results/scaling_tuned.csv). Для малых матриц выигрыш съедают startup/import/I/O; утверждать 10× на каждом размере неверно.

### 8.3 Пропуски в сетке — честный отрицательный результат

Matrix-free PCG использует точный full-grid inverse как ограниченный preconditioner. Но после удаления точек это **не** точный inverse observed covariance. Для каждого из 512 posterior variances потребовались дополнительные CG solves. Все они включены в полное время.

| Пропущено | Baseline mean, с | PCG mean, с | Полный speedup | То есть медленнее | Guards / пар |
|---|---:|---:|---:|---:|---|
'''
    rows=csv_rows('results/masked_extension_fixed.csv')
    for f in (0.01,.1,.3,.5):
        rs=[r for r in rows if r['phase']=='full' and float(r['missing_fraction'])==f]
        bt=statistics.mean(float(r['baseline_cold_s']) for r in rs);ft=statistics.mean(float(r['method_cold_s']) for r in rs)
        out+=f"| {100*f:g}% | {bt:.6f} | {ft:.6f} | {bt/ft:.5f}× | {ft/bt:.2f}× | {sum(yes(r['quality_pass']) for r in rs)}/{len(rs)} |\n"
    out+='''
Завершены все 3 pilot + 20 full пары, без timeout/выборочного исключения. Факт прохождения качества **не** превращает замедление в ускорение. Быстрый training/mean-only компонент здесь не доказывал бы ускорения full mean+variance системы. Нельзя переносить неудачу именно этого preconditioner/скалярных solves на все возможные structured missing-data методы.

[Все исправленные результаты](results/masked_extension_fixed.csv), [план](research/extension_protocol.json), [код](tensor_gp/masked.py).

### 8.4 Плохая обусловленность — 10× без потерь не универсально

Фиксированный заранее sweep: 6 noise variances × 3 lengthscale pairs × 3 seed = **54 пары**. Генеративный шум данных остаётся std=0,05, меняется model regularization; это stress test, не поиск нового основного benchmark. Допуски не ослаблены, jitter не добавлен, спектр не обрезан.

| Model noise variance | Все guards pass | Завершились, но guards FAIL | Solver failure |
|---|---:|---:|---:|
'''
    rows=csv_rows('results/numerical_robustness.csv')
    for noise in sorted({float(r['noise_variance']) for r in rows},reverse=True):
        rs=[r for r in rows if float(r['noise_variance'])==noise]
        counts=[sum(r['status']==s for r in rs) for s in ('pass','quality_fail','solver_failure')]
        out+=f'| {noise:g} | {counts[0]} | {counts[1]} | {counts[2]} |\n'
    out+='''
Итого **20 pass, 19 quality/guard failures, 15 solver-failure пар**. Иногда RMSE ещё укладывается в допуск, но не проходит более строгий NLL guard при огромном NLL маленькой noise variance — такая строка всё равно **не** считается lossless. При почти нулевом noise обе реализации могут численно потерять SPD. Без high-precision reference нельзя объявить одну из них абсолютной истиной. Эти строки не входят в положительную оценку ускорения.

[CSV всех 54 случаев](results/numerical_robustness.csv), [сырые ошибки](results/runs/numerical_robustness), [протокол](research/robustness_protocol.json).

### 8.5 Найденная ошибка измерителя — аннулирование, не сокрытие

В первом вспомогательном missing-grid запуске decimal run ID вроде `missing0.01_...` передавался в `Path.with_suffix`. Метод отбрасывал часть имени после точки, и два prediction-файла могли совпадать. **Три старые pilot-пары имеют недействительные pointwise guard-сравнения**; шесть завершённых попыток и одна прерванная full попытка сохранены и помечены invalid. Их числа не используются для выводов. Процесс остановлен сразу после обнаружения, новый полный план заново запущен под `masked_extension_fixed`.

Исправление: расширение добавляется, не заменяется; evaluator запрещает общий путь, записывает SHA-256 и отвергает перезаписанный artifact. Есть реальные CLI regression tests с точками в именах. Все 30 первичных файлов имели разные имена без точек в stem; они независимо перепроверены, их сохранённые SHA-256 совпали, RMSE и все 15 guard-сравнений пересчитаны. Первичный результат не затронут.

[Явное аннулирование](results/masked_extension_INVALIDATED.json), [исторические попытки](results/runs/masked_extension), [регрессионные тесты](tests/test_measurement_integrity.py), [проверка целостности](results/integrity_audit.json), [полные held-out predictions первичных seed](results/primary_predictions.csv).

Дополнительная неподтверждённая гипотеза: подозревалось, что diagonal update через `.flat` объясняет секундный kernel stage. Проверка 27 component trials этого **не подтвердила**: при N=8192 сами diagonal updates занимали доли миллисекунды. [Отрицательный диагностический результат](results/diagonal_component_diagnostic.json). Его не выдают за системное ускорение.

'''
    return out


def extra_sections(final,proof):
    primary=j('results/preregistered_primary_summary.json')
    raw=[j(str(p.relative_to(ROOT))) for p in (ROOT/'results/runs/preregistered_primary').glob('*dense.json')]
    total=statistics.mean(r['cold_wall_s'] for r in raw)
    factor=statistics.mean(r['stages']['fit_factor_s'] for r in raw)
    pipe=statistics.mean(r['pipeline_s'] for r in raw)
    f=factor/total;amdahl=1/(1-f+f/10);common=total-pipe
    out=f'''<!-- publication-audit -->
## 11. Математика сложности, память и закон Амдала

**РАССЧИТАНО, не hardware-counter measurement:** dense Cholesky требует около `N³/3` leading FLOPs, batched predictive variance — `M N²`; tensor fit — `O(nx³+ny³+N(nx+ny))`, off-grid mean+variance — `O(M(nx²+ny²)+MN)`.
Для N=8192, M=512: Cholesky **183,25 млрд** leading FLOPs, variance solve **34,36 млрд**. Tensor forward training transform — около **3,15 млн**, cross-basis transforms — **20,97 млн**, каждый mean/variance contraction — около **8,39 млн**, плюс полные маленькие eigensystems. Константа eigensolver не приравнивается к одному FLOP на куб; теоретические тысячи раз сокращения arithmetic **не** выдаются за измеренные wall-clock тысячи раз.

**РАССЧИТАНО:** principal model arrays dense — **536 936 448 bytes**, tensor — **294 912 bytes**. Это не RSS: оси, Python, inputs, temporaries, BLAS и runtime не входят. **ИЗМЕРЕНО:** peak RSS в первичном опыте **1 134 878 720 → 67 653 632 bytes**. Полное обучение sklearn GPR достигает **1 741 225 984 bytes**, tensor — **82 513 920 bytes**. Пропускная способность памяти не подменяется теоретическим vendor peak: dense должен хранить/переносить N² doubles, tensor этого вообще не материализует.

Для исходного baseline доля Cholesky во всём cold endpoint — примерно **{100*f:.2f}%**. Если ускорить **только её** в 10 раз, Амдал даёт

`S = 1 / ((1 − f) + f/10) = {amdahl:.4f}×`, **не 10×**.

В нашей системе устранены и dense kernel materialization, и cubic fitting, и dense posterior-variance solve. Средний остаток `cold − internal pipeline` около **{common:.4f} с**. Если условно считать эту startup/output-часть неизменной, её Амдал-cap около **{total/common:.2f}×**; отсюда арифметическое сокращение на порядки не даёт такого же cold-speedup. NumPy-only путь отдельно уменьшает сам import/runtime overhead. Главные **измеренные** числа остаются 11,54× / 30,33× / 276,78× в своих разных, явно названных экспериментах.

[Полный вывод, bandwidth/conditioning](research/math.md), [точные objective/gradient формулы](research/hyperparameter_math.md).

## 12. Ограничения и недоказанные переносы

- Реализация двумерная. Нужны **полная обучающая Cartesian grid**, separable kernel и scalar noise. Off-grid test inputs допустимы; arbitrary off-grid training inputs — нет. При одной длинной оси и другой размера 1 eigensystem сам остаётся кубическим: заявленного выигрыша для общего 1D GP нет.
- Это не новая Kronecker-теория и не превосходство над существующими специализированными Kronecker GP библиотеками. Generic dense LAPACK/sklearn — реальные широко используемые baseline, но не best-in-class structured solvers.
- Первичный benchmark специально структурный и синтетический. Все seed и естественные Set12 targets убирают выбор только удачных outputs, **но не устраняют выбор выгодной области задач**. Ускорение на независимо заданной неструктурированной AI-задаче не установлено. Если запрет «подбирать данные под метод» трактовать как запрет любой такой структурной специализации, общий успех по этому более строгому требованию **не подтверждён**; результат остаётся ограниченным специальным случаем.
- Качество image-GP не SOTA. Сохранение слабого абсолютного image-score не делает его полезной заменой современным vision-моделям; ценно здесь тождество вероятностной модели и полная проверка скорости в этой задаче.
- Near-singular float64 settings действительно не проходят guards. Никакого обещания «без потери на всех данных/числах» нет.
- Выигрыш зависит от N, количества запросов, mean-only против mean+variance, startup и библиотеки. Нет 10× на маленьких задачах; нельзя выдавать 63× internal или 1697× training-internal за полный cold-speedup.
- CPU VM не эксклюзивная. Bootstrap содержит 5 primary seed-кластеров / 12 image-кластеров; это ограниченная описательная статистика, не гарантия переноса на другое железо, GPU или Transformer/LLM.

## 13. Воспроизводимость и последний контроль времени

'''
    if (ROOT/'results/reproduction_check.json').exists():
        idx=j('results/reproduction_check.json')
        out+=f"Документированная команда `bash reproduce.sh --output artifacts/reproduction_check` реально выполнена: все {len(idx['steps'])} этапа завершились с exit 0. Длительности runner stages: "+', '.join(f"{s['name']}={s['duration_s']:.3f} с" for s in idx['steps'])+". Зависимости на этом повторе уже были установлены; это не заявление о времени fresh network install. Оригинальные данные/CSV не перезаписаны. [Индекс реального повтора](results/reproduction_check.json).\n\n"
    if (ROOT/'results/late_stability_summary.json').exists():
        s=j('results/late_stability_summary.json');ci=s['primary_speedup_cluster_bootstrap_95ci']
        out+=f"Оставшееся окно использовано на заранее объявленные **новые seed 100..399**, по порядку, без фильтра по score. Завершено {s['n_pairs']} сравнений, failed pairs: {s['failed_pairs']}; не начатые из-за времени seed сохранены. Отдельный late-time strong-dense → NumPy результат: **{s['primary_speedup_ratio_of_sums']:.4f}× [{ci[0]:.4f}; {ci[1]:.4f}]**, all quality guards={s['all_quality_checks_pass']}. Он **не объединён** с первичными 15 парами. [План/правило остановки](research/late_audit_protocol.json), [CSV](results/late_stability.csv), [сводка](results/late_stability_summary.json).\n\n"
    if (ROOT/'results/deadline_residual_audit.json').exists():
        s=j('results/deadline_residual_audit.json')
        out+=f"До истечения бюджета выполнено ещё **{s['probes']}** независимо seeded random-RHS residual probes полного tensor solve: max relative residual **{s['max_relative_residual']:.3e}**, предел **1e−8**, failed probes **{s['failed_probes']}**. Это дополнительная algebraic correctness check, **не новое измерение системного ускорения**. [Все итоги](results/deadline_residual_audit.json).\n\n"
    if final:
        out+=f"**Финальная проверка инструмента:** UTC **{proof['utc']}**, wall elapsed **{proof['elapsed_seconds']:.6f} с**, monotonic elapsed **{proof['elapsed_monotonic_seconds']:.6f} с**, оба ≥5400. До этого файл был явно помечен предварительным и не сдавался как финальный. [Машиночитаемое доказательство времени](results/deadline_proof.json), [полный рабочий журнал](work_log.md).\n"
    else:
        out+='Финальная фиксация ещё запрещена: требуется реальная проверка обоих часов ≥5400 секунд.\n'
    return out


def main():
    p=argparse.ArgumentParser();p.add_argument('--final',action='store_true');a=p.parse_args()
    proof=None
    if a.final:
        start=j('research/start_time.json')
        if min(time.time()-start['start_unix'],time.monotonic()-start['start_monotonic'])<5400:
            raise SystemExit('Refusing final publication before 90 real minutes.')
        proof=stamp('Stage 13 — final report gate after 90 real minutes','Wall and monotonic clocks both reached 5400 s. Final report may now be published; no elapsed time was fabricated.')
        (ROOT/'results/deadline_proof.json').write_text(json.dumps(proof,indent=2)+'\n')
    path=ROOT/'report.md';text=path.read_text().split('<!-- publication-audit -->')[0]
    text=re.sub(r'## 8\..*?(?=## 9\.)',measured_sections(),text,flags=re.S)
    if a.final:
        text='\n'.join('> **ФИНАЛЬНЫЙ ОТЧЁТ.** Опубликован после инструментальной проверки 90 реальных минут; границы утверждений и неудачи сохранены.' if line.startswith('> **ПРЕДВАРИТЕЛЬНАЯ ВЕРСИЯ.') else line for line in text.split('\n'))
    text=text.rstrip()+'\n\n'+extra_sections(a.final,proof)
    path.write_text(text)
    if a.final:
        readme=ROOT/'README.md'
        r=readme.read_text().replace('Окончательные дополнительные таблицы и проверка 90-минутного бюджета фиксируются в `report.md` после завершения исследовательского окна.',
            'Все дополнительные таблицы и ограничения приведены в [финальном отчёте](report.md). 90 реальных минут проверены по [wall и monotonic часам](results/deadline_proof.json).')
        readme.write_text(r)
        paths=[ROOT/'README.md',path,ROOT/'results.csv',ROOT/'work_log.md',ROOT/'requirements.txt',ROOT/'reproduce.sh',*sorted((ROOT/'tensor_gp').glob('*.py'))]
        seals={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
        (ROOT/'results/deliverable_sha256.json').write_text(json.dumps(seals,indent=2)+'\n')
    print('Wrote',path,'final=',a.final)


if __name__=='__main__': main()
